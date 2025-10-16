import functools
import json
import os
import secrets

from .path import CACHE_DIR

SECRET_VAR_PREFIX = "MUSIC_ARENA_SECRET_"
_SECRETS_DIR = CACHE_DIR / "secrets"
_SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def get_secret_var_name(tag: str) -> str:
    return f"{SECRET_VAR_PREFIX}{tag.upper()}"


@functools.lru_cache(maxsize=None)
def get_secret_json(tag: str) -> dict:
    secrets_path = _SECRETS_DIR / f"{tag}.json"
    if secrets_path.exists():
        secret = json.load(secrets_path.open())
    else:
        # Prompt user to enter secret
        json_path = input(f"Enter JSON path for tag {tag}: ").strip()
        if not json_path:
            raise ValueError(f"JSON path for tag {tag} not found")
        secret = json.load(open(json_path))
    if not secrets_path.exists():
        secrets_path.write_text(json.dumps(secret, indent=2))
    return secret


@functools.lru_cache(maxsize=None)
def get_secret(tag: str, randomly_initialize: bool = False) -> str:
    tag_with_prefix = get_secret_var_name(tag)
    secrets_path = _SECRETS_DIR / f"{tag}.txt"
    if tag_with_prefix in os.environ:
        # Grab from environment override if defined
        secret = os.environ[tag_with_prefix]
    elif secrets_path.exists():
        # Grab from cache if previously set
        secret = secrets_path.read_text()
    else:
        # New secret
        if randomly_initialize:
            # Generate a cryptographically secure random secret
            secret = secrets.token_hex(32)
        else:
            # Prompt user to enter secret
            secret = input(f"Enter secret for tag {tag}: ").strip()
            if not secret:
                raise ValueError(f"Secret for tag {tag} not found")
    # Cache the secret
    if not secrets_path.exists():
        secrets_path.write_text(secret)
    return secret
