import enum
import pathlib
from dataclasses import dataclass, field
from typing import Any, Optional

from .base import MusicArenaDataClass


class SystemAccess(enum.Enum):
    OPEN = "OPEN"
    PROPRIETARY = "PROPRIETARY"


@dataclass
class SystemKey(MusicArenaDataClass):
    system_tag: str
    variant_tag: str

    def __post_init__(self):
        if ":" in self.system_tag:
            raise ValueError("System tag cannot contain ':'")
        if ":" in self.variant_tag:
            raise ValueError("Variant tag cannot contain ':'")

    def __hash__(self):
        return hash(self.as_string())

    def __eq__(self, other):
        if not isinstance(other, SystemKey):
            return False
        return self.as_string() == other.as_string()

    def as_string(self) -> str:
        return f"{self.system_tag}:{self.variant_tag}"

    @classmethod
    def from_string(cls, s: str) -> "SystemKey":
        system_tag, variant_tag = s.split(":")
        return cls(system_tag=system_tag, variant_tag=variant_tag)


@dataclass
class TextToMusicSystemMetadata(MusicArenaDataClass):
    # Required fields
    key: SystemKey
    display_name: str
    description: str
    organization: str
    access: SystemAccess
    supports_lyrics: bool
    # Variant fields
    registry_dir: pathlib.Path
    module_name: str
    class_name: str
    # Optional fields
    private: bool = False
    requires_gpu: Optional[bool] = None
    model_type: Optional[str] = None
    training_data: dict[str, Any] = field(default_factory=dict)
    citation: Optional[str] = None
    links: dict[str, str] = field(default_factory=dict)
    release_audio_publicly: bool = True
    # Optional variant fields
    docker_base: Optional[str] = None
    secrets: list[str] = field(default_factory=list)
    init_kwargs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.access = SystemAccess(self.access)
        if self.requires_gpu is None:
            self.requires_gpu = True if self.access == SystemAccess.OPEN else False

    @property
    def primary_link(self) -> Optional[str]:
        if self.links is None or len(self.links) == 0:
            return None
        for link_type in ["home", "paper", "code"]:
            if link_type in self.links:
                return self.links[link_type]
        return list(self.links.values())[0]

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "TextToMusicSystemMetadata":
        if "access" in d:
            d["access"] = SystemAccess(d["access"])
        return cls.from_dict(d)
