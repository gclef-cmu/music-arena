import logging
import subprocess
import tempfile
import time

import numpy as np
from riff_api import RiffAPIClient
from riff_api.types import SoundPrompt

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.audio import ffprobe_metadata
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

_LOGGER = logging.getLogger(__name__)


def _ffmpeg_decode(audio_path: str) -> Audio:
    ffmpeg_cmd = [
        "ffmpeg",
        "-i",
        audio_path,
        "-f",
        "f32le",  # 32-bit float little-endian
        "-ac",
        "2",  # force stereo
        "-",  # output to stdout
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
    samples = np.frombuffer(result.stdout, dtype=np.float32)
    samples = samples.reshape(-1, 2)  # reshape to stereo
    sample_rate = ffprobe_metadata(audio_path)["sample_rate"]
    return Audio(samples=samples, sample_rate=sample_rate)


class Riffusion(TextToMusicAPISystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None

    def _prepare(self):
        self._client = RiffAPIClient(api_key=get_secret("RIFFUSION_API_KEY"))

    def _release(self):
        del self._client

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental and prompt.lyrics is not None:
            # Conditioning on specific lyrics has issues depending on lyrics length.
            return PromptSupport.PARTIAL
        if prompt.duration is not None or (
            prompt.duration is not None and prompt.duration > 217
        ):
            # Riffusion doesn't explicitly handle user-specified duration.
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings = []

        # Adapt prompt to Riffusion API
        if prompt.instrumental or prompt.lyrics is None:
            fn = "prompt"
            kwargs = {
                "prompt": prompt.overall_prompt,
                "instrumental": prompt.instrumental,
            }
        else:
            fn = "compose"
            kwargs = {
                "sound_prompts": [
                    SoundPrompt(text=prompt.overall_prompt, strength=0.5)
                ],
                "lyrics": prompt.lyrics,
                "lyrics_strength": 0.5,
                "weirdness": 0.5,
            }

        # Call Riffusion API
        with tempfile.TemporaryDirectory() as temp_dir:
            _LOGGER.info(f"Calling Riffusion API with {fn} and {kwargs}")
            s = time.time()
            timings.append(("call", s))
            response = getattr(self._client, fn)(
                **kwargs,
                moderate_inputs=True,
                audio_format="m4a",
                save_to=f"{temp_dir}/audio.m4a",
            )
            _LOGGER.info(f"Riffusion API response in {time.time() - s:.2f} seconds")
            timings.append(("decode", time.time()))
            audio = _ffmpeg_decode(f"{temp_dir}/audio.m4a")
            timings.append(("done", time.time()))

        if prompt.duration is not None:
            audio = audio.crop(duration=prompt.duration)
        lyrics = prompt.lyrics if prompt.lyrics is not None else response.lyrics
        return TextToMusicResponse(audio=audio, lyrics=lyrics, custom_timings=timings)
