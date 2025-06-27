import argparse
import asyncio
import concurrent.futures
import json
import logging

from ..audio import AudioEncoding
from ..chat.route import route_prompt
from ..dataclass.prompt import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt
from ..env import CONTAINER_COMPONENT, CONTAINER_SYSTEM_KEY, EXECUTING_IN_CONTAINER
from ..path import CONTAINER_IO_DIR
from ..registry import init_system
from ..system import PromptSupport

_LOGGER = logging.getLogger(__name__)


def write_response_to_disk(response, stem, generation_idx):
    """Write a single response to disk (audio and lyrics)."""
    response.audio.write(
        CONTAINER_IO_DIR / f"{stem}-{generation_idx}.mp3", encoding=AudioEncoding.MP3_V0
    )
    if response.lyrics is not None:
        with open(CONTAINER_IO_DIR / f"{stem}-{generation_idx}.txt", "w") as f:
            f.write(response.lyrics)
    _LOGGER.info(
        f"Generated audio and lyrics saved to {stem}-{generation_idx}.wav and {stem}-{generation_idx}.txt"
    )


async def main_async():
    """Main async function that handles prompt construction and generation."""
    # Check if we are in a system container
    if not (
        EXECUTING_IN_CONTAINER
        and CONTAINER_COMPONENT == "system"
        and CONTAINER_SYSTEM_KEY is not None
    ):
        raise RuntimeError("This command must be run in a system container")

    logging.basicConfig(level=logging.INFO)

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--num_generations",
        type=int,
        default=1,
        help="Number of generations to run",
    )
    parser.add_argument(
        "-s", "--seed", type=int, help="Random seed for reproducibility"
    )
    parser.add_argument("-p", "--prompt", help="Simple text prompt for generation")
    parser.add_argument(
        "--skip_route",
        action="store_false",
        dest="route",
        help="If specified, call the router to expand the prompt",
    )
    parser.add_argument("-f", "--prompt_filename", help="Filename to JSON prompt file")
    args = parser.parse_args()

    # Construct prompt
    if args.prompt_filename is not None:
        with open(CONTAINER_IO_DIR / args.prompt_filename, "r") as f:
            prompt = DetailedTextToMusicPrompt.from_json_dict(json.load(f))
    elif args.prompt is not None:
        if args.route:
            prompt = await route_prompt(SimpleTextToMusicPrompt(prompt=args.prompt))
        else:
            prompt = DetailedTextToMusicPrompt(
                overall_prompt=args.prompt, instrumental=True
            )
    else:
        raise ValueError("Either --prompt or --prompt_filename must be provided")

    # Write prompt to disk
    checksum = prompt.checksum[:4]
    prompt_output_filename = f"{checksum}.json"
    prompt_output_path = CONTAINER_IO_DIR / prompt_output_filename
    _LOGGER.info(f"Writing prompt to {prompt_output_filename}")
    with open(prompt_output_path, "w") as f:
        f.write(json.dumps(prompt.as_json_dict(), indent=2))
    _LOGGER.info(f"Prompt: {prompt}")

    # Initialize system
    _LOGGER.info(f"Initializing system: {CONTAINER_SYSTEM_KEY}")
    system = init_system(CONTAINER_SYSTEM_KEY, lazy=False)
    supported = system.prompt_support(prompt)
    _LOGGER.log(
        logging.INFO if supported == PromptSupport.SUPPORTED else logging.WARNING,
        f"Prompt support status: {supported}",
    )

    # Generate audio
    stem = f"{checksum}-{CONTAINER_SYSTEM_KEY.system_tag}-{CONTAINER_SYSTEM_KEY.variant_tag}"
    generation_idx = 0
    _LOGGER.info(
        f"Generating {args.num_generations} audio files with seed {args.seed}..."
    )

    # Use ThreadPoolExecutor for concurrent disk writes
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        write_tasks = []

        # Stream responses and write them as they become available
        async for response in system.generate_stream(
            [prompt] * args.num_generations, args.seed
        ):
            # Submit write task (non-blocking)
            task = executor.submit(
                write_response_to_disk, response, stem, generation_idx
            )
            write_tasks.append(task)
            generation_idx += 1

        # Wait for all writes to complete
        for task in concurrent.futures.as_completed(write_tasks):
            task.result()  # This will raise any exceptions that occurred


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
