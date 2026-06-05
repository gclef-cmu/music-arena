import time
from typing import Any, Optional

import numpy as np
import torch
from huggingface_hub import login as hf_login
from stable_audio_3 import StableAudioModel

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.secret import get_secret
from music_arena.system import TextToMusicGPUSystem


class StableAudio3(TextToMusicGPUSystem):
    def __init__(
        self,
        model_name: str = "medium",
        max_duration: float = 120.0,
        default_duration: float = 120.0,
        # Defaults match the stable-audio-3 CLI for post-trained models.
        generate_steps: int = 8,
        generate_cfg_scale: float = 1.0,
        model_half: bool = True,
        normalize: bool = True,
        generate_kwargs: dict[str, Any] = {},
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model_name = model_name
        self._max_duration = max_duration
        self._default_duration = default_duration
        self._generate_steps = generate_steps
        self._generate_cfg_scale = generate_cfg_scale
        self._model_half = model_half
        self._normalize = normalize
        self._generate_kwargs = generate_kwargs
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model: Optional[StableAudioModel] = None

    def _prepare(self):
        hf_login(token=get_secret("HUGGINGFACE_READ_TOKEN"))
        self._model = StableAudioModel.from_pretrained(
            self._model_name,
            device=self._device,
            model_half=self._model_half,
        )
        self._sample_rate = self._model.model.sample_rate

    def _release(self):
        assert self._model is not None
        del self._model
        self._model = None
        torch.cuda.empty_cache()

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

        # Compute duration
        if prompt.duration is None:
            duration = self._default_duration
        else:
            duration = min(prompt.duration, self._max_duration)

        # Generate audio (returns [batch, channels, samples])
        timings.append(("generate", time.time()))
        output = self._model.generate(
            prompt=prompt.overall_prompt,
            duration=duration,
            steps=self._generate_steps,
            cfg_scale=self._generate_cfg_scale,
            seed=seed,
            **self._generate_kwargs,
        )
        timings.append(("done_generate", time.time()))

        # Convert to [samples, channels] float32
        samples = output[0].transpose(0, 1).cpu().numpy().astype(np.float32)
        audio = Audio(samples=samples, sample_rate=self._sample_rate)

        # Crop to requested duration
        audio = audio.crop(duration=duration)
        if self._normalize:
            audio = audio.peak_normalize(in_place=True, peak_dbfs=-1.0)
        timings.append(("done", time.time()))

        return TextToMusicResponse(audio=audio, custom_timings=timings)


class StableAudio3Medium(StableAudio3):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            model_name="medium",
            max_duration=120.0,
            default_duration=120.0,
            **kwargs,
        )


class StableAudio3SmallMusic(StableAudio3):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            model_name="small-music",
            max_duration=120.0,
            default_duration=120.0,
            **kwargs,
        )
