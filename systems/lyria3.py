import logging
import time
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

_LOGGER = logging.getLogger(__name__)


class Lyria3(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        model_id_secret_name: str = "API_MODEL_ID",
        fixed_duration: float = 30.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._model_id_secret_name = model_id_secret_name
        self._fixed_duration = fixed_duration
        self._model_id: Optional[str] = None
        self._client: Optional[genai.Client] = None

    def _prepare(self):
        self._client = genai.Client(api_key=get_secret("GEMINI_API_KEY"))
        self._model_id = get_secret(self._model_id_secret_name).strip()

    def _release(self):
        if self._client is not None:
            del self._client
            self._client = None
        self._model_id = None

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        # The Lyria 3 30s model always returns a fixed-length generation.
        if prompt.duration is not None and prompt.duration > self._fixed_duration:
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        assert self._client is not None
        assert self._model_id is not None
        timings: list[tuple[str, float]] = []

        _LOGGER.info("Calling Lyria 3 model='%s'", self._model_id)
        s = time.time()
        timings.append(("call", s))
        text_prompt = prompt.overall_prompt
        if prompt.instrumental and "instrumental" not in text_prompt.lower():
            text_prompt = f"{text_prompt} (instrumental only)"
        response = self._client.models.generate_content(
            model=self._model_id,
            contents=text_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Audio", "Text"],
            ),
        )
        timings.append(("decode", time.time()))

        audio_bytes = None
        text_parts: list[str] = []
        for part in response.parts:
            if part.text:
                text_parts.append(part.text)
            if part.inline_data and part.inline_data.data:
                audio_bytes = part.inline_data.data

        if audio_bytes is None:
            raise RuntimeError("Lyria 3 response did not contain audio inline_data.")

        audio = Audio.from_file(BytesIO(audio_bytes))
        if prompt.duration is not None:
            audio = audio.crop(duration=min(prompt.duration, self._fixed_duration))
        timings.append(("done", time.time()))

        # Lyria 3 returns text parts containing lyric/timing metadata.
        lyrics = (
            prompt.lyrics
            if prompt.lyrics is not None
            else (text_parts[0] if text_parts else None)
        )
        return TextToMusicResponse(audio=audio, lyrics=lyrics, custom_timings=timings)
