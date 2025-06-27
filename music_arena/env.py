import os
import subprocess

from .dataclass.system_metadata import SystemKey

EXECUTING_IN_CONTAINER = os.getenv("MUSIC_ARENA_EXECUTING_IN_CONTAINER") is not None
CONTAINER_HOST_GIT_HASH = os.getenv("MUSIC_ARENA_CONTAINER_HOST_GIT_HASH")
CONTAINER_COMPONENT = os.getenv("MUSIC_ARENA_CONTAINER_COMPONENT")
CONTAINER_SYSTEM_TAG = os.getenv("MUSIC_ARENA_CONTAINER_SYSTEM_TAG")
CONTAINER_VARIANT_TAG = os.getenv("MUSIC_ARENA_CONTAINER_VARIANT_TAG")
if CONTAINER_SYSTEM_TAG is not None and CONTAINER_VARIANT_TAG is not None:
    CONTAINER_SYSTEM_KEY = SystemKey(
        system_tag=CONTAINER_SYSTEM_TAG, variant_tag=CONTAINER_VARIANT_TAG
    )
else:
    CONTAINER_SYSTEM_KEY = None
CACHE_DIR_VAR = os.getenv("MUSIC_ARENA_CACHE_DIR")


def get_git_commit_hash() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()


def get_git_porcelain_status() -> bool:
    return (
        subprocess.check_output(["git", "status", "--porcelain"])
        .decode("utf-8")
        .strip()
        == ""
    )


def get_git_summary() -> str:
    return (
        f"{get_git_commit_hash()}:{'clean' if get_git_porcelain_status() else 'dirty'}"
    )


def check_gpu_memory_gb(device_id: int = 0) -> dict[str, float]:
    output = (
        subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.free,memory.total",
                "--format=csv,noheader,nounits",
                f"--id={device_id}",
            ]
        )
        .decode("utf-8")
        .strip()
    )

    # Output format is like "7549, 1234, 8783" (used, free, total in MiB)
    used, free, total = map(lambda x: round(int(x) / 1024, 2), output.split(", "))

    return {"used": used, "available": free, "total": total}
