import abc
import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from .base import MusicArenaDataClass


@dataclass
class BasePrompt(MusicArenaDataClass):

    @property
    def checksum(self) -> str:
        d = self.as_json_dict()
        d = {k: v for k, v in d.items() if v is not None}
        return hashlib.md5(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class SimpleTextToMusicPrompt(BasePrompt):
    prompt: str

    @classmethod
    def from_text(cls, text: str) -> "SimpleTextToMusicPrompt":
        return cls(prompt=text)


@dataclass
class DetailedTextToMusicPrompt(BasePrompt):
    overall_prompt: str
    instrumental: bool
    lyrics: Optional[str] = None
    duration: Optional[float] = None
    bpm: Optional[float] = None

    def __post_init__(self):
        if self.instrumental and self.lyrics is not None:
            raise ValueError("Lyrics must be None for instrumental music")

    @property
    def generate_lyrics(self) -> bool:
        return not self.instrumental and self.lyrics is None
