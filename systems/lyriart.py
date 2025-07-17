import asyncio
import base64
import logging
import time
from io import BytesIO
from typing import Any, Dict, Optional

import nest_asyncio
import numpy as np
from google import genai
from google.genai import types

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.secret import get_secret
from music_arena.system import TextToMusicAPISystem

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

_LOGGER = logging.getLogger(__name__)


class LyriaRealTime(TextToMusicAPISystem):
    def __init__(
        self,
        *args,
        model_name: str = "models/lyria-realtime-exp",
        default_duration: float = 20.0,
        max_duration: float = 120.0,
        sample_rate: int = 48000,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._model_name = model_name
        self._default_duration = default_duration
        self._max_duration = max_duration
        self._sample_rate = sample_rate
        self._client: Optional[genai.Client] = None

    def _prepare(self):
        """Initialize the Google GenAI client"""
        api_key = get_secret("GEMINI_API_KEY")
        self._client = genai.Client(
            api_key=api_key, http_options={"api_version": "v1alpha"}
        )

    def _release(self):
        """Clean up the client"""
        if self._client:
            del self._client
            self._client = None

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        """Check if the prompt is supported by Lyria RealTime"""
        if not prompt.instrumental:
            return PromptSupport.UNSUPPORTED
        if prompt.duration is not None and prompt.duration > self._max_duration:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        """Generate a single music response using Lyria RealTime"""
        assert self._client is not None
        timings = []

        # Extract duration
        duration = prompt.duration or self._default_duration
        if duration > self._max_duration:
            duration = self._max_duration

        # Prepare the prompt for Lyria
        music_prompt = prompt.overall_prompt

        # Prepare the seed
        seed = seed % 2147483647  # Ensure seed fits in int32

        _LOGGER.info(
            f"Generating music with Lyria RealTime: {music_prompt}, duration: {duration}, seed: {seed}"
        )

        # Start generation timing
        start_time = time.time()
        timings.append(("start", start_time))

        # Collect audio chunks
        audio_chunks = []
        collected_duration = 0.0
        chunk_duration = 2.0  # 2 second chunks
        num_chunks = np.ceil(duration / chunk_duration)

        async def collect_audio(session):
            """Collect audio chunks until we reach the desired duration"""
            nonlocal collected_duration, audio_chunks

            async for message in session.receive():
                if message.server_content and message.server_content.audio_chunks:
                    # Extract audio data from the chunk
                    chunk = message.server_content.audio_chunks[0]
                    _LOGGER.info(
                        f"Received chunk: {chunk.mime_type}, {len(chunk.data)} bytes"
                    )

                    # Handle L16 (Linear PCM 16-bit) format
                    if chunk.mime_type.startswith("audio/l16"):
                        # L16 is raw 16-bit PCM, try little-endian first
                        audio_array = np.frombuffer(
                            chunk.data, dtype="<i2"
                        )  # little-endian 16-bit

                        # Convert to float32 and normalize
                        audio_float = audio_array.astype(np.float32) / 32768.0

                        # Reshape to stereo (assuming 2 channels)
                        if len(audio_float) % 2 == 0:
                            audio_float = audio_float.reshape(-1, 2)
                        else:
                            # If odd number of samples, pad or truncate
                            audio_float = audio_float[:-1].reshape(-1, 2)

                        # Parse sample rate from mime type (default to 48000)
                        sample_rate = self._sample_rate
                        if "rate=" in chunk.mime_type:
                            try:
                                rate_part = chunk.mime_type.split("rate=")[1].split(
                                    ";"
                                )[0]
                                sample_rate = int(rate_part)
                            except (IndexError, ValueError):
                                pass

                        audio_chunks.append(audio_float)
                        collected_duration += len(audio_float) / sample_rate

                        _LOGGER.info(
                            f"Collected {len(audio_chunks)} chunks, duration: {collected_duration:.2f}s, samples: {len(audio_float)}"
                        )
                    else:
                        raise NotImplementedError(
                            f"Unsupported audio format: {chunk.mime_type}"
                        )

                    # Stop collecting when we have enough audio
                    if len(audio_chunks) >= num_chunks:
                        break

                await asyncio.sleep(0.001)

        # Connect to Lyria RealTime and generate music
        async with self._client.aio.live.music.connect(
            model=self._model_name
        ) as session:
            # Start the audio collection task (like in the official example)
            audio_task = asyncio.create_task(collect_audio(session))

            # Configure the session (setup is handled internally)
            await session.set_weighted_prompts(
                prompts=[
                    types.WeightedPrompt(text=music_prompt, weight=1.0),
                ]
            )

            # Set generation config with seed
            await session.set_music_generation_config(
                config=types.LiveMusicGenerationConfig(
                    temperature=1.0,
                    seed=seed,
                )
            )

            # Start streaming music
            await session.play()

            # Wait for audio collection to complete
            await asyncio.wait_for(audio_task, timeout=duration + 10.0)

        timings.append(("generation_complete", time.time()))

        # Concatenate all audio chunks
        if audio_chunks:
            concatenated_audio = np.concatenate(audio_chunks, axis=0)
        else:
            # Fallback to silence if no audio was generated
            num_samples = int(duration * self._sample_rate)
            concatenated_audio = np.zeros((num_samples, 2), dtype=np.float32)

        # Convert to Audio object
        audio = Audio(samples=concatenated_audio, sample_rate=self._sample_rate)

        # Crop to exact requested duration
        if prompt.duration is not None:
            audio = audio.crop(duration=duration)

        timings.append(("done", time.time()))

        return TextToMusicResponse(
            audio=audio,
            custom_timings=timings,
        )
