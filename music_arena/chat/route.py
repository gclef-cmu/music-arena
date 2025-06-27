import json
import logging
from typing import Iterator, Optional

from ..dataclass import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt
from ..exceptions import ChatException, PromptContentException
from .backend import ChatBackend, chat_completion
from .helper import format_examples, load_json_examples
from .moderate import RULES_V00 as MODERATION_RULES_V00

_LOGGER = logging.getLogger(__name__)

PROMPT_V00 = """
You are a specialized AI assistant performing two tasks: (1) moderate natural language text prompts from users, and (2) for prompts that pass moderation, convert them to a structured representation.

{moderation_rules}

{routing_rules}

{pre_examples}

{examples}

{pre_query}

{query}
""".strip()

RULES_V00 = """
For prompts that pass moderation, your goals in priority order are to:

1. Determine if the user intends for their prompt to be *instrumental-only*, or if they want it to contain lyrics. If there is ambiguity, err on the side of instrumental.
2. Determine if the user has suggested a specific *duration* for the song. If so, output the duration in *seconds*. Otherwise, output null. Unless the user has been very specific, err on the side of null.
""".strip()

PRE_EXAMPLES_V00 = """
For prompts that fail moderation, you must respond with a valid JSON object matching this specification:

{
    "is_okay": false,
    "rationale": str
}

For prompts that pass moderation, you must respond with a valid JSON object matching this specification:

{
    "is_okay": true,
    "instrumental": bool,
    "duration": number | null,
}

Here are some examples input / output pairs.
""".strip()

EXAMPLE_V00 = """
========================================================================================
Input:
{input}

Output (JSON only):
{output}
""".strip()


PRE_QUERY_V00 = """
Now, you will be given an actual user prompt. You must respond with a valid JSON object only. The error message, if relevant, should be short and similar to the error message in one of the provided examples above.
""".strip()


QUERY_V00 = """
========================================================================================
Input:
{input}

Output (JSON only):
""".strip()


def moderate_to_route_v00(examples: list[dict]) -> Iterator[dict]:
    for example in examples:
        if not example["output"]["is_okay"]:
            yield example


_ROUTE_CONFIGS = {
    "4o-v00": {
        "backend": ChatBackend.OPENAI_GPT4O,
        "prompt": PROMPT_V00,
        "moderation_rules": MODERATION_RULES_V00,
        "routing_rules": RULES_V00,
        "pre_examples": PRE_EXAMPLES_V00,
        "moderation_examples": "moderate_v00",
        "moderation_convert_fn": moderate_to_route_v00,
        "routing_examples": "route_v00",
        "example_template": EXAMPLE_V00,
        "pre_query": PRE_QUERY_V00,
        "query": QUERY_V00,
        "backend_kwargs": {
            "max_tokens": 64,
            "force_json": True,
        },
    }
}


async def route_prompt(
    simple_prompt: SimpleTextToMusicPrompt,
    config: str = "4o-v00",
    seed: Optional[int] = None,
) -> DetailedTextToMusicPrompt:
    if config not in _ROUTE_CONFIGS:
        raise ValueError(f"Invalid config: {config}")
    _LOGGER.info(f"Routing prompt: {simple_prompt}")

    attrs = _ROUTE_CONFIGS[config]

    # Load moderation examples
    moderation_examples = load_json_examples(attrs["moderation_examples"])

    # Load routing examples
    routing_examples = load_json_examples(attrs["routing_examples"])

    # Combine all examples (moderation + routing)
    all_examples = list(attrs["moderation_convert_fn"](moderation_examples)) + list(
        routing_examples
    )

    text_input = attrs["prompt"].format(
        moderation_rules=attrs["moderation_rules"],
        routing_rules=attrs["routing_rules"],
        pre_examples=attrs["pre_examples"],
        examples=format_examples(all_examples, attrs["example_template"]),
        pre_query=attrs["pre_query"],
        query=attrs["query"].format(input=simple_prompt.prompt),
    )

    result = await chat_completion(
        attrs["backend"],
        text_input,
        seed=seed,
        **attrs["backend_kwargs"],
    )
    result = result.strip()

    try:
        result_dict = json.loads(result)
        assert "is_okay" in result_dict
    except json.JSONDecodeError:
        raise ChatException("Invalid JSON output")
    except AssertionError:
        raise ChatException("Incomplete JSON output")

    _LOGGER.info(f"Route result: {result_dict}")

    if not result_dict["is_okay"]:
        raise PromptContentException(
            rationale=result_dict.get("rationale", None),
            error_message=result_dict.get("error_message", None),
        )

    # Convert the routing result to TextToMusicPrompt
    return DetailedTextToMusicPrompt(
        overall_prompt=simple_prompt.prompt,
        instrumental=result_dict["instrumental"],
        duration=result_dict["duration"],
    )
