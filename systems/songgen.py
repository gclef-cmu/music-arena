import asyncio
import time

import nest_asyncio
import torch
from songgen import SongGenMixedForConditionalGeneration, SongGenProcessor

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


class SongGen(TextToMusicGPUSystem):
    def __init__(
        self,
        ckpt_path: str = "LiuZH-19/SongGen_mixed_pro",
        lyrics_config: str = "4o-v00",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._ckpt_path = ckpt_path
        self._model = None
        self._processor = None
        self._lyrics_config = lyrics_config

    def _prepare(self):
        # Initialize model
        self._model = SongGenMixedForConditionalGeneration.from_pretrained(
            self._ckpt_path, attn_implementation="sdpa"
        ).to("cuda")

        # Initialize processor
        self._processor = SongGenProcessor(self._ckpt_path, "cuda")

    def _release(self):
        assert self._model is not None
        del self._model
        del self._processor
        torch.cuda.empty_cache()
        self._model = None
        self._processor = None

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if prompt.duration is not None and prompt.duration > 30.0:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings = []
        assert self._model is not None
        assert self._processor is not None

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
                        prompt=prompt.copy(duration=30.0),
                        config=self._lyrics_config,
                    )
                )

        # Prepare model inputs
        timings.append(("preprocess", time.time()))
        model_inputs = self._processor(
            text=prompt.overall_prompt,
            lyrics=lyrics,
            ref_voice_path=None,
            separate=False,
        )

        # Generate audio
        timings.append(("generate", time.time()))
        generation = self._model.generate(**model_inputs, do_sample=True)
        timings.append(("done", time.time()))

        # Convert to numpy and create Audio object
        audio_arr = generation.cpu().numpy().squeeze()
        audio = Audio(
            samples=audio_arr,
            sample_rate=self._model.config.sampling_rate,
        )
        if prompt.duration is not None:
            audio = audio.crop(duration=prompt.duration)

        return TextToMusicResponse(
            audio=audio,
            lyrics=lyrics if not prompt.instrumental else None,
            custom_timings=timings,
        )
