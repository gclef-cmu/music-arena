import hashlib
import pathlib
import uuid
from typing import Literal


def create_uuid() -> str:
    return str(uuid.uuid4())


def checksum(b: bytes | str | pathlib.Path, strategy: Literal["md5"] = "md5") -> str:
    if strategy == "md5":
        hasher = hashlib.md5()
    else:
        raise ValueError(f"Invalid hash strategy: {strategy}")

    if isinstance(b, pathlib.Path):
        with b.open("rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
    else:
        if isinstance(b, str):
            b = b.encode()
        hasher.update(b)
    return hasher.hexdigest()


def salted_checksum(s: str, salt: str, strategy: Literal["md5"] = "md5") -> str:
    return checksum(f"{s}{salt}", strategy=strategy)
