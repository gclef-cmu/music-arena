import functools
import io
import json
import logging
import pathlib
import random
import time
from typing import Optional

import fastapi
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles

from music_arena.dataclass import (
    Battle,
    DetailedTextToMusicPrompt,
    Preference,
    Session,
    SimpleTextToMusicPrompt,
    SystemKey,
    User,
    Vote,
)
from music_arena.exceptions import PromptContentException
from music_arena.helper import create_uuid
from music_arena.logging import get_battle_logger
from music_arena.path import CONTAINER_IO_DIR
from music_arena.secret import get_secret_json

from .battle import BattleGenerator
from .bucket import BucketBase, GCPBucket, LocalBucket

# Global state
_LOGGER = logging.getLogger(__name__)
_LIB_DIR = pathlib.Path(__file__).parent
_COMPONENT_DIR = _LIB_DIR.parent
_STATIC_DIR = CONTAINER_IO_DIR / "gateway"
_APP = fastapi.FastAPI()
_APP.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
_BATTLES = {}
_BATTLE_GENERATOR: Optional[BattleGenerator] = None
_BUCKET_METADATA: Optional[BucketBase] = None
_BUCKET_AUDIO: Optional[BucketBase] = None
_FLAKINESS = 0.0


def _maybe_raise_flaky_error(logger):
    if random.random() < _FLAKINESS:
        logger.warning("Flaky error!")
        raise HTTPException(status_code=500, detail="Flaky error!")


def _parse_musicarena_type(data: dict, key: str, type: type, required: list[str] = []):
    try:
        result = type.from_json_dict(data[key])
    except KeyError:
        raise HTTPException(status_code=400, detail=f"{key} is required")
    except TypeError:
        raise HTTPException(status_code=400, detail=f"{key} data must be a dictionary")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid {key} data: {str(e)}")
    if any(getattr(result, attr) is None for attr in required):
        raise HTTPException(
            status_code=400, detail=f"{key} is missing required fields: {required}"
        )
    return result


def _update_battle(battle: Battle):
    assert _BUCKET_METADATA is not None
    global _BATTLES
    _BATTLES[battle.uuid] = battle
    _BUCKET_METADATA.put(
        f"{battle.uuid}.json",
        io.BytesIO(json.dumps(battle.as_json_dict(), indent=2).encode("utf-8")),
        allow_overwrite=True,
    )


@functools.lru_cache()
def _format_systems():
    assert _BATTLE_GENERATOR is not None
    return [system.as_json_dict() for system in _BATTLE_GENERATOR.get_systems().keys()]


@_APP.get("/systems")
def systems():
    """Returns list of System objects"""
    _maybe_raise_flaky_error(logging.getLogger("/systems"))
    return _format_systems()


@functools.lru_cache()
def _parse_prebaked_prompts():
    try:
        with open(_COMPONENT_DIR / "prebaked.json", "r") as f:
            prompts = [
                DetailedTextToMusicPrompt.from_json_dict(p) for p in json.load(f)
            ]
    except FileNotFoundError:
        _LOGGER.warning("prebaked.json not found, returning empty prebaked prompts")
        return {}
    result = {p.checksum: p for p in prompts}
    assert len(result) == len(prompts)
    return result


@_APP.get("/prebaked")
def prebaked():
    """Returns dictionary mapping checksum to TextToMusicPrompt dict"""
    _maybe_raise_flaky_error(logging.getLogger("/prebaked"))
    return {k: v.as_json_dict() for k, v in _parse_prebaked_prompts().items()}


def _audio_key(prompt: DetailedTextToMusicPrompt, battle_uuid: str, suffix: str) -> str:
    prebaked = prompt.checksum in _parse_prebaked_prompts()
    prefix = "prebaked" if prebaked else "original"
    return f"{prefix}-{prompt.checksum}-{battle_uuid}-{suffix}.mp3"


@_APP.get("/health_check")
async def health_check():
    """Health check"""
    assert _BATTLE_GENERATOR is not None
    assert _BUCKET_AUDIO is not None
    prebaked_prompts = _parse_prebaked_prompts()
    prompt_detailed = random.choice(list(prebaked_prompts.values()))

    # Generate battle
    timings = []
    timings.append(("generate", time.time()))
    battle, a_audio_bytes, b_audio_bytes = await _BATTLE_GENERATOR.generate_battle(
        prompt_detailed=prompt_detailed, prompt_prebaked=True, timings=timings
    )

    # Store audio
    timings.append(("upload_audio", time.time()))
    a_audio_key = _audio_key(prompt_detailed, battle.uuid, "a")
    b_audio_key = _audio_key(prompt_detailed, battle.uuid, "b")
    try:
        _BUCKET_AUDIO.put(a_audio_key, io.BytesIO(a_audio_bytes))
        _BUCKET_AUDIO.put(b_audio_key, io.BytesIO(b_audio_bytes))
        battle.a_audio_url = _BUCKET_AUDIO.get_public_url(a_audio_key)
        battle.b_audio_url = _BUCKET_AUDIO.get_public_url(b_audio_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading audio: {e}")

    # Store battle
    timings.append(("upload_metadata", time.time()))
    battle.timings = sorted(timings, key=lambda x: x[1])
    try:
        _update_battle(battle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading battle: {e}")

    return {"status": "ok", "uuid": battle.uuid}


@_APP.post("/generate_battle")
async def generate_battle(data: dict):
    """Generate a battle"""
    assert _BATTLE_GENERATOR is not None
    assert _BUCKET_AUDIO is not None

    # Parse user and prompt
    timings = []
    timings.append(("parse", time.time()))
    session = _parse_musicarena_type(
        data,
        "session",
        Session,
        required=["uuid", "create_time", "frontend_git_hash", "ack_tos"],
    )
    user = _parse_musicarena_type(data, "user", User)
    if data.get("prompt_detailed") is not None:
        prompt = None
        prompt_detailed = _parse_musicarena_type(
            data, "prompt_detailed", DetailedTextToMusicPrompt
        )
        prompt_prebaked = prompt_detailed.checksum in _parse_prebaked_prompts()
    else:
        prompt = _parse_musicarena_type(data, "prompt", SimpleTextToMusicPrompt)
        prompt_detailed = None
        prompt_prebaked = False
    battle_uuid = create_uuid()
    logger = get_battle_logger(
        "/generate_battle", session=session, user=user, battle=battle_uuid
    )
    if user.salted_ip is None and user.salted_fingerprint is None:
        logger.warning("User has no tracking information")

    # Flake out
    _maybe_raise_flaky_error(logger)

    # Generate audio
    logger.info(
        f"prompt={prompt},"
        f"prompt_detailed={prompt_detailed},"
        f"prompt_prebaked={prompt_prebaked},"
    )

    # TODO: handle prebaked audio!

    # Generate battle
    timings.append(("generate", time.time()))
    try:
        battle, a_audio_bytes, b_audio_bytes = await _BATTLE_GENERATOR.generate_battle(
            prompt=prompt,
            prompt_detailed=prompt_detailed,
            timings=timings,
            logger=logger,
            uuid=battle_uuid,
            prompt_user=user,
            prompt_session=session,
            prompt_prebaked=prompt_prebaked,
        )
    except PromptContentException as e:
        raise HTTPException(status_code=406, detail=e.rationale)
    logger.info(
        f"a_system_key={battle.a_metadata.system_key.as_string()}, "
        f"a_audio_size={battle.a_metadata.size_bytes / 1024 / 1024:.2f} MB, "
        f"b_system_key={battle.b_metadata.system_key.as_string()}, "
        f"b_audio_size={battle.b_metadata.size_bytes / 1024 / 1024:.2f} MB"
    )

    # Store audio
    timings.append(("upload_audio", time.time()))
    a_audio_key = _audio_key(battle.prompt_detailed, battle.uuid, "a")
    b_audio_key = _audio_key(battle.prompt_detailed, battle.uuid, "b")
    try:
        _BUCKET_AUDIO.put(a_audio_key, io.BytesIO(a_audio_bytes))
        _BUCKET_AUDIO.put(b_audio_key, io.BytesIO(b_audio_bytes))
        battle.a_audio_url = _BUCKET_AUDIO.get_public_url(a_audio_key)
        battle.b_audio_url = _BUCKET_AUDIO.get_public_url(b_audio_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading audio: {e}")

    # Store battle
    timings.append(("upload_metadata", time.time()))
    battle.timings = sorted(timings, key=lambda x: x[1])
    try:
        _update_battle(battle)
    except Exception as e:
        logging.error(f"Error updating battle: {e}")

    timings.append(("anonymizing", time.time()))
    return battle.anonymize().as_json_dict()


@_APP.post("/record_vote")
def record_vote(data: dict):
    """Record vote for a given battle"""
    # Parse user and vote
    session = _parse_musicarena_type(
        data,
        "session",
        Session,
        required=["uuid", "create_time", "frontend_git_hash", "ack_tos"],
    )
    user = _parse_musicarena_type(data, "user", User)
    battle_uuid = data.get("battle_uuid")
    if battle_uuid is None:
        raise HTTPException(status_code=400, detail="battle_uuid is required")
    vote = _parse_musicarena_type(
        data, "vote", Vote, required=["preference", "preference_time"]
    )
    logger = get_battle_logger(
        "/record_vote", session=session, user=user, battle=battle_uuid
    )
    if user.salted_ip is None and user.salted_fingerprint is None:
        logger.warning("User has no tracking information")

    # Flake out if needed
    _maybe_raise_flaky_error(logger)

    # Get battle
    global _BATTLES
    battle = _BATTLES.get(battle_uuid)
    if battle is None:
        try:
            battle = _BUCKET_METADATA.get(f"{battle_uuid}.json")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Battle not found: {e}")
    assert battle is not None
    timings = battle.timings

    # Update battle with vote
    timings.append(("vote", time.time()))
    if user.checksum != battle.prompt_user.checksum:
        logger.warning(
            f"Vote user {user.checksum} does not match prompt user {battle.prompt_user.checksum}"
        )
    if session.uuid != battle.prompt_session.uuid:
        logger.warning(
            f"Vote session {session.uuid} does not match prompt session {battle.prompt_session.uuid}"
        )
    if battle.vote is not None:
        logger.warning(f"Battle {battle.uuid} already has a vote!")
    battle.vote = vote
    battle.vote_user = user
    battle.vote_session = session
    try:
        _update_battle(battle)
    except Exception as e:
        logging.error(f"Error updating battle: {e}")

    # Determine winner
    if vote.preference == Preference.A:
        winner = battle.a_metadata.system_key.as_json_dict()
    elif vote.preference == Preference.B:
        winner = battle.b_metadata.system_key.as_json_dict()
    else:
        winner = None

    return {
        "winner": winner,
        "a_metadata": battle.a_metadata.as_json_dict(),
        "b_metadata": battle.b_metadata.as_json_dict(),
    }


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", type=str, required=True)
    parser.add_argument("--system_ports", type=str)
    parser.add_argument("--weights", type=str)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--public_base_url", type=str)
    parser.add_argument(
        "--systems_base_url", type=str, default="http://host.docker.internal"
    )
    parser.add_argument("--bucket_metadata", type=str)
    parser.add_argument("--bucket_audio", type=str)
    parser.add_argument("--route_config", type=str, default="4o-v00")
    parser.add_argument("--flakiness", type=float, default=0.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    _LOGGER.info(f"Args: {args}")

    # Parse system
    systems = []
    system_ports = {}
    for system in args.systems.split(","):
        if len(system.strip()) == 0:
            continue
        system_parts = system.strip().split(":")
        if len(system_parts) < 2:
            raise ValueError(f"Invalid system: {system}")
        system_key = SystemKey(system_tag=system_parts[0], variant_tag=system_parts[1])
        systems.append(system_key)
        if len(system_parts) == 3:
            system_ports[system_key] = int(system_parts[2])
        elif len(system_parts) > 3:
            raise ValueError(f"Invalid system: {system}")
    _LOGGER.info(f"Systems: {systems}")
    _LOGGER.info(f"System ports: {system_ports}")

    # Parse weights
    weights = None
    if args.weights is not None:
        weights = {}
        for spec in args.weights.split(","):
            a, b, w = spec.strip().split("/")
            a = SystemKey.from_string(a)
            b = SystemKey.from_string(b)
            weights[(a, b)] = float(w)
        _LOGGER.info(f"Weights: {weights}")

    # Set up battle generator
    global _BATTLE_GENERATOR
    _BATTLE_GENERATOR = BattleGenerator(
        systems,
        weights,
        ports=system_ports,
        route_config=args.route_config,
        base_url=args.systems_base_url,
    )

    # Set up buckets
    global _BUCKET_METADATA, _BUCKET_AUDIO
    if args.bucket_metadata is None:
        metadata_dir = _STATIC_DIR / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        _BUCKET_METADATA = LocalBucket(
            metadata_dir,
            public_url=(
                None
                if args.public_base_url is None
                else f"{args.public_base_url}/static/metadata"
            ),
        )
    else:
        _BUCKET_METADATA = GCPBucket(
            args.bucket_metadata,
            credentials=get_secret_json("GCP_BUCKET_SERVICE_ACCOUNT"),
            signed_urls=True,
        )
    if args.bucket_audio is None:
        audio_dir = _STATIC_DIR / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        _BUCKET_AUDIO = LocalBucket(
            audio_dir,
            public_url=(
                None
                if args.public_base_url is None
                else f"{args.public_base_url}/static/audio"
            ),
        )
    else:
        _BUCKET_AUDIO = GCPBucket(
            args.bucket_audio,
            credentials=get_secret_json("GCP_BUCKET_SERVICE_ACCOUNT"),
            signed_urls=True,
        )

    # Set up flakiness
    global _FLAKINESS
    _FLAKINESS = args.flakiness

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(_APP, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
