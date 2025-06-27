import pathlib

from .env import CACHE_DIR_VAR, EXECUTING_IN_CONTAINER

# Host paths
LIB_DIR = pathlib.Path(__file__).parent
REPO_DIR = LIB_DIR.parent
COMPONENTS_DIR = REPO_DIR / "components"
SYSTEMS_DIR = REPO_DIR / "systems"
if CACHE_DIR_VAR is not None:
    CACHE_DIR = pathlib.Path(CACHE_DIR_VAR)
else:
    CACHE_DIR = pathlib.Path.home() / ".cache" / "music_arena"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
IO_DIR = REPO_DIR / "io"
IO_DIR.mkdir(parents=True, exist_ok=True)

# Container paths
CONTAINER_REPO_DIR = pathlib.Path("/music-arena")
CONTAINER_LIB_DIR = CONTAINER_REPO_DIR / "music_arena"
CONTAINER_COMPONENTS_DIR = CONTAINER_REPO_DIR / "components"
CONTAINER_SYSTEMS_DIR = CONTAINER_REPO_DIR / "systems"
CONTAINER_CACHE_DIR = CONTAINER_REPO_DIR / "cache"
CONTAINER_IO_DIR = CONTAINER_REPO_DIR / "io"

if EXECUTING_IN_CONTAINER:
    assert REPO_DIR == CONTAINER_REPO_DIR
    assert LIB_DIR == CONTAINER_LIB_DIR
    assert SYSTEMS_DIR == CONTAINER_SYSTEMS_DIR
    assert CACHE_DIR == CONTAINER_CACHE_DIR
    assert IO_DIR == CONTAINER_IO_DIR
