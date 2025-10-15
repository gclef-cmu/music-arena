import logging
import time
from io import BytesIO

import numpy as np
from elevenlabs.client import ElevenLabs

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.exceptions import PromptContentException
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

_LOGGER = logging.getLogger(__name__)


class ElevenLabsMusic(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        default_duration_ms: int = 20000,
        model_id: str = "music_v1",
        output_format: str = "mp3_44100_128",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._client = ElevenLabs(api_key=get_secret("ELEVENLABS_API_KEY").strip())
        self._default_duration_ms = int(default_duration_ms)
        self._model_id = model_id
        self._output_format = output_format

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        # The Eleven Music quickstart exposes prompt + duration.
        # Support for explicitly-specified lyrics is unclear (treating as PARTIAL).
        if prompt.lyrics is not None:
            return PromptSupport.PARTIAL
        if prompt.duration is not None and (
            prompt.duration < 3.0 or prompt.duration > 300.0
        ):
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings: list[tuple[str, float]] = []

        # Determine duration in milliseconds
        if prompt.duration is not None:
            music_length_ms = int(round(prompt.duration * 1000.0))
            music_length_ms = max(music_length_ms, 3000)
            music_length_ms = min(music_length_ms, 300000)
        else:
            music_length_ms = self._default_duration_ms

        _LOGGER.info(
            f"Calling ElevenLabs Music compose_detailed with duration_ms={music_length_ms}"
        )
        s = time.time()
        timings.append(("call", s))

        # Use compose_detailed to retrieve metadata and audio bytes
        try:
            # Ensure seed is within int32 range to avoid validation error
            seed = seed % (2**31)
            audio = self._client.music.compose(
                model_id=self._model_id,
                output_format=self._output_format,
                seed=seed,
                prompt=prompt.overall_prompt,
                force_instrumental=prompt.instrumental,
                music_length_ms=music_length_ms,
            )
            audio_bytes = b"".join(audio)
        except Exception as e:
            if (
                hasattr(e, "body")
                and isinstance(e.body, dict)
                and "detail" in e.body
                and e.body["detail"]["status"] == "bad_prompt"
            ):
                raise PromptContentException(e.body["detail"]["message"])
            raise e

        # Load audio from returned bytes
        if self._output_format.startswith("pcm"):
            sample_rate = int(self._output_format.split("_")[1])
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
            samples = samples.reshape(-1, 2)
            samples = samples.astype(np.float32) / 32768.0
            audio = Audio(samples=samples, sample_rate=sample_rate)
        else:
            audio = Audio.from_file(BytesIO(audio_bytes))
        timings.append(("done", time.time()))

        # TODO: Retrieve lyrics from output?
        return TextToMusicResponse(audio=audio, lyrics=None, custom_timings=timings)
