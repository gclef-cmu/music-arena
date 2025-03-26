import requests
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

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

    def generate_music(
        self, prompt: str, seed: Optional[int] = None
    ) -> MusicResponseOutput:
        """
        Generate music from a text prompt using the custom Flask server.

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
            # Submit the job
            submit_response = requests.post(f"{base_url}/submit", data=data)
            submit_response.raise_for_status()
            job_id = submit_response.json()["job_id"]

            # Poll for completion
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                status_response = requests.get(
                    f"{base_url}/status", params={"job_id": job_id}
                )
                status_response.raise_for_status()
                status = status_response.json()["status"]

                if status == "COMPLETE":
                    # Download the generated audio
                    download_response = requests.get(
                        f"{base_url}/download", params={"job_id": job_id}
                    )
                    download_response.raise_for_status()
                    return MusicResponseOutput(audio_data=download_response.content)

                elif status == "ERROR":
                    return MusicResponseOutput(
                        audio_data=None, error=f"Job {job_id} failed during processing"
                    )

                time.sleep(check_interval)

            return MusicResponseOutput(
                audio_data=None,
                error=f"Job {job_id} timed out after {max_wait_time} seconds",
            )

        except requests.exceptions.RequestException as e:
            return MusicResponseOutput(
                audio_data=None, error=f"API request failed: {str(e)}"
            )


def get_music_api_provider(model_key: str, **kwargs):
    """
    Factory function to create an appropriate music API provider instance.

    Args:
        model_key (str): Key identifying the model configuration to use
        **kwargs: Additional configuration parameters that override defaults

    Returns:
        BaseMusicAPIProvider: An instance of the appropriate provider class
    """
    import os
    import json
    
    # Default configuration
    base_config = {
        "base_url": "http://localhost:5000",
        "check_interval": 1.0,
        "max_wait_time": 60.0,  # 1 minute
    }
    
    # Try to load model configuration from model_config.json
    config_path = os.path.join("config", "model_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                model_configs = json.load(f)
                
            # If the model_key exists in the configuration, use it
            if model_key in model_configs:
                model_config = model_configs[model_key]
                model_name = model_config.get("model_name", model_key)
                config = {**base_config, **model_config.get("config", {})}
                logger.info(f"Using configuration for model {model_key} from model_config.json")
            else:
                model_name = model_key
                config = base_config
                logger.warning(f"Model {model_key} not found in model_config.json, using default configuration")
        except Exception as e:
            logger.error(f"Error loading model configuration: {str(e)}")
            model_name = model_key
            config = base_config
    else:
        logger.warning("model_config.json not found, using default configuration")
        model_name = model_key
        config = base_config
    
    # Merge kwargs into config, prioritizing kwargs
    config = {**config, **kwargs}
    
    return CustomServerMusicAPIProvider(model_name, **config)