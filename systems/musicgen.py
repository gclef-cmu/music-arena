import logging

import torch
from audiocraft.models import musicgen

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicGPUBatchedSystem

SAMPLE_RATE = 32000
LOGGER = logging.getLogger(__name__)


class MusicGen(TextToMusicGPUBatchedSystem):
    def __init__(
        self,
        model_size: str = "small",
        temperature: float = 1.0,
        top_p: float = 0.0,
        top_k: int = 250,
        gpu_mem_gb_per_item: float = 8.0,
    ):
        super().__init__(gpu_mem_gb_per_item=gpu_mem_gb_per_item)
        self.model_size = f"facebook/musicgen-{model_size}"
        self._model = None
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k

    def _prepare(self):
        self._model = musicgen.MusicGen.get_pretrained(self.model_size, device="cuda")
        self._model.set_generation_params(
            temperature=self._temperature, top_p=self._top_p, top_k=self._top_k
        )

    def _release(self):
        assert self._model is not None
        del self._model
        torch.cuda.empty_cache()

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental:
            return PromptSupport.UNSUPPORTED
        if prompt.duration is not None and prompt.duration > 30:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        if any(not p.instrumental or p.lyrics is not None for p in prompts):
            LOGGER.warning("Only instrumental music is supported")
        assert self._model is not None
        torch.manual_seed(seed)
        batch_samples = self._model.generate(
            descriptions=[p.overall_prompt for p in prompts]
        )
        batch_samples = batch_samples.cpu().numpy()
        responses = []
        for samples, prompt in zip(batch_samples, prompts):
            audio = Audio(samples=samples.swapaxes(0, 1), sample_rate=SAMPLE_RATE)
            if prompt.duration is not None:
                audio = audio.crop(duration=prompt.duration)
            responses.append(TextToMusicResponse(audio=audio))
        return responses


class MusicGenSmall(MusicGen):
    def __init__(self, gpu_mem_gb_per_item: float = 8.0, **kwargs):
        super().__init__(
            model_size="small", gpu_mem_gb_per_item=gpu_mem_gb_per_item, **kwargs
        )


class MusicGenMedium(MusicGen):
    def __init__(self, gpu_mem_gb_per_item: float = 16.0, **kwargs):
        super().__init__(
            model_size="medium", gpu_mem_gb_per_item=gpu_mem_gb_per_item, **kwargs
        )


class MusicGenLarge(MusicGen):
    def __init__(self, gpu_mem_gb_per_item: float = 32.0, **kwargs):
        super().__init__(
            model_size="large", gpu_mem_gb_per_item=gpu_mem_gb_per_item, **kwargs
        )
