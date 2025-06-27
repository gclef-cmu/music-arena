import base64
import io
from dataclasses import dataclass, field
from typing import Any, Optional

from ..audio import Audio, AudioEncoding
from .base import MusicArenaDataClass


@dataclass
class BaseResponse(MusicArenaDataClass):
    pass


@dataclass
class TextToMusicResponse(BaseResponse):
    audio: Audio
    lyrics: Optional[str] = None
    custom_timings: list[tuple[str, float]] = field(default_factory=list)

    def as_json_dict_with_encoding(self, encoding: AudioEncoding) -> dict[str, Any]:
        result = super().as_json_dict()
        audio_bytes = io.BytesIO()
        self.audio.write(audio_bytes, encoding=encoding)
        result["audio_b64"] = base64.b64encode(audio_bytes.getvalue()).decode("utf-8")
        del result["audio"]
        return result

    def as_json_dict(self) -> dict[str, Any]:
        """Returns dict of self."""
        return self.as_json_dict_with_encoding(AudioEncoding.WAV_F32)

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "TextToMusicResponse":
        """Returns instance of self from JSON dict."""
        if "audio_b64" in d:
            audio = Audio.from_file(io.BytesIO(base64.b64decode(d["audio_b64"])))
            d["audio"] = audio
            del d["audio_b64"]
        if "custom_timings" in d:
            d["custom_timings"] = [(e, t) for e, t in d["custom_timings"]]
        return cls.from_dict(d)
