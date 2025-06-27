from typing import Any

import numpy as np
import torch
from einops import rearrange
from huggingface_hub import login as hf_login
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.secret import get_secret
from music_arena.system import TextToMusicGPUBatchedSystem


class StableAudioOpen(TextToMusicGPUBatchedSystem):
    def __init__(
        self,
        model_name: str = "stabilityai/stable-audio-open-1.0",
        max_duration: float = 47.0,
        generate_kwargs: dict[str, Any] = {
            "steps": 100,
            "cfg_scale": 7.0,
            "sigma_min": 0.3,
            "sigma_max": 500,
            "sampler_type": "dpmpp-3m-sde",
        },
        normalize: bool = True,
        gpu_mem_gb_per_item: float = 8.0,
    ):
        super().__init__(gpu_mem_gb_per_item=gpu_mem_gb_per_item)
        self.model_name = model_name
        self._max_duration = max_duration
        self._generate_kwargs = generate_kwargs
        self._normalize = normalize
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = None
        self._model_config = None

    def _prepare(self):
        hf_login(token=get_secret("HUGGINGFACE_READ_TOKEN"))
        self._model, self._model_config = get_pretrained_model(self.model_name)
        self._model = self._model.to(self._device)
        self._sample_rate = self._model_config["sample_rate"]
        self._sample_size = self._model_config["sample_size"]

    def _release(self):
        assert self._model is not None
        del self._model
        del self._model_config
        torch.cuda.empty_cache()

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental:
            return PromptSupport.UNSUPPORTED
        if prompt.duration is not None and prompt.duration > self._max_duration:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        assert self._model is not None

        # Prepare conditioning
        durations = []
        conditioning = []
        for prompt in prompts:
            # Compute duration
            if prompt.duration is None:
                duration = self._max_duration
            else:
                duration = min(prompt.duration, self._max_duration)
            durations.append(duration)
            conditioning.append(
                {
                    "prompt": prompt.overall_prompt,
                    "seconds_start": 0,
                    "seconds_total": duration,
                }
            )

        # Generate audio
        output = generate_diffusion_cond(
            model=self._model,
            batch_size=len(prompts),
            conditioning=conditioning,
            sample_size=self._sample_size,
            device=self._device,
            seed=seed,
            **self._generate_kwargs,
        )

        # Rearrange audio batch to a single sequence
        output = rearrange(output, "b c n -> b n c")
        output = output.cpu().numpy().astype(np.float32)

        # Aggregate each output
        results = []
        for i, duration in enumerate(durations):
            audio = Audio(
                samples=output[i],
                sample_rate=self._sample_rate,
            )
            audio = audio.crop(duration=duration)
            if self._normalize:
                audio = audio.peak_normalize(in_place=True, peak_dbfs=-1.0)
            results.append(TextToMusicResponse(audio=audio))

        return results


class StableAudioOpenV1(StableAudioOpen):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            model_name="stabilityai/stable-audio-open-1.0",
            max_duration=47.0,
            generate_kwargs={
                "steps": 100,
                "cfg_scale": 7.0,
                "sigma_min": 0.3,
                "sigma_max": 500,
                "sampler_type": "dpmpp-3m-sde",
            },
            gpu_mem_gb_per_item=2.0,
            **kwargs,
        )


class StableAudioOpenSmall(StableAudioOpen):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            model_name="stabilityai/stable-audio-open-small",
            max_duration=11.0,
            generate_kwargs={
                "steps": 8,
                "cfg_scale": 1.0,
                "sampler_type": "pingpong",
            },
            gpu_mem_gb_per_item=1.0,
            **kwargs,
        )
