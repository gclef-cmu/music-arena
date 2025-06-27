import logging
import os
from typing import Any, Optional

import requests

from music_arena.dataclass import (
    Battle,
    DetailedTextToMusicPrompt,
    Session,
    SimpleTextToMusicPrompt,
    SystemKey,
    TextToMusicSystemMetadata,
    User,
    Vote,
)
from music_arena.exceptions import (
    PromptContentException,
    RateLimitException,
    SystemTimeoutException,
)
from music_arena.registry import get_system_metadata

from . import constants as C

URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
_LOGGER = logging.getLogger(__name__)


class GatewayException(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _get_json(route: str, timeout: float) -> dict[str, Any]:
    try:
        response = requests.get(f"{URL}/{route}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise SystemTimeoutException()
    except requests.exceptions.HTTPError as e:
        _LOGGER.error(f"HTTP error getting {route}: {e}")
        raise GatewayException(e.response.text, e.response.status_code) from e
    except Exception as e:
        _LOGGER.error(f"Error getting {route}: {e}")
        raise GatewayException(str(e)) from e


def _post_json(route: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        response = requests.post(f"{URL}/{route}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        _LOGGER.error(f"HTTP error posting {route}: {e}")

        # Try to parse error response as JSON to extract detail
        error_message = e.response.text
        try:
            error_json = e.response.json()
            if "detail" in error_json:
                error_message = error_json["detail"]
        except (ValueError, KeyError):
            # If JSON parsing fails or no detail field, use original text
            pass

        if e.response.status_code == 406:
            raise PromptContentException(error_message) from e
        elif e.response.status_code == 429:
            raise RateLimitException(error_message) from e
        else:
            raise GatewayException(error_message, e.response.status_code) from e
    except Exception as e:
        _LOGGER.error(f"Error posting {route}: {e}")
        raise GatewayException(str(e)) from e


def get_systems() -> dict[str, TextToMusicSystemMetadata]:
    """GET active systems from API gateway"""
    system_key_dicts = _get_json("systems", timeout=C.GATEWAY_GET_TIMEOUT)
    known_systems = {}
    for k_dict in system_key_dicts:
        try:
            k = SystemKey.from_json_dict(k_dict)
            system_metadata = get_system_metadata(k)
            known_systems[k] = system_metadata
        except ValueError:
            _LOGGER.warning(f"Unknown system reported by backend: {k_dict}")
    return known_systems


def get_prebaked_prompts() -> dict[str, DetailedTextToMusicPrompt]:
    """GET prebaked prompts from API gateway"""
    prebaked_prompts = _get_json("prebaked", timeout=C.GATEWAY_GET_TIMEOUT)
    return {
        k: DetailedTextToMusicPrompt.from_json_dict(v)
        for k, v in prebaked_prompts.items()
    }


def post_generate_battle(
    session: Session,
    user: User,
    prompt: Optional[SimpleTextToMusicPrompt] = None,
    detailed_prompt: Optional[DetailedTextToMusicPrompt] = None,
) -> Battle:
    """POST audio pair generation request to API gateway"""
    assert session.ack_tos == C.TERMS_CHECKSUM
    payload = {
        "session": session.as_json_dict(),
        "user": user.as_json_dict(),
        "prompt": prompt.as_json_dict() if prompt is not None else None,
        "prompt_detailed": (
            detailed_prompt.as_json_dict() if detailed_prompt is not None else None
        ),
    }
    result = _post_json("generate_battle", payload, timeout=C.GATEWAY_GENERATE_TIMEOUT)
    return Battle.from_json_dict(result)


def post_record_vote(
    session: Session, user: User, battle_uuid: str, vote: Vote
) -> dict[str, Any]:
    """POST user vote data to API gateway"""
    assert session.ack_tos == C.TERMS_CHECKSUM
    payload = {
        "session": session.as_json_dict(),
        "user": user.as_json_dict(),
        "battle_uuid": battle_uuid,
        "vote": vote.as_json_dict(),
    }
    return _post_json("record_vote", payload, timeout=C.GATEWAY_VOTE_TIMEOUT)
