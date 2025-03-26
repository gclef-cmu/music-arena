import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_settings():
    """
    Load settings from config file or environment variables.
    """
    config_path = "config/settings.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    
    # Default settings if config file doesn't exist
    return {
        "firebase_collections": {
            "audio_metadata": "audio_metadata",
            "audio_outcomes": "audio_outcomes"
        },
        "gcs_buckets": {
            "audio_files": os.getenv("GCS_AUDIO_BUCKET", "music-arena-audio")
        },
        "version_backend": "0.1.0"
    }

def generate_unique_id():
    """Generate a unique ID for audio files."""
    return str(uuid.uuid4())

def get_timestamp():
    """Get current timestamp in seconds."""
    return int(datetime.now().timestamp())

def create_audio_metadata(
    audio_id: str,
    user_id: str,
    prompt: str,
    model: str,
    latency: float,
    seed: Optional[int] = None,
    pair_audio_id: Optional[str] = None,
    pair_index: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create metadata dictionary for an audio file.
    
    Args:
        audio_id: Unique ID for the audio
        user_id: ID of the user who requested the audio
        prompt: Text prompt used to generate the audio
        model: Name of the model used for generation
        latency: Time taken to generate the audio in seconds
        seed: Optional seed used for generation
        pair_audio_id: ID of the paired audio (if applicable)
        pair_index: Index in the pair (0 or 1)
        
    Returns:
        Dictionary containing the audio metadata
    """
    metadata = {
        "audioId": audio_id,
        "userId": user_id,
        "timestamp": get_timestamp(),
        "prompt": prompt,
        "model": model,
        "latency": latency,
        "versionBackend": get_settings().get("version_backend", "0.1.0")
    }
    
    if seed is not None:
        metadata["seed"] = seed
    
    if pair_audio_id is not None:
        metadata["pairAudioId"] = pair_audio_id
    
    if pair_index is not None:
        metadata["pairIndex"] = pair_index
    
    return metadata