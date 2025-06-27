import enum
import functools
import logging
from typing import Optional

import openai

from ..secret import get_secret

LOGGER = logging.getLogger(__name__)


class ChatBackend(enum.Enum):
    OPENAI_GPT4O = "openai-gpt-4o"


@functools.lru_cache
def _get_openai_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=get_secret("OPENAI_API_KEY"))


async def openai_chat_completion(
    backend: ChatBackend,
    text_input: str,
    max_tokens: int = 400,
    stop_tokens: Optional[list[str]] = None,
    seed: Optional[int] = None,
    force_json: bool = False,
) -> str:
    client = _get_openai_client()
    if backend == ChatBackend.OPENAI_GPT4O:
        model = "gpt-4o"
    else:
        raise ValueError(f"Invalid backend: {backend}")
    LOGGER.debug(
        f"Sending request to {backend} ({model}) with text_input:\n```\n{text_input}\n```"
    )

    # Prepare request parameters
    request_params = {
        "model": model,
        "messages": [
            {"role": "user", "content": text_input},
        ],
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop_tokens,
    }

    # Add response_format if JSON is forced
    if force_json:
        request_params["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**request_params)
    response_message = response.choices[0].message.content
    LOGGER.debug(f"Response message: {repr(response_message)}")
    return response_message


async def chat_completion(backend: ChatBackend, text_input: str, **kwargs) -> str:
    if backend in [ChatBackend.OPENAI_GPT4O]:
        return await openai_chat_completion(backend, text_input, **kwargs)
    else:
        raise ValueError(f"Invalid backend: {backend}")
