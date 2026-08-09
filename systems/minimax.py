import logging
import time
from io import BytesIO

import requests

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

_API_URL = "https://api.minimax.io/v1/music_generation"
_CONTENT_MODERATION_STATUS_CODE = 1026


class MiniMaxMusic(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        model: str = "music-3.0-free",
        sample_rate: int = 44100,
        bitrate: int = 256000,
        audio_format: str = "wav",
        timeout: float = 300.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._api_key = get_secret("MINIMAX_API_KEY").strip()
        self._model = model
        self._sample_rate = sample_rate
        self._bitrate = bitrate
        self._audio_format = audio_format
        self._timeout = timeout

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        # The API does not expose a duration control parameter; song length is
        # determined by the model. We crop locally when a duration is requested.
        if prompt.duration is not None:
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings: list[tuple[str, float]] = []

        # Non-instrumental generations need lyrics. If the caller didn't supply
        # any, let MiniMax auto-generate them from the prompt via
        # `lyrics_optimizer` (supported on all four music-2.6/3.0 [-free] models)
        # rather than generating them ourselves. The API doesn't echo back the
        # auto-generated lyrics, so we only have text to report when the caller
        # supplied it explicitly.
        lyrics = None
        lyrics_optimizer = False
        if not prompt.instrumental:
            lyrics = prompt.lyrics
            lyrics_optimizer = lyrics is None

        payload = {
            "model": self._model,
            "prompt": prompt.overall_prompt or "",
            "is_instrumental": bool(prompt.instrumental),
            "lyrics_optimizer": lyrics_optimizer,
            "output_format": "hex",
            "stream": False,
            "audio_setting": {
                "sample_rate": self._sample_rate,
                "bitrate": self._bitrate,
                "format": self._audio_format,
            },
        }
        if lyrics is not None:
            payload["lyrics"] = lyrics

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        _LOGGER.info(
            "Calling MiniMax Music generation model='%s' with prompt='%s', is_instrumental=%s",
            self._model,
            payload["prompt"],
            payload["is_instrumental"],
        )
        s = time.time()
        timings.append(("call", s))
        resp = requests.post(
            _API_URL, json=payload, headers=headers, timeout=self._timeout
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"MiniMax Music request failed: {resp.status_code} {resp.text}"
            )
        result = resp.json()

        base_resp = result.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        if status_code == _CONTENT_MODERATION_STATUS_CODE:
            raise PromptContentException(
                base_resp.get("status_msg", "Content flagged for sensitive material")
            )
        if status_code != 0:
            raise RuntimeError(
                f"MiniMax Music generation failed: {status_code} {base_resp.get('status_msg')}"
            )

        data = result.get("data") or {}
        audio_hex = data.get("audio")
        if not audio_hex:
            raise RuntimeError("MiniMax Music returned no audio")
        timings.append(("decode", time.time()))

        audio_bytes = bytes.fromhex(audio_hex)
        audio = Audio.from_file(BytesIO(audio_bytes))
        timings.append(("done", time.time()))

        if prompt.duration is not None:
            audio = audio.crop(duration=prompt.duration)

        return TextToMusicResponse(
            audio=audio,
            lyrics=lyrics,
            custom_timings=timings,
        )
