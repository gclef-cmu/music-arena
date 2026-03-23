"""Download and parse battle logs from GCP.

Requires GCP authentication and the following environment variables:
    MUSIC_ARENA_GCP_PROJECT_ID
    MUSIC_ARENA_METADATA_BUCKET
    MUSIC_ARENA_AUDIO_BUCKET

Install with: pip install -e "components/leaderboard/[gcp]"
"""

import json
import os

import pandas as pd
from datetime import datetime, timezone
from tqdm import tqdm

from .config import MODELS_METADATA


def _get_gcp_config():
    """Read GCP configuration from environment variables."""
    project_id = os.environ.get("MUSIC_ARENA_GCP_PROJECT_ID")
    metadata_bucket = os.environ.get("MUSIC_ARENA_METADATA_BUCKET")
    audio_bucket = os.environ.get("MUSIC_ARENA_AUDIO_BUCKET")

    missing = []
    if not project_id:
        missing.append("MUSIC_ARENA_GCP_PROJECT_ID")
    if not metadata_bucket:
        missing.append("MUSIC_ARENA_METADATA_BUCKET")
    if not audio_bucket:
        missing.append("MUSIC_ARENA_AUDIO_BUCKET")

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "These are needed for GCP access. Contact the project maintainers."
        )

    return project_id, metadata_bucket, audio_bucket


def download_filtered_logs_and_audio(
    logs_dir, audio_dir, start_date=None, end_date=None
):
    """Download battle logs and audio from GCP buckets.

    Filters by known models and optional date range.
    Skips files already present locally.
    """
    from google.cloud import storage
    from urllib.parse import urlparse

    project_id, metadata_bucket_name, audio_bucket_name = _get_gcp_config()

    print(f"Starting integrated download...")
    print(f" - Logs will be saved to: '{logs_dir}'")
    print(f" - Audio will be saved to: '{audio_dir}'")

    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    storage_client = storage.Client(project=project_id)
    metadata_bucket = storage_client.bucket(metadata_bucket_name)
    audio_bucket = storage_client.bucket(audio_bucket_name)

    local_log_files = set(os.listdir(logs_dir))
    local_audio_files = set(os.listdir(audio_dir))
    known_models = set(MODELS_METADATA.keys())

    all_blobs = list(metadata_bucket.list_blobs())
    if start_date and end_date:
        all_blobs = [
            b
            for b in all_blobs
            if b.time_created and start_date <= b.time_created <= end_date
        ]

    print(f"Found {len(all_blobs)} logs in range. Filtering and downloading...")

    downloaded_logs = 0
    downloaded_audio = 0
    skipped_unknown = 0

    for blob in tqdm(all_blobs, desc="Processing Logs and Audio"):
        log_filename = os.path.basename(blob.name)
        if not log_filename.endswith(".json"):
            continue

        try:
            if log_filename in local_log_files:
                continue

            metadata_content = blob.download_as_string()
            data = json.loads(metadata_content)

            if not data.get("vote"):
                continue

            model_a = (
                data.get("a_metadata", {})
                .get("system_key", {})
                .get("system_tag")
            )
            model_b = (
                data.get("b_metadata", {})
                .get("system_key", {})
                .get("system_tag")
            )

            if not (
                model_a
                and model_b
                and model_a in known_models
                and model_b in known_models
            ):
                skipped_unknown += 1
                continue

            with open(os.path.join(logs_dir, log_filename), "wb") as f:
                f.write(metadata_content)
            downloaded_logs += 1

            audio_urls = [data.get("a_audio_url"), data.get("b_audio_url")]
            for url in audio_urls:
                if not url:
                    continue

                audio_filename = os.path.basename(urlparse(url).path)
                if not audio_filename:
                    continue

                if audio_filename not in local_audio_files:
                    audio_blob = audio_bucket.blob(audio_filename)
                    if audio_blob.exists():
                        dest_path = os.path.join(audio_dir, audio_filename)
                        audio_blob.download_to_filename(dest_path)
                        local_audio_files.add(audio_filename)
                        downloaded_audio += 1

        except Exception as e:
            print(f"\nWarning: Failed to process {blob.name}. Error: {e}")

    print(f"\nDownload complete.")
    print(f"  Logs downloaded: {downloaded_logs}")
    print(f"  Audio downloaded: {downloaded_audio}")
    print(f"  Skipped (unknown models): {skipped_unknown}")


def load_all_raw_logs(log_dir: str) -> list:
    """Load all JSON log files from a directory."""
    if not os.path.exists(log_dir):
        return []
    raw_logs = []
    for filename in os.listdir(log_dir):
        if filename.endswith(".json"):
            with open(os.path.join(log_dir, filename), "r") as f:
                try:
                    raw_logs.append(json.load(f))
                except json.JSONDecodeError:
                    continue
    return raw_logs


def parse_logs(log_dir, start_date=None, end_date=None):
    """Parse local JSON logs into a battles DataFrame.

    Returns:
        Tuple of (battles_df, raw_logs)
    """
    print(f"\nParsing logs from: {log_dir}")

    parsed_data = []
    raw_logs = []
    known_models = set(MODELS_METADATA.keys())
    skipped_unknown = 0

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Parsing files"):
        filepath = os.path.join(log_dir, filename)
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        # Recover prompt from detailed prompt if missing
        if not data.get("prompt") and data.get("prompt_prebaked"):
            prompt_detailed = data.get("prompt_detailed")
            if isinstance(prompt_detailed, dict):
                recovered = prompt_detailed.get("overall_prompt")
                if not recovered:
                    lyrics = data.get("a_metadata", {}).get(
                        "lyrics"
                    ) or data.get("b_metadata", {}).get("lyrics")
                    if lyrics:
                        recovered = f"(Lyrics) {lyrics[:100]}..."
                if recovered:
                    data["prompt"] = recovered

        # Date filtering
        if start_date and end_date:
            session_time_unix = None
            prompt_session = data.get("prompt_session")
            if isinstance(prompt_session, dict):
                session_time_unix = prompt_session.get("create_time")
            if not session_time_unix:
                a_meta = data.get("a_metadata")
                if isinstance(a_meta, dict):
                    session_time_unix = a_meta.get("gateway_time_completed")

            if session_time_unix:
                try:
                    ts_dt = datetime.fromtimestamp(
                        session_time_unix, tz=timezone.utc
                    )
                    if not (start_date <= ts_dt <= end_date):
                        continue
                except (ValueError, OSError):
                    continue
            else:
                continue

        # Normalize instrumental boolean
        prompt_detailed = data.get("prompt_detailed")
        if not isinstance(prompt_detailed, dict):
            prompt_detailed = {}
            data["prompt_detailed"] = prompt_detailed

        raw_inst = prompt_detailed.get("instrumental")
        is_inst = False
        if raw_inst is not None:
            if isinstance(raw_inst, str):
                is_inst = raw_inst.lower() == "true"
            else:
                is_inst = bool(raw_inst)
        data["prompt_detailed"]["instrumental"] = is_inst

        # Extract lyrics
        extracted_lyrics = data.get("a_metadata", {}).get("lyrics")
        if not extracted_lyrics:
            extracted_lyrics = data.get("b_metadata", {}).get("lyrics")
        data["lyrics"] = extracted_lyrics

        raw_logs.append(data)

        if (
            data.get("vote")
            and data.get("a_metadata")
            and data.get("b_metadata")
        ):
            try:
                model_a = data["a_metadata"]["system_key"]["system_tag"]
                model_b = data["b_metadata"]["system_key"]["system_tag"]

                if model_a not in known_models or model_b not in known_models:
                    skipped_unknown += 1
                    continue

                pref = data["vote"]["preference"]
                if pref == "BOTH_BAD":
                    continue  # Exclude BOTH_BAD from scoring
                winner = "tie"
                if pref == "A":
                    winner = "model_a"
                elif pref == "B":
                    winner = "model_b"

                parsed_data.append(
                    {
                        "model_a": model_a,
                        "model_b": model_b,
                        "winner": winner,
                        "duration_a": data["a_metadata"]["duration"],
                        "generation_time_a": data["a_metadata"][
                            "gateway_time_completed"
                        ]
                        - data["a_metadata"]["gateway_time_started"],
                        "duration_b": data["b_metadata"]["duration"],
                        "generation_time_b": data["b_metadata"][
                            "gateway_time_completed"
                        ]
                        - data["b_metadata"]["gateway_time_started"],
                        "is_instrumental": is_inst,
                        "instrumental": is_inst,
                        "lyrics": extracted_lyrics,
                    }
                )
            except (KeyError, TypeError):
                continue

    if skipped_unknown:
        print(f"  Skipped {skipped_unknown} battles with unknown models")

    return pd.DataFrame(parsed_data), raw_logs
