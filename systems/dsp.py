import numpy as np

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicLocalSystem


class Noise(TextToMusicLocalSystem):
    def __init__(
        self,
        gain: float = 0.01,
        lyrics: str = "Noise",
        duration: float = 10.0,
        sample_rate: int = 44100,
        num_channels: int = 1,
    ):
        super().__init__(max_batch_size=None)
        self.gain = gain
        self.lyrics = lyrics
        self.duration = duration
        self.sample_rate = sample_rate
        self.num_channels = num_channels

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        if not prompt.instrumental or prompt.lyrics is not None:
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        np.random.seed(seed)
        result = []
        for p in prompts:
            duration = self.duration if p.duration is None else p.duration
            lyrics = self.lyrics if p.lyrics is None else p.lyrics
            samples = (
                np.random.randn(int(self.sample_rate * duration), self.num_channels)
                * self.gain
            )
            result.append(
                TextToMusicResponse(
                    audio=Audio(samples=samples, sample_rate=self.sample_rate),
                    lyrics=lyrics,
                )
            )
        return result
