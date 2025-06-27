import argparse
import asyncio
import json
import logging

from .. import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt
from ..chat import generate_lyrics, prompt_is_okay, route_prompt


async def main_async():
    parser = argparse.ArgumentParser()
    parser.add_argument("flow", type=str, choices=["moderate", "route", "lyrics"])
    parser.add_argument("-c", "--config", type=str, default="4o-v00")
    parser.add_argument("-p", "--prompt", type=str)
    parser.add_argument("-f", "--prompt_path", type=str)
    args = parser.parse_args()

    detailed_prompt = None
    simple_prompt = None
    if args.prompt_path is not None:
        with open(args.prompt_path, "r") as f:
            detailed_prompt = DetailedTextToMusicPrompt.from_json_dict(json.load(f))
    elif args.prompt is not None:
        simple_prompt = SimpleTextToMusicPrompt.from_text(args.prompt)
    else:
        raise ValueError("Either --prompt or --prompt_path must be provided")

    logging.basicConfig(level=logging.DEBUG)
    if args.flow == "moderate":
        print(await prompt_is_okay(simple_prompt, config=args.config))
    elif args.flow == "route":
        print(await route_prompt(simple_prompt, config=args.config))
    elif args.flow == "lyrics":
        print(await generate_lyrics(detailed_prompt, config=args.config))
    else:
        raise ValueError(f"Invalid flow: {args.flow}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
