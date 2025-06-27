import json
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any


def _as_json(o: Any) -> Any:
    if isinstance(o, MusicArenaDataClass):
        return o.as_json_dict()
    elif isinstance(o, Enum):
        return o.value
    elif isinstance(o, tuple):
        return tuple(_as_json(v) for v in o)
    elif isinstance(o, list):
        return [_as_json(v) for v in o]
    elif isinstance(o, dict):
        return {k: _as_json(v) for k, v in o.items()}
    return o


@dataclass
class MusicArenaDataClass:
    def as_dict(self) -> dict[str, Any]:
        """Returns dict of self."""
        return asdict(self)

    def as_json_dict(self) -> dict[str, Any]:
        """Returns dict of self."""
        return _as_json(self.as_dict())

    def copy(self, **kwargs) -> "MusicArenaDataClass":
        """Returns a copy of self."""
        return replace(self, **kwargs)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MusicArenaDataClass":
        """Returns instance of self from dict."""
        return cls(**d)

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "MusicArenaDataClass":
        """Returns instance of self from JSON dict."""
        return cls.from_dict(d)

    @classmethod
    def from_json(cls, json_str: str) -> "MusicArenaDataClass":
        """Returns instance of self from JSON string."""
        return cls.from_json_dict(json.loads(json_str))
