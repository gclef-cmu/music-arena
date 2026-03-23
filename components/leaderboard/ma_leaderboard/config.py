"""Configuration for Music Arena Leaderboard.

Model metadata is loaded automatically from systems/registry.yaml
(the single source of truth for all models in Music Arena).
No GCP credentials or bucket names are stored here.
"""

import os
from pathlib import Path

# HuggingFace dataset repository (public)
HF_REPO_ID = os.getenv("MUSIC_ARENA_HF_REPO", "music-arena/music-arena-dataset")

# Minimum number of votes required for a model to appear on the leaderboard
MIN_VOTES_THRESHOLD = 30

# =============================================================================
# Hardware RTF Normalization
#
# When open-weights models run on different hardware, their measured RTF changes.
# To ensure fair comparison, we normalize all RTFs to a reference hardware (A6000).
#
# HARDWARE_RTF_RATIOS maps hardware_name -> speed ratio relative to A6000.
# A ratio < 1 means slower than A6000; > 1 means faster.
# To normalize: corrected_rtf = measured_rtf / ratio (brings it back to A6000 scale)
#
# To recalculate: ma-leaderboard compute-baselines
# This only affects the leaderboard display, NOT the dataset.
# =============================================================================
REFERENCE_HARDWARE = "A6000"

HARDWARE_RTF_RATIOS = {
    "A6000": 1.0,
    "A5000": 0.815,  # A5000 is ~0.81x the speed of A6000
}

# =============================================================================
# Model Metadata — loaded from systems/registry.yaml
# =============================================================================

# Models to exclude from leaderboard:
# - test/utility systems that were never deployed
# - older private testing models that should not be shown publicly
_EXCLUDED_MODELS = {
    "noise",           # test system
    "audioldm2",       # registered but never deployed
    "lyria-rt",        # registered but never deployed
    "sa2",             # registered but never deployed
    "songgen",         # registered but never deployed
    "musicgen-large",  # registered but never deployed
    "magenta-rt-base", # registered but never deployed
    "preview-ocelot",  # private testing model
    "preview-jerboa",  # private testing model
}

_ACCESS_MAP = {"OPEN": "Open weights", "PROPRIETARY": "Proprietary"}

_TRAINING_DATA_MAP = {
    "Stock": "Stock",
    "Creative Commons": "Open",
    "Licensed": "Licensed",
    "Commercial": "Commercial",
}


def _load_models_from_registry():
    """Load model metadata from systems/registry.yaml (single source of truth).

    Automatically picks up new models when they are added to the registry,
    and excludes models that are removed.
    """
    import yaml

    # Find registry.yaml relative to music-arena root
    registry_paths = [
        Path(__file__).parent.parent.parent.parent / "systems" / "registry.yaml",
        Path(os.getenv("MUSIC_ARENA_REGISTRY", "")) / "registry.yaml",
    ]

    for path in registry_paths:
        if path.exists():
            break
    else:
        print(
            "WARNING: systems/registry.yaml not found. "
            "Using empty model metadata."
        )
        return {}

    with open(path) as f:
        registry = yaml.safe_load(f)

    models = {}
    for name, info in registry.items():
        if name in _EXCLUDED_MODELS:
            continue
        if not isinstance(info, dict):
            continue

        access_raw = info.get("access", "PROPRIETARY")
        td_raw = info.get("training_data", {})
        td_type = td_raw.get("type", "Unspecified") if isinstance(td_raw, dict) else "Unspecified"

        models[name] = {
            "organization": info.get("organization", "Unknown"),
            "training_data": _TRAINING_DATA_MAP.get(td_type, "Unspecified"),
            "supports_lyrics": info.get("supports_lyrics", False),
            "access": _ACCESS_MAP.get(access_raw, "Proprietary"),
        }

    return models


MODELS_METADATA = _load_models_from_registry()
