import argparse
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import fastapi
import nest_asyncio
import uvicorn

from ..audio import AudioEncoding
from ..dataclass import DetailedTextToMusicPrompt
from ..env import (
    CONTAINER_COMPONENT,
    CONTAINER_HOST_GIT_HASH,
    CONTAINER_SYSTEM_KEY,
    EXECUTING_IN_CONTAINER,
)
from ..registry import init_system
from ..system import TextToMusicSystem

_SYSTEM: Optional[TextToMusicSystem] = None
_APP = fastapi.FastAPI()
_QUEUE: asyncio.Queue = None
_MAX_BATCH_SIZE: int = 1
_MAX_DELAY: float = 10.0


@dataclass
class QueueItem:
    prompt: DetailedTextToMusicPrompt
    future: asyncio.Future
    timestamp: float


@_APP.get("/health")
def health():
    return {"status": "ok"}


@_APP.post("/generate")
async def generate(prompt_dict: dict):
    assert _SYSTEM is not None
    prompt = DetailedTextToMusicPrompt.from_json_dict(prompt_dict)

    # Create a future to wait for the result
    future = asyncio.Future()
    queue_item = QueueItem(prompt=prompt, future=future, timestamp=time.time())

    # Add to queue
    await _QUEUE.put(queue_item)

    # Wait for result
    try:
        response = await future
        result = response.as_json_dict_with_encoding(AudioEncoding.MP3_V0)
    except Exception as e:
        raise fastapi.HTTPException(status_code=500, detail=str(e))

    result["git_hash"] = CONTAINER_HOST_GIT_HASH
    return result


async def process_batch(batch: List[QueueItem]):
    """Process a batch of queue items using generate_stream for optimal batching."""
    if not batch:
        return

    assert _SYSTEM is not None and _SYSTEM.ready
    try:
        # Extract prompts from batch items
        prompts = [item.prompt for item in batch]
        logging.info(f"Processing batch of {len(prompts)} prompts")

        # Use generate_stream for efficient batch processing
        responses = []
        try:
            async for response in _SYSTEM.generate_stream(prompts):
                responses.append(response)
                logging.info(f"Received response {len(responses)}/{len(prompts)}")
        except Exception as stream_error:
            logging.error(f"Error during generate_stream: {stream_error}")
            raise

        # Match responses back to futures
        if len(responses) != len(batch):
            raise RuntimeError(f"Expected {len(batch)} responses, got {len(responses)}")

        for i, (item, response) in enumerate(zip(batch, responses)):
            logging.info(
                f"Setting result for item {i}, response type: {type(response)}"
            )
            if response is None:
                logging.error(f"Got None response for item {i}")
                item.future.set_exception(RuntimeError("Generated response is None"))
            else:
                item.future.set_result(response)

    except Exception as e:
        logging.error(f"Error in process_batch: {e}", exc_info=True)
        # If batch processing fails, set exception for all items
        for item in batch:
            if not item.future.done():
                item.future.set_exception(e)


async def queue_processor():
    """Background task that processes the queue based on batch size and delay constraints."""
    batch = []

    while True:
        try:
            # Calculate timeout based on oldest item in current batch
            timeout = None
            if batch:
                oldest_timestamp = batch[0].timestamp
                elapsed = time.time() - oldest_timestamp
                timeout = max(0, _MAX_DELAY - elapsed)

            # Try to get an item from the queue
            try:
                if timeout is not None and timeout <= 0:
                    # Process current batch immediately if delay exceeded
                    if batch:
                        await process_batch(batch)
                        batch = []
                    continue

                item = await asyncio.wait_for(_QUEUE.get(), timeout=timeout)
                batch.append(item)
                logging.info(f"Added item to batch, current size: {len(batch)}")

                # Process batch if we've reached max batch size
                if len(batch) >= _MAX_BATCH_SIZE:
                    logging.info(f"Processing batch due to size limit: {len(batch)}")
                    await process_batch(batch)
                    batch = []

            except asyncio.TimeoutError:
                # Timeout reached, process current batch
                if batch:
                    await process_batch(batch)
                    batch = []

        except Exception as e:
            logging.error(f"Error in queue processor: {e}")
            # Set exception for any items in current batch
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(e)
            batch = []


def main():
    # Check if we are in a system container
    if not (
        EXECUTING_IN_CONTAINER
        and CONTAINER_COMPONENT == "system"
        and CONTAINER_SYSTEM_KEY is not None
        and CONTAINER_HOST_GIT_HASH is not None
    ):
        raise RuntimeError("This command must be run in a system container")

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--max_batch_size",
        type=int,
        default=1,
        help="Maximum number of requests to batch together",
    )
    parser.add_argument(
        "--max_delay",
        type=float,
        default=4.0,
        help="Maximum delay in seconds before processing a batch",
    )
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Apply nest_asyncio to allow nested event loops
    nest_asyncio.apply()

    # Set global queue parameters
    global _QUEUE, _MAX_BATCH_SIZE, _MAX_DELAY
    _QUEUE = asyncio.Queue()
    _MAX_BATCH_SIZE = args.max_batch_size
    _MAX_DELAY = args.max_delay

    # Initialize system
    global _SYSTEM
    _SYSTEM = init_system(CONTAINER_SYSTEM_KEY)
    _SYSTEM.prepare()

    # Start queue processor as background task
    @_APP.on_event("startup")
    async def startup_event():
        asyncio.create_task(queue_processor())

    # Run server
    uvicorn.run(_APP, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
