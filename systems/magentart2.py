import math
import time
from typing import Optional

from magenta_rt import MagentaRT2Jax

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicGPUSystem

# The MRT2 JAX backend generates audio one frame at a time. 25 frames == 1
# second of 48kHz stereo audio (see magenta_rt.jax.generate).
FRAMES_PER_SECOND = 25


class MagentaRealTime2(TextToMusicGPUSystem):
    def __init__(
        self,
        size: str = "mrt2_base",
        default_duration: float = 20.0,
        max_duration: float = 30.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._size = size
        self._default_duration = default_duration
        self._max_duration = max_duration
        self._model: Optional[MagentaRT2Jax] = None

    def _prepare(self):
        # Builds the model, loads the checkpoint, and JIT-compiles the
        # streaming step (assets are baked into the image at build time).
        self._model = MagentaRT2Jax(size=self._size)

    def _release(self):
        del self._model
        self._model = None

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
        style = self._model.embed_style(
            prompt.overall_prompt, use_mapper=True, seed=seed
        )

        # Generate audio (streaming generation runs internally over the frames)
        timings.append(("generate", time.time()))
        frames = math.ceil(duration * FRAMES_PER_SECOND)
        waveform, _ = self._model.generate(style=style, frames=frames)
        timings.append(("done_generate", time.time()))

        result = Audio(samples=waveform.samples, sample_rate=waveform.sample_rate)

        # Crop audio to the requested duration
        timings.append(("crop", time.time()))
        result = result.crop(duration=duration)
        timings.append(("done", time.time()))

        return TextToMusicResponse(
            audio=result,
            custom_timings=timings,
        )
