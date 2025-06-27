import json
from typing import Optional

from ..dataclass import SimpleTextToMusicPrompt
from ..exceptions import ChatException, PromptContentException
from .backend import ChatBackend, chat_completion
from .helper import format_examples, load_json_examples

PROMPT_V00 = """
You are a specialized AI assistant that moderates text prompts and lyrics from users. Your task is to determine if the text prompt is appropriate for a music generation model.

{rules}

{pre_examples}

{examples}

{pre_query}

{query}
""".strip()

RULES_V00 = """
We want to moderate prompts that contain any of the following *rationale*:

["Music Reference", "Copyrighted", "Insensitive", "Explicit", "Profanity"]

An explanation of each *rationale* is provided below:

- Music Reference: References to real music artists, songs, albums
- Copyrighted: Lyrics that are from a well-known copyrighted song (though folk songs are okay!)
- Insensitive: Culturally insensitive content: racial slurs, hate speech, or other offensive content
- Explicit: Explicit content: sexually explicit or violent content
- Profanity: Profanity is okay to use, but only if it is appropriate for the style/genre/topics

Be aware that a user may try to deliberately deceive the content moderation filter by introducing typos like "Tailor Shwift". Moderate these cases as well.
""".strip()

PRE_EXAMPLES_V00 = """
For prompts that pass moderation, you must respond with a valid JSON object matching this specification:

{
    "is_okay": true
}

For prompts that pass moderation, you must respond with a valid JSON object matching this specification:

{
    "is_okay": false,
    "rationale": str
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
Now, you will be given an actual user prompt. You must respond with a valid JSON object only. The rationale should match one of the parenthetical rationales above.
""".strip()


QUERY_V00 = """
========================================================================================
Input:
{input}

Output (JSON only):
""".strip()


_CONFIGS = {
    "4o-v00": {
        "backend": ChatBackend.OPENAI_GPT4O,
        "prompt": PROMPT_V00,
        "rules": RULES_V00,
        "pre_examples": PRE_EXAMPLES_V00,
        "examples": "moderate_v00",
        "example_template": EXAMPLE_V00,
        "pre_query": PRE_QUERY_V00,
        "query": QUERY_V00,
        "backend_kwargs": {
            "max_tokens": 64,
            "force_json": True,
        },
    }
}


async def prompt_is_okay(
    prompt: SimpleTextToMusicPrompt, config: str = "4o-v00", seed: Optional[int] = None
) -> bool:
    if config not in _CONFIGS:
        raise ValueError(f"Invalid config: {config}")
    attrs = _CONFIGS[config]
    text_input = attrs["prompt"].format(
        rules=attrs["rules"],
        pre_examples=attrs["pre_examples"],
        examples=format_examples(
            load_json_examples(attrs["examples"]), attrs["example_template"]
        ),
        pre_query=attrs["pre_query"],
        query=attrs["query"].format(input=prompt.prompt),
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
    if result_dict["is_okay"]:
        return True
    else:
        raise PromptContentException(
            rationale=result_dict.get("rationale", None),
            error_message=result_dict.get("error_message", None),
        )
