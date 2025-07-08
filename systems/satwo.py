import logging
import time
from io import BytesIO

import requests

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

_LOGGER = logging.getLogger(__name__)


class StableAudio2(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        duration: float = 60.0,
        steps: int = 50,
        cfg_scale: float = 7.0,
        max_duration: float = 190.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._api_key = get_secret("STABILITY_API_KEY")
        self._duration = duration
        self._steps = steps
        self._cfg_scale = cfg_scale
        self._max_duration = max_duration

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental or prompt.lyrics is not None:
            # Stable Audio 2.0 does not support vocals
            return PromptSupport.UNSUPPORTED
        if prompt.duration is not None and prompt.duration > self._max_duration:
            # Stable Audio 2.0 typically supports up to 190 seconds
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings = []

        # Prepare the prompt for Stability API
        text_prompt = prompt.overall_prompt

        # Determine duration
        duration = prompt.duration if prompt.duration is not None else self._duration

        # Clamp duration to limits for Stability API
        duration = min(duration, self._max_duration)

        # Call Stability API
        _LOGGER.info(
            f"Calling Stability API with prompt: {text_prompt}, duration: {duration}"
        )
        s = time.time()
        timings.append(("call", s))

        # Prepare the request
        url = "https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "audio/*",
        }
        files = {"none": ""}
        data = {
            "prompt": text_prompt,
            "seed": seed,
            "steps": self._steps,
            "cfg_scale": self._cfg_scale,
            "duration": duration,
            "output_format": "wav",
        }

        # Make the API request
        response = requests.post(url, headers=headers, files=files, data=data)

        if response.status_code != 200:
            raise Exception(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        _LOGGER.info(f"Stability API response in {time.time() - s:.2f} seconds")
        timings.append(("decode", time.time()))

        # Save response content to BytesIO and load audio
        bio = BytesIO(response.content)
        audio = Audio.from_file(bio)

        timings.append(("done", time.time()))

        # Apply duration cropping if needed
        audio = audio.crop(duration=duration)

        return TextToMusicResponse(audio=audio, lyrics=None, custom_timings=timings)
