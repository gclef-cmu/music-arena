import functools
import json

from ..path import LIB_DIR


@functools.lru_cache(maxsize=100)
def load_json_examples(tag: str) -> list[dict]:
    return json.load(open(LIB_DIR / "chat" / "examples" / f"{tag}.json"))


def format_examples(examples: list[dict], template: str) -> str:
    return "\n".join(
        template.format(
            input=example["input"],
            output=json.dumps(example["output"], indent=4),
        )
        for example in examples
    )
