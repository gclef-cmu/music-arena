import asyncio
import base64
import itertools
import json
import logging
import random
import tempfile
import time
from typing import Optional

import aiohttp

from music_arena.audio import ffprobe_metadata
from music_arena.chat.route import route_prompt
from music_arena.dataclass import (
    Battle,
    DetailedTextToMusicPrompt,
    ResponseMetadata,
    SimpleTextToMusicPrompt,
)
from music_arena.docker import system_port
from music_arena.helper import checksum
from music_arena.registry import SystemKey, get_system_metadata


class BattleGenerator:
    def __init__(
        self,
        systems: list[SystemKey],
        weights: Optional[dict[tuple[SystemKey, SystemKey], float]] = None,
        *,
        base_url: Optional[str] = "http://localhost",
        ports: Optional[dict[SystemKey, int]] = None,
        route_config: Optional[str] = None,
        num_retries: int = 1,
    ):
        if len(systems) < 2:
            raise ValueError("No systems specified")
        if weights is None:
            weights = {(a, b): 1.0 for a, b in itertools.combinations(systems, 2)}
        if len(weights) == 0:
            raise ValueError("No weights specified")
        if any(w <= 0 for w in weights.values()):
            raise ValueError("Weights must be positive")
        for a, b in weights.keys():
            if a not in systems:
                raise ValueError(f"System {a} not found")
            if b not in systems:
                raise ValueError(f"System {b} not found")
            if a == b:
                raise ValueError("System cannot battle itself")
        self.systems = {k: get_system_metadata(k) for k in systems}
        norm = sum(weights.values())
        self.weights = {k: v / norm for k, v in weights.items()}
        self.base_url = base_url
        self.ports = {} if ports is None else ports
        self.route_config = route_config
        self.num_retries = num_retries

    def get_systems(self) -> list[SystemKey]:
        return self.systems

    def get_system_url(self, system: SystemKey) -> str:
        return f"{self.base_url}:{self.ports.get(system, system_port(system))}"

    def sample_pair(
        self, prompt: DetailedTextToMusicPrompt
    ) -> tuple[SystemKey, SystemKey]:
        # TODO: This logic is only meant for our initial launch. Need to refine down the road.
        if prompt.instrumental:
            # Filter pairs to those where at most one system supports lyrics
            qualifying_pairs = []
            qualifying_weights = []
            for pair, weight in self.weights.items():
                system_a, system_b = pair
                total_supporting_lyrics = int(
                    self.systems[system_a].supports_lyrics
                ) + int(self.systems[system_b].supports_lyrics)
                if total_supporting_lyrics <= 1:
                    qualifying_pairs.append(pair)
                    qualifying_weights.append(weight)
        else:
            # Filter pairs to only those where both systems support lyrics
            qualifying_pairs = []
            qualifying_weights = []
            for pair, weight in self.weights.items():
                system_a, system_b = pair
                if (
                    self.systems[system_a].supports_lyrics
                    and self.systems[system_b].supports_lyrics
                ):
                    qualifying_pairs.append(pair)
                    qualifying_weights.append(weight)

        if not qualifying_pairs:
            raise ValueError("No system pairs available")

        # Sample one pair from qualifying pairs
        pair = random.choices(qualifying_pairs, weights=qualifying_weights, k=1)[0]

        # Randomly order the two systems in the pair
        result = list(pair)
        random.shuffle(result)
        return tuple(result)

    async def generate_audio(
        self,
        system: SystemKey,
        prompt: DetailedTextToMusicPrompt,
        *,
        logger: Optional[logging.Logger] = None,
        timings: Optional[list[tuple[str, float]]] = None,
    ) -> tuple[bytes, ResponseMetadata]:
        """Generate audio by calling the system health and generate endpoints with retry logic"""
        if timings is None:
            timings = []
        if logger is None:
            logger = logging.getLogger(__name__)

        url = self.get_system_url(system)
        health_url = f"{url}/health"
        generate_url = f"{url}/generate"

        # Health check first
        timings.append((f"health_check_{system.as_string()}_start", time.time()))
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"System {system.as_string()} health check failed with status {response.status}: {error_text}"
                        )
        except Exception as e:
            raise RuntimeError(f"System {system.as_string()} health check failed: {e}")
        timings.append((f"health_check_{system.as_string()}_end", time.time()))

        # Prepare the prompt data
        prompt_data = prompt.as_json_dict()

        # Try generation with retries
        timings.append((f"generate_{system.as_string()}_start", time.time()))
        last_exception = None
        start_time = time.time()
        for attempt in range(1 + self.num_retries):
            try:
                # Make HTTP request to the system container
                async with aiohttp.ClientSession() as session:
                    async with session.post(generate_url, json=prompt_data) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise RuntimeError(
                                f"System {system.as_string()} returned status {response.status}: {error_text}"
                            )
                        result = await response.json()
                end_time = time.time()

                # Parse response - the system-serve.py returns a JSON dict with audio data and metadata
                # Extract audio bytes (base64 encoded)
                audio_b64 = result.get("audio_b64")
                if not audio_b64:
                    raise RuntimeError(
                        f"System {system.as_string()} did not return audio_b64"
                    )
                audio_bytes = base64.b64decode(audio_b64)

                # Create response metadata
                # ffprobe_metadata requires a file path, so write to temp file
                with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
                    with open(temp_file.name, "wb") as f:
                        f.write(audio_bytes)
                    audio_metadata = ffprobe_metadata(temp_file.name)

                metadata = ResponseMetadata(
                    system_key=system,
                    system_git_hash=result.get("git_hash"),
                    system_time_queued=result.get("time_queued"),
                    system_time_started=result.get("time_started"),
                    system_time_completed=result.get("time_completed"),
                    gateway_time_started=start_time,
                    gateway_time_completed=end_time,
                    gateway_num_retries=attempt,
                    size_bytes=len(audio_bytes),
                    lyrics=result.get("lyrics"),
                    **audio_metadata,
                    checksum=checksum(audio_bytes),
                )
                logger.info(f"audio_metadata=\n{json.dumps(audio_metadata, indent=2)}")

                timings.append((f"generate_{system.as_string()}_end", time.time()))
                return (audio_bytes, metadata)

            except Exception as e:
                last_exception = e
                if attempt < self.num_retries:
                    continue
                else:
                    break

        # All retries failed
        timings.append((f"generate_{system.as_string()}_failed", time.time()))
        raise RuntimeError(
            f"System {system.as_string()} generation failed after {1 + self.num_retries} attempts. Last error: {last_exception}"
        )

    async def generate_battle(
        self,
        prompt: Optional[SimpleTextToMusicPrompt] = None,
        prompt_detailed: Optional[DetailedTextToMusicPrompt] = None,
        *,
        timings: Optional[list[tuple[str, float]]] = None,
        logger: Optional[logging.Logger] = None,
        **battle_kwargs,
    ) -> tuple[Battle, bytes, bytes]:
        if prompt_detailed is None and prompt is None:
            raise ValueError("Either prompt_detailed or prompt must be provided")

        if timings is None:
            timings = []
        if logger is None:
            logger = logging.getLogger(__name__)

        # Route prompt
        timings.append(("route", time.time()))
        if prompt_detailed is None:
            prompt_detailed = await route_prompt(prompt, config=self.route_config)
            logger.info(f"prompt_routed={prompt_detailed}")
        assert prompt_detailed is not None

        # Sample pair
        timings.append(("sample_pair", time.time()))
        a_system, b_system = self.sample_pair(prompt_detailed)
        logger.info(f"sampled_pair={a_system} vs {b_system}")

        # Generate audio for both systems in parallel
        timings.append(("generate_parallel_start", time.time()))
        (a_audio_bytes, a_metadata), (b_audio_bytes, b_metadata) = await asyncio.gather(
            self.generate_audio(a_system, prompt_detailed, timings=timings),
            self.generate_audio(b_system, prompt_detailed, timings=timings),
        )
        timings.append(("generate_parallel_end", time.time()))

        # Create the Battle object
        timings.append(("create_battle_obj", time.time()))
        battle = Battle(
            prompt=prompt,
            prompt_detailed=prompt_detailed,
            prompt_routed=True,
            a_metadata=a_metadata,
            b_metadata=b_metadata,
            timings=timings,
            **battle_kwargs,
        )
        logger.info(f"battle_created={battle.uuid}")
        logger.info(f"battle=\n{json.dumps(battle.as_json_dict(), indent=2)}")

        return (battle, a_audio_bytes, b_audio_bytes)
