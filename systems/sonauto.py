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
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

_LOGGER = logging.getLogger(__name__)

_API_BASE_URL = "https://api.sonauto.ai"


class Sonauto(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        prompt_strength: float = 2.3,
        balance_strength: float = 0.7,
        poll_interval: float = 1.0,
        timeout: float = 300.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._api_key = get_secret("SONAUTO_API_KEY").strip()
        self._prompt_strength = prompt_strength
        self._balance_strength = balance_strength
        self._poll_interval = poll_interval
        self._timeout = timeout

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        # Sonauto's base generation returns ~95s audio and does not take a custom duration.
        # We support cropping locally when a duration is provided.
        if prompt.duration is not None:
            return PromptSupport.PARTIAL
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        timings: list[tuple[str, float]] = []

        # Build generation payload (see https://sonauto.ai/developers)
        payload: dict = {
            "prompt": prompt.overall_prompt or "",
            "instrumental": bool(prompt.instrumental),
            "prompt_strength": float(self._prompt_strength),
            "balance_strength": float(self._balance_strength),
            "seed": int(seed),
            "num_songs": 1,
            "output_format": "flac",
            "bpm": "auto" if prompt.bpm is None else round(prompt.bpm),
        }
        if not prompt.instrumental and prompt.lyrics is not None:
            payload["lyrics"] = prompt.lyrics

        url = f"{_API_BASE_URL}/v1/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        _LOGGER.info(
            f"Calling Sonauto API with prompt='{payload.get('prompt')}', instrumental={payload.get('instrumental')}"
        )
        s = time.time()
        timings.append(("call", s))
        create_resp = requests.post(url, json=payload, headers=headers)
        if create_resp.status_code != 200:
            raise RuntimeError(
                f"Sonauto create failed: {create_resp.status_code} {create_resp.text}"
            )
        task_id = create_resp.json().get("task_id")
        if not task_id:
            raise RuntimeError("Sonauto create returned no task_id")

        # Poll for completion
        status_url = f"{_API_BASE_URL}/v1/generations/{task_id}"
        start_poll = time.time()
        result_json = None
        while True:
            poll_resp = requests.get(status_url, headers=headers)
            if poll_resp.status_code != 200:
                raise RuntimeError(
                    f"Sonauto status failed: {poll_resp.status_code} {poll_resp.text}"
                )
            result_json = poll_resp.json()
            status = result_json.get("status")
            if status == "SUCCESS":
                break
            if status == "FAILURE":
                err_msg = result_json.get("error_message")
                raise RuntimeError(f"Sonauto generation failed: {err_msg}")
            if time.time() - start_poll > self._timeout:
                raise TimeoutError("Sonauto generation timed out")
            time.sleep(self._poll_interval)

        timings.append(("decode", time.time()))
        song_paths = result_json.get("song_paths") or []
        if len(song_paths) == 0:
            raise RuntimeError("Sonauto returned no song paths")
        # Use the first song
        audio_url = song_paths[0]
        audio_resp = requests.get(audio_url)
        if audio_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to download Sonauto audio: {audio_resp.status_code}"
            )
        audio = Audio.from_file(BytesIO(audio_resp.content))
        timings.append(("done", time.time()))

        # Optionally crop to requested duration
        if prompt.duration is not None:
            audio = audio.crop(duration=prompt.duration)

        # Lyrics: present for vocal generations; omit for instrumental
        lyrics = None if prompt.instrumental else result_json.get("lyrics")
        return TextToMusicResponse(audio=audio, lyrics=lyrics, custom_timings=timings)
