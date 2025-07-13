import asyncio
import tempfile
import time

import nest_asyncio
import numpy as np
import torch
from acestep.pipeline_ace_step import ACEStepPipeline
from scipy.io.wavfile import read as wavread

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.chat.lyrics import generate_lyrics
from music_arena.system import TextToMusicGPUSystem

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()


class ACEStep(TextToMusicGPUSystem):
    def __init__(
        self,
        duration: float = 30.0,
        steps: int = 60,
        lyrics_config: str = "4o-v00",
        normalize: bool = True,
        bfloat16: bool = True,
        torch_compile: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model = None
        self._duration = duration
        self._steps = steps
        self._lyrics_config = lyrics_config
        self._normalize = normalize
        self._bfloat16 = bfloat16
        self._torch_compile = torch_compile

    def _prepare(self):
        self._model = ACEStepPipeline(
            dtype="bfloat16" if self._bfloat16 else "float32",
            torch_compile=self._torch_compile,
        )

    def _release(self):
        assert self._model is not None
        del self._model
        torch.cuda.empty_cache()
        self._model = None

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if prompt.duration is not None and prompt.duration > self._duration:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings = []
        assert self._model is not None

        # Set random seed
        torch.manual_seed(seed)

        # Extract lyrics
        if prompt.instrumental:
            lyrics = ""
        else:
            lyrics = prompt.lyrics
            if lyrics is None:
                timings.append(("lyrics", time.time()))
                lyrics = asyncio.run(
                    generate_lyrics(
                        prompt=prompt.copy(duration=self._duration),
                        config=self._lyrics_config,
                    )
                )

        # Determine duration
        duration = prompt.duration if prompt.duration is not None else self._duration

        # Generate audio
        timings.append(("generate", time.time()))
        with tempfile.TemporaryDirectory() as temp_dir:
            path, _ = self._model(
                prompt=prompt.overall_prompt,
                lyrics=lyrics,
                audio_duration=duration,
                infer_step=self._steps,
                save_path=temp_dir,
            )
            sample_rate, samples = wavread(path)
        timings.append(("done", time.time()))

        assert samples.dtype == np.int16
        samples = samples.astype(np.float32) / 32768.0

        # Normalize audio to float32 between -1 and 1
        if self._normalize:
            norm_factor = np.max(np.abs(samples))
            if norm_factor > 0:
                samples /= norm_factor

        # Create Audio object with the properly formatted array
        audio = Audio(
            samples=samples,  # Now in channels-second format
            sample_rate=sample_rate,
        )

        return TextToMusicResponse(
            audio=audio,
            lyrics=lyrics if not prompt.instrumental else None,
            custom_timings=timings,
        )
