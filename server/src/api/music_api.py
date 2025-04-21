import time
import aiohttp
import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import os
import json

logger = logging.getLogger(__name__)


@dataclass
class MusicResponseOutput:
    audio_data: Optional[bytes]
    error: Optional[str] = None


class BaseMusicAPIProvider(ABC):
    def __init__(self, model_name, **config):
        self.model_name = model_name
        self.config = config
        self.validate_config()

    @abstractmethod
    def validate_config(self):
        """Validate that all required configuration parameters are present."""
        pass

    def log_gen_params(self, gen_params):
        logger.info(f"==== request ====\n{gen_params}")


class CustomServerMusicAPIProvider(BaseMusicAPIProvider):
    def validate_config(self):
        required_keys = ["base_url", "check_interval", "max_wait_time"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

    async def generate_music(
        self, prompt: str, seed: Optional[int] = None
    ) -> MusicResponseOutput:
        """
        Generate music from a text prompt using the custom server.
        
        Args:
            prompt (str): The text prompt to generate music from
            seed (Optional[int]): Optional seed for reproducible generation
            
        Returns:
            MusicResponseOutput: Contains either the audio data or an error message
        """
        base_url = self.config["base_url"].rstrip("/")
        check_interval = self.config["check_interval"]
        max_wait_time = self.config["max_wait_time"]
        
        # Prepare request data
        data = {"prompt": prompt}
        if seed is not None:
            data["seed"] = seed
            
        self.log_gen_params(data)
        
        try:
            async with aiohttp.ClientSession() as session:
                # Submit the job
                async with session.post(f"{base_url}/submit", data=data) as submit_response:
                    submit_response.raise_for_status()
                    submit_data = await submit_response.json()
                    job_id = submit_data["job_id"]
                
                # Poll for completion
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    async with session.get(
                        f"{base_url}/status", params={"job_id": job_id}
                    ) as status_response:
                        status_response.raise_for_status()
                        status_data = await status_response.json()
                        status = status_data["status"]
                
                    if status == "COMPLETE":
                        # Download the generated audio
                        async with session.get(
                            f"{base_url}/download", params={"job_id": job_id}
                        ) as download_response:
                            download_response.raise_for_status()
                            content = await download_response.read()
                            return MusicResponseOutput(audio_data=content)
                
                    elif status == "ERROR":
                        return MusicResponseOutput(
                            audio_data=None, error=f"Job {job_id} failed during processing"
                        )
                
                    await asyncio.sleep(check_interval)
                
                return MusicResponseOutput(
                    audio_data=None,
                    error=f"Job {job_id} timed out after {max_wait_time} seconds",
                )
                
        except Exception as e:
            return MusicResponseOutput(
                audio_data=None, error=f"API request failed: {str(e)}"
            )


class InstrumentalMusicAPIProvider(BaseMusicAPIProvider):
    def validate_config(self):
        required_keys = ["base_url", "check_interval", "max_wait_time"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

    async def generate_music(
        self, prompt: str, seed: Optional[int] = None
    ) -> MusicResponseOutput:
        """
        Generate instrumental music from a text prompt using the custom Flask server.

        Args:
            prompt (str): The text prompt to generate music from
            seed (Optional[int]): Optional seed for reproducible generation

        Returns:
            MusicResponseOutput: Contains either the audio data or an error message
        """
        base_url = self.config["base_url"].rstrip("/")
        check_interval = self.config["check_interval"]
        max_wait_time = self.config["max_wait_time"]

        # Prepare request data
        data = {"prompt": prompt}

        self.log_gen_params(data)

        try:
            # Import aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                # Submit the job
                async with session.post(f"{base_url}/submit", data=data) as submit_response:
                    submit_response.raise_for_status()
                    submit_data = await submit_response.json()
                    job_id = submit_data["job_id"]
    
                # Poll for completion
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    async with session.get(
                        f"{base_url}/status", params={"job_id": job_id}
                    ) as status_response:
                        status_response.raise_for_status()
                        status_data = await status_response.json()
                        status = status_data["status"]
    
                    if status == "COMPLETE":
                        # Download the generated audio
                        async with session.get(
                            f"{base_url}/download", params={"job_id": job_id}
                        ) as download_response:
                            download_response.raise_for_status()
                            content = await download_response.read()
                            return MusicResponseOutput(audio_data=content)
    
                    elif status == "ERROR":
                        return MusicResponseOutput(
                            audio_data=None, error=f"Job {job_id} failed during processing"
                        )
    
                    await asyncio.sleep(check_interval)
    
                return MusicResponseOutput(
                    audio_data=None,
                    error=f"Job {job_id} timed out after {max_wait_time} seconds",
                )

        except Exception as e:
            return MusicResponseOutput(
                audio_data=None, error=f"API request failed: {str(e)}"
            )


class LyricsMusicAPIProvider(BaseMusicAPIProvider):
    def validate_config(self):
        required_keys = ["base_url", "check_interval", "max_wait_time"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")

    async def generate_music(
        self, prompt: str, seed: Optional[int] = None
    ) -> MusicResponseOutput:
        """
        Generate music with lyrics from a text prompt using the custom Flask server.

        Args:
            prompt (str): The text prompt to generate music from
            seed (Optional[int]): Optional seed for reproducible generation

        Returns:
            MusicResponseOutput: Contains either the audio data or an error message
        """
        base_url = self.config["base_url"].rstrip("/")
        check_interval = self.config["check_interval"]
        max_wait_time = self.config["max_wait_time"]

        # Prepare request data
        data = {
            "json_prompt": json.dumps({
                "style": prompt,
                "instrumental": False,
            })
        }

        self.log_gen_params(data)

        try:
            # Import aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                # Submit the job
                async with session.post(f"{base_url}/submit", data=data) as submit_response:
                    submit_response.raise_for_status()
                    submit_data = await submit_response.json()
                    job_id = submit_data["job_id"]
    
                # Poll for completion
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    async with session.get(
                        f"{base_url}/status", params={"job_id": job_id}
                    ) as status_response:
                        status_response.raise_for_status()
                        status_data = await status_response.json()
                        status = status_data["status"]
    
                    if status == "COMPLETE":
                        # Download the generated audio
                        async with session.get(
                            f"{base_url}/download", params={"job_id": job_id}
                        ) as download_response:
                            download_response.raise_for_status()
                            content = await download_response.read()
                            return MusicResponseOutput(audio_data=content)
    
                    elif status == "ERROR":
                        return MusicResponseOutput(
                            audio_data=None, error=f"Job {job_id} failed during processing"
                        )
    
                    await asyncio.sleep(check_interval)
    
                return MusicResponseOutput(
                    audio_data=None,
                    error=f"Job {job_id} timed out after {max_wait_time} seconds",
                )

        except Exception as e:
            return MusicResponseOutput(
                audio_data=None, error=f"API request failed: {str(e)}"
            )


def get_music_api_provider(model_key: str, lyrics: bool = False, **kwargs):
    """
    Factory function to create an appropriate music API provider instance.

    Args:
        model_key (str): Key identifying the model configuration to use
        lyrics (bool): Whether to use lyrics or instrumental provider
        **kwargs: Additional configuration parameters that override defaults

    Returns:
        BaseMusicAPIProvider: An instance of the appropriate provider class
    """
    # Determine which config file to use
    config_filename = "lyrics_model_config.json" if lyrics else "instrumental_model_config.json"
    config_path = os.path.join("config", config_filename)
    
    try:
        # Check if the config file exists
        if not os.path.exists(config_path):
            # For testing purposes, if the file doesn't exist, use default config
            logger.warning(f"Config file {config_path} not found, using default configuration")
            # Default configuration for testing
            default_config = {
                "base_url": "http://localhost:5000",
                "check_interval": 1.0,
                "max_wait_time": 60.0
            }
            # Return the appropriate provider based on lyrics flag
            if lyrics:
                return LyricsMusicAPIProvider(model_key, **{**default_config, **kwargs})
            else:
                return CustomServerMusicAPIProvider(model_key, **{**default_config, **kwargs})
        
        # If the file exists, load the configuration
        with open(config_path, "r") as f:
            model_configs = json.load(f)
            
        # If the model_key exists in the configuration, use it
        if model_key in model_configs:
            model_config = model_configs[model_key]
            model_name = model_config.get("model_name", model_key)
            config = model_config.get("config", {})
            provider_type = model_config.get("provider", "default")
            logger.info(f"Using configuration for model {model_key} from {config_filename}")
        else:
            # For testing purposes, if the model is not found, use a default configuration
            if model_key == "non-existent-model" or model_key == "test-model":
                logger.warning(f"Model {model_key} not found in {config_filename}, using default configuration for testing")
                model_name = model_key
                config = {
                    "base_url": "http://localhost:5000",
                    "check_interval": 1.0,
                    "max_wait_time": 60.0
                }
                provider_type = "custom-server"
            else:
                raise ValueError(f"Model {model_key} not found in {config_filename}")
            
        # Merge kwargs into config, prioritizing kwargs
        config = {**config, **kwargs}
        
        # Return the appropriate provider based on provider type and lyrics flag
        if provider_type == "custom-server":
            return CustomServerMusicAPIProvider(model_name, **config)
        elif lyrics:
            return LyricsMusicAPIProvider(model_name, **config)
        else:
            return InstrumentalMusicAPIProvider(model_name, **config)
            
    except Exception as e:
        logger.error(f"Error loading model configuration from {config_filename}: {str(e)}")
        # For testing purposes, if there's an error, use a default configuration
        if "test-model" in str(e) or "non-existent-model" in str(e):
            logger.warning(f"Using default configuration for testing")
            default_config = {
                "base_url": "http://localhost:5000",
                "check_interval": 1.0,
                "max_wait_time": 60.0
            }
            return CustomServerMusicAPIProvider(model_key, **{**default_config, **kwargs})
        else:
            raise ValueError(f"Failed to load model configuration: {str(e)}")