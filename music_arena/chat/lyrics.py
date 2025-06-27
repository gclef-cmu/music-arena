from typing import Optional

from ..dataclass import DetailedTextToMusicPrompt
from .backend import ChatBackend, chat_completion

PROMPT_V00 = """
You are a specialized AI assistant that transforms brief text prompts from users into appropriate lyrics. Your generated lyrics will be paired with the original text prompt and fed to a music generation model that takes in a text prompt and lyrics as input and outputs completed songs.

{instruction}

The user prompt is:

```
{prompt}
```

Please generate lyrics that would be appropriate for the target duration of `{duration}` seconds (will be None if the user did not specify a duration).
""".strip()


INSTRUCTION_V00 = """
A user will provide a text prompt which will likely be somewhat vague. It may contain just a description of style/genre (e.g., "lo-fi beats", "dreamy synthwave"). It may contain just a topic (e.g., "a song about a roadtrip with Bob"). It may contain neither or both.

Analyze the provided music style to understand or infer its:

- Topical themes and subject matter, if specified
- Intended style/genre, if unspecified
- Emotional tone and atmosphere
- Common vocabulary, slang, or linguistic patterns
- Intended language, if appropriate (e.g., "Cumbia" should usually yield Spanish lyrics)
- Typical song structure for that genre
- Intended length of the lyrics, if specified (e.g., "less than 60 seconds", or "just include a chorus", or "just one verse")

Generate lyrics that authentically match the style and are:

- Lyrics that feel natural and appropriate for the text prompt
- Consistent voice, perspective, and emotional tone
- Appropriate for the style/genre/topics both in language and content
- Appropriate for the intended length of the lyrics, if specified

Guidelines

- Capture the essence of the requested style without relying on cliches
- Generate unique lyrics, not derivative of existing songs
- Consider rhythm, meter, and how the words will flow when sung
- Exclude section labels (e.g., no [Verse 1], [Chorus])
- Adjust to styles ranging from minimal (ambient, lo-fi) to complex (rap, prog rock)
- Create lyrics that are specific enough to be meaningful but open enough for musical interpretation
- Even if the style prompt says to, do not generate any toxic lyrics, racial slurs or hate speech, sexually explicit content, or profanity

Just output the lyrics, do not output anything else. Do not include any explanations or additional text.
""".strip()


_CONFIGS = {
    "4o-v00": {
        "backend": ChatBackend.OPENAI_GPT4O,
        "prompt": PROMPT_V00,
        "instruction": INSTRUCTION_V00,
        "max_tokens": 512,
    }
}


async def generate_lyrics(
    prompt: DetailedTextToMusicPrompt,
    config: str = "4o-v00",
    seed: Optional[int] = None,
) -> str:
    if config not in _CONFIGS:
        raise ValueError(f"Invalid config: {config}")
    attrs = _CONFIGS[config]
    text_input = attrs["prompt"].format(
        prompt=prompt.overall_prompt,
        duration=prompt.duration,
        instruction=attrs["instruction"],
    )
    return await chat_completion(
        attrs["backend"], text_input, max_tokens=attrs["max_tokens"], seed=seed
    )
