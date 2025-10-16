import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from ..env import CONTAINER_COMPONENT, CONTAINER_HOST_GIT_HASH, EXECUTING_IN_CONTAINER
from ..helper import create_uuid, salted_checksum
from ..secret import get_secret
from .base import MusicArenaDataClass
from .prompt import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt
from .system_metadata import SystemKey


class Preference(Enum):
    A = "A"
    B = "B"
    TIE = "TIE"
    BOTH_BAD = "BOTH_BAD"


class ListenEvent(Enum):
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    STOP = "STOP"
    TICK = "TICK"


@dataclass
class Session(MusicArenaDataClass):
    deployment: Optional[str] = None
    uuid: Optional[str] = None
    create_time: Optional[float] = None
    frontend_git_hash: Optional[str] = None
    ack_tos: Optional[str] = None
    new_battle_times: list[float] = field(default_factory=list)

    def __post_init__(self):
        if self.uuid is None:
            self.uuid = create_uuid()
        if self.create_time is None:
            self.create_time = time.time()
        if (
            self.frontend_git_hash is None
            and EXECUTING_IN_CONTAINER
            and CONTAINER_COMPONENT == "frontend"
            and CONTAINER_HOST_GIT_HASH is not None
        ):
            self.frontend_git_hash = CONTAINER_HOST_GIT_HASH


@dataclass
class User(MusicArenaDataClass):
    ip: Optional[str] = None
    salted_ip: Optional[str] = None
    fingerprint: Optional[str] = None
    salted_fingerprint: Optional[str] = None

    def __post_init__(self):
        # Anonymizes on creation for improved user privacy
        salt = get_secret("ANONYMIZED_USER_SALT", randomly_initialize=True)
        if self.ip is not None:
            self.salted_ip = salted_checksum(self.ip, salt)
            del self.ip
        if self.fingerprint is not None:
            self.salted_fingerprint = salted_checksum(self.fingerprint, salt)
            del self.fingerprint
        assert self.ip is None and self.fingerprint is None

    @property
    def checksum(self) -> str:
        d = {"salted_ip": self.salted_ip, "salted_fingerprint": self.salted_fingerprint}
        return hashlib.md5(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()


def sum_listen_time(listen_data: list[tuple[ListenEvent, float]]) -> float:
    last_play = None
    total_time = 0
    for event, timestamp in listen_data:
        if event == ListenEvent.PLAY:
            last_play = timestamp
        elif event in [ListenEvent.PAUSE, ListenEvent.TICK] and last_play is not None:
            play_time = timestamp - last_play
            if play_time > 0:
                total_time += play_time
            # For PAUSE, stop tracking; for TICK, continue tracking from this point
            if event == ListenEvent.PAUSE:
                last_play = None
            else:  # event == ListenEvent.TICK
                last_play = timestamp
    return total_time


@dataclass
class Vote(MusicArenaDataClass):
    a_listen_data: list[tuple[ListenEvent, float]] = field(default_factory=list)
    b_listen_data: list[tuple[ListenEvent, float]] = field(default_factory=list)
    preference: Optional[Preference] = None
    preference_time: Optional[float] = None
    feedback: Optional[str] = None
    a_feedback: Optional[str] = None
    b_feedback: Optional[str] = None
    feedback_time: Optional[float] = None

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "preference" and value is not None and self.preference_time is None:
            super().__setattr__("preference_time", time.time())
        if (
            name in ["feedback", "a_feedback", "b_feedback"]
            and value is not None
            and self.feedback_time is None
        ):
            super().__setattr__("feedback_time", time.time())

    def play(self, name: Literal["a", "b"]):
        attr = f"{name}_listen_data"
        getattr(self, attr).append((ListenEvent.PLAY, time.time()))

    def pause(self, name: Literal["a", "b"]):
        attr = f"{name}_listen_data"
        getattr(self, attr).append((ListenEvent.PAUSE, time.time()))

    def tick(self, name: Literal["a", "b"]):
        attr = f"{name}_listen_data"
        getattr(self, attr).append((ListenEvent.TICK, time.time()))

    def sum_listen_time(self, name: Literal["a", "b"]) -> float:
        return sum_listen_time(getattr(self, f"{name}_listen_data"))

    @property
    def a_listen_time(self) -> Optional[float]:
        return self.sum_listen_time("a")

    @property
    def b_listen_time(self) -> Optional[float]:
        return self.sum_listen_time("b")

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Vote":
        if d.get("preference") is not None:
            d["preference"] = Preference[d["preference"]]
        if "a_listen_data" in d:
            d["a_listen_data"] = [(ListenEvent[e], t) for e, t in d["a_listen_data"]]
        if "b_listen_data" in d:
            d["b_listen_data"] = [(ListenEvent[e], t) for e, t in d["b_listen_data"]]
        return cls.from_dict(d)


@dataclass
class ResponseMetadata(MusicArenaDataClass):
    system_key: Optional[SystemKey] = None
    system_git_hash: Optional[str] = None
    system_time_queued: Optional[float] = None
    system_time_started: Optional[float] = None
    system_time_completed: Optional[float] = None
    gateway_time_started: Optional[float] = None
    gateway_time_completed: Optional[float] = None
    gateway_num_retries: Optional[int] = None
    size_bytes: Optional[int] = None
    lyrics: Optional[str] = None
    sample_rate: Optional[int] = None
    num_channels: Optional[int] = None
    duration: Optional[float] = None
    checksum: Optional[str] = None

    def __post_init__(self):
        if (
            self.system_git_hash is None
            and EXECUTING_IN_CONTAINER
            and CONTAINER_COMPONENT == "system"
            and CONTAINER_HOST_GIT_HASH is not None
        ):
            self.system_git_hash = CONTAINER_HOST_GIT_HASH

    def anonymize(self) -> "ResponseMetadata":
        return ResponseMetadata(
            lyrics=self.lyrics,
            checksum=self.checksum,
        )

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ResponseMetadata":
        if d.get("system_key") is not None:
            d["system_key"] = SystemKey.from_json_dict(d["system_key"])
        return cls.from_dict(d)


@dataclass
class Battle(MusicArenaDataClass):
    uuid: Optional[str] = None
    gateway_git_hash: Optional[str] = None
    prompt: Optional[SimpleTextToMusicPrompt] = None
    prompt_detailed: Optional[DetailedTextToMusicPrompt] = None
    prompt_user: Optional[User] = None
    prompt_session: Optional[Session] = None
    prompt_prebaked: bool = False
    prompt_routed: bool = False
    a_audio_url: Optional[str] = None
    a_metadata: Optional[ResponseMetadata] = None
    b_audio_url: Optional[str] = None
    b_metadata: Optional[ResponseMetadata] = None
    vote: Optional[Vote] = None
    vote_user: Optional[User] = None
    vote_session: Optional[Session] = None
    timings: list[tuple[str, float]] = field(default_factory=list)

    def __post_init__(self):
        if self.uuid is None:
            self.uuid = create_uuid()
        if (
            self.gateway_git_hash is None
            and EXECUTING_IN_CONTAINER
            and CONTAINER_COMPONENT == "gateway"
            and CONTAINER_HOST_GIT_HASH is not None
        ):
            self.gateway_git_hash = CONTAINER_HOST_GIT_HASH

    def anonymize(self) -> "Battle":
        """Returns a copy w/ system tags set to none"""
        return self.copy(
            a_metadata=self.a_metadata.anonymize() if self.a_metadata else None,
            b_metadata=self.b_metadata.anonymize() if self.b_metadata else None,
            timings=[],
        )

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Battle":
        if d.get("prompt") is not None:
            d["prompt"] = SimpleTextToMusicPrompt.from_json_dict(d["prompt"])
        if d.get("prompt_detailed") is not None:
            d["prompt_detailed"] = DetailedTextToMusicPrompt.from_json_dict(
                d["prompt_detailed"]
            )
        if d.get("prompt_user") is not None:
            d["prompt_user"] = User.from_json_dict(d["prompt_user"])
        if d.get("prompt_session") is not None:
            d["prompt_session"] = Session.from_json_dict(d["prompt_session"])
        if d.get("a_metadata") is not None:
            d["a_metadata"] = ResponseMetadata.from_json_dict(d["a_metadata"])
        if d.get("b_metadata") is not None:
            d["b_metadata"] = ResponseMetadata.from_json_dict(d["b_metadata"])
        if d.get("vote") is not None:
            d["vote"] = Vote.from_json_dict(d["vote"])
        if d.get("vote_user") is not None:
            d["vote_user"] = User.from_json_dict(d["vote_user"])
        if d.get("vote_session") is not None:
            d["vote_session"] = Session.from_json_dict(d["vote_session"])
        if "timings" in d:
            d["timings"] = [(e, t) for e, t in d["timings"]]
        return cls.from_dict(d)
