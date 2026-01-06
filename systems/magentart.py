import math
import time
from typing import Optional

import nest_asyncio
from magenta_rt import audio, system

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicGPUSystem

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()


class MagentaRealTime(TextToMusicGPUSystem):
    def __init__(
        self,
        tag: str = "large",
        default_duration: float = 20.0,
        max_duration: float = 180.0,
        device: str = "gpu",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._tag = tag
        self._default_duration = default_duration
        self._max_duration = max_duration
        self._device = device
        self._model: Optional[system.MagentaRT] = None

    def _prepare(self):
        self._model = system.MagentaRT(tag=self._tag, device=self._device, lazy=False)

    def _release(self):
        del self._model

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental:
            return PromptSupport.UNSUPPORTED
        if prompt.duration is not None and prompt.duration > self._max_duration:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        assert self._model is not None
        timings = []

        # Extract duration
        duration = prompt.duration or self._default_duration
        if duration > self._max_duration:
            duration = self._max_duration

        # Embed style
        timings.append(("style", time.time()))
        style = self._model.embed_style(prompt.overall_prompt)

        # Generate audio
        timings.append(("generate", time.time()))
        num_chunks = math.ceil(duration / self._model.config.chunk_length)
        state = None
        chunks = []
        for i in range(num_chunks):
            chunk, state = self._model.generate_chunk(state=state, style=style)
            chunks.append(chunk)
            timings.append((f"chunk {i}", time.time()))

        # Concatenate chunks
        timings.append(("concatenate", time.time()))
        generated = audio.concatenate(chunks)
        result = Audio(samples=generated.samples, sample_rate=generated.sample_rate)

        # Crop audio
        timings.append(("crop", time.time()))
        result = result.crop(duration=duration)
        timings.append(("done", time.time()))

        return TextToMusicResponse(
            audio=result,
            custom_timings=timings,
        )
