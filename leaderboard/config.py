GCP_PROJECT_ID = "Hidden"
METADATA_BUCKET_NAME = "Hidden"
AUDIO_BUCKET_NAME = "Hidden"
BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs"
METADATA_DOWNLOAD_DIR = "battle_data"
AUDIO_DOWNLOAD_DIR = "audio_files"

MODELS_METADATA = {
    "musicgen-small": {
        "organization": "Meta", "license": "CC-BY-NC 4.0", "training_data": "Stock",
        "supports_lyrics": False, "access": "Open weights"
    },
    "sao": {
        "organization": "Stability AI", "license": "STAI Community", "training_data": "Open",
        "supports_lyrics": False, "access": "Open weights"
    },
    "sao-small": {
        "organization": "Stability AI", "license": "STAI Community", "training_data": "Open",
        "supports_lyrics": False, "access": "Open weights"
    },
    "magenta-rt-large": {
        "organization": "Google DeepMind", "license": "Apache 2.0", "training_data": "Unspecified",
        "supports_lyrics": False, "access": "Open weights"
    },
    "acestep": {
        "organization": "ACE Studio", "license": "Apache 2.0", "training_data": "Unspecified",
        "supports_lyrics": True, "access": "Open weights"
    },
    "riffusion-fuzz-1-0": {
        "organization": "Riffusion", "license": "Closed", "training_data": "Commercial",
        "supports_lyrics": True, "access": "Proprietary"
    },
    "riffusion-fuzz-1-1": {
        "organization": "Riffusion", "license": "Closed", "training_data": "Commercial",
        "supports_lyrics": True, "access": "Proprietary"
    },
    "preview-ocelot": {
        "organization": "Hidden", "license": "Closed", "training_data": "Unspecified",
        "supports_lyrics": True, "access": "Proprietary"
    },
    "preview-jerboa": {
        "organization": "Hidden", "license": "Closed", "training_data": "Unspecified",
        "supports_lyrics": True, "access": "Proprietary"
    }
}