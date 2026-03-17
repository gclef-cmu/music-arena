"""Preprocess raw battle logs into HuggingFace dataset format.

Transforms raw GCP log files into the simplified schema used by
the music-arena-dataset on HuggingFace, organized by monthly batches.
"""

import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from tqdm import tqdm

from .config import MODELS_METADATA

EASTERN_TZ = ZoneInfo("America/New_York")

# Models whose audio is not publicly released
NON_PUBLIC_MODELS = {"sao", "sao-small"}


def sum_listen_time(listen_data: list) -> float:
    """Calculate total listening time from playback event logs."""
    total_time = 0.0
    last_play_time = None
    if not listen_data:
        return 0.0
    for event_data in listen_data:
        event, timestamp = None, None
        if isinstance(event_data, list) and len(event_data) == 2:
            event, timestamp = event_data
        elif isinstance(event_data, dict):
            event = event_data.get("action")
            timestamp = event_data.get("time")
        if not event or not timestamp:
            continue
        if event == "PLAY":
            if last_play_time is None:
                last_play_time = timestamp
        elif event in ["PAUSE", "STOP", "TICK"]:
            if last_play_time is not None:
                total_time += timestamp - last_play_time
            last_play_time = timestamp if event == "TICK" else None
    return total_time


def get_month_folder(date_obj: datetime) -> str:
    """Determine the target folder name based on the date."""
    FIRST_BATCH_END_DATE = datetime(2025, 8, 31, 23, 59, 59, tzinfo=EASTERN_TZ)
    if date_obj <= FIRST_BATCH_END_DATE:
        return "01-2025JULAUG"
    start_year = 2025
    start_month = 9
    months_diff = (date_obj.year - start_year) * 12 + (
        date_obj.month - start_month
    )
    batch_number = months_diff + 2
    year_str = date_obj.year
    month_str = date_obj.strftime("%b").upper()
    return f"{batch_number:02d}-{year_str}{month_str}"


def extract_hardware_and_time(metadata: dict, raw_json_str: str) -> tuple:
    """Extract generation times and determine hardware type (GPU).

    Returns both system_time (pure GPU compute) and gateway_time
    (includes network/queue overhead) for transparency.

    Returns:
        (hardware, system_time, gateway_time)
    """
    if not metadata:
        return "Unknown", None, None

    sys_start = metadata.get("system_time_started")
    sys_end = metadata.get("system_time_completed")
    gw_start = metadata.get("gateway_time_started")
    gw_end = metadata.get("gateway_time_completed")

    system_time = None
    if sys_start and sys_end:
        try:
            system_time = float(sys_end) - float(sys_start)
        except (ValueError, TypeError):
            pass

    gateway_time = None
    if gw_start and gw_end:
        try:
            gateway_time = float(gw_end) - float(gw_start)
        except (ValueError, TypeError):
            pass

    system_key = metadata.get("system_key") or {}
    system_tag = system_key.get("system_tag")
    model_info = MODELS_METADATA.get(system_tag, {})

    if model_info.get("access") == "Open weights":
        # Detect hardware from raw JSON content
        if "music-arena.org-new-a5000-machine" in raw_json_str:
            hardware = "A5000"
        else:
            hardware = "A6000"
    else:
        hardware = "Unknown (API)"

    return hardware, system_time, gateway_time


def process_example(example: dict, audio_a_path: str, audio_b_path: str) -> dict:
    """Parse a raw battle log into the simplified HuggingFace dataset schema."""
    vote_data = example.get("vote") or {}
    prompt_data = example.get("prompt") or {}
    raw_prompt_top = (
        prompt_data.get("prompt")
        if isinstance(prompt_data, dict)
        else example.get("prompt")
    )

    prompt_detailed = example.get("prompt_detailed") or {}
    a_meta = example.get("a_metadata") or {}
    b_meta = example.get("b_metadata") or {}
    user_data = example.get("prompt_user") or {}
    session_data = example.get("prompt_session") or {}

    date_timestamp = vote_data.get("preference_time") or session_data.get(
        "create_time"
    )
    date_obj = (
        datetime.fromtimestamp(date_timestamp, tz=EASTERN_TZ)
        if date_timestamp
        else None
    )

    # Normalize instrumental boolean
    is_inst = prompt_detailed.get("instrumental")
    if isinstance(is_inst, str):
        is_inst = is_inst.lower() == "true"
    else:
        is_inst = bool(is_inst)

    # Determine if prebaked
    raw_prebaked = (
        example.get("prompt_prebaked")
        or prompt_detailed.get("prompt_prebaked")
        or (
            prompt_data.get("prompt_prebaked")
            if isinstance(prompt_data, dict)
            else None
        )
    )
    if raw_prebaked is not None:
        if isinstance(raw_prebaked, str):
            is_prebaked = raw_prebaked.lower() == "true"
        else:
            is_prebaked = bool(raw_prebaked)
    else:
        is_prebaked = False

    # Extract prompt text
    overall_prompt = prompt_detailed.get("overall_prompt")
    if raw_prompt_top and str(raw_prompt_top).strip():
        prompt = raw_prompt_top
    elif overall_prompt and str(overall_prompt).strip():
        prompt = overall_prompt
    else:
        prompt = ""

    # Extract lyrics
    lyrics_extracted = (
        prompt_detailed.get("lyrics")
        or a_meta.get("lyrics")
        or b_meta.get("lyrics")
    )
    if is_inst:
        lyrics_extracted = ""
    if lyrics_extracted is None:
        lyrics_extracted = ""

    if not prompt and not is_inst:
        if lyrics_extracted and str(lyrics_extracted).strip():
            prompt = f"(Lyrics) {lyrics_extracted[:100]}..."

    if prompt is None:
        prompt = ""

    # Feedback
    feedback_a = vote_data.get("a_feedback") or ""
    feedback_b = vote_data.get("b_feedback") or ""
    feedback_gen = vote_data.get("feedback") or ""
    all_feedback = [
        f
        for f in [
            f"General: {feedback_gen}" if feedback_gen else "",
            f"Audio A: {feedback_a}" if feedback_a else "",
            f"Audio B: {feedback_b}" if feedback_b else "",
        ]
        if f
    ]

    # Listen data
    listen_data_a_str = (
        json.dumps(vote_data.get("a_listen_data"))
        if vote_data.get("a_listen_data")
        else None
    )
    listen_data_b_str = (
        json.dumps(vote_data.get("b_listen_data"))
        if vote_data.get("b_listen_data")
        else None
    )

    # Hardware and timing
    raw_json_str = json.dumps(example)
    hw_a, sys_time_a, gw_time_a = extract_hardware_and_time(a_meta, raw_json_str)
    hw_b, sys_time_b, gw_time_b = extract_hardware_and_time(b_meta, raw_json_str)

    return {
        "battle_uuid": example.get("uuid"),
        "date": date_obj.isoformat() if date_obj else None,
        "prompt": prompt,
        "is_instrumental": prompt_detailed.get("instrumental"),
        "is_prebaked": is_prebaked,
        "user_pseudonym": user_data.get("salted_ip"),
        "audio_a": audio_a_path,
        "system_a": (a_meta.get("system_key") or {}).get("system_tag"),
        "audio_b": audio_b_path,
        "system_b": (b_meta.get("system_key") or {}).get("system_tag"),
        "preference": vote_data.get("preference"),
        "total_listening_time_a": sum_listen_time(
            vote_data.get("a_listen_data")
        ),
        "total_listening_time_b": sum_listen_time(
            vote_data.get("b_listen_data")
        ),
        "feedback": " | ".join(all_feedback),
        "timestamp": date_timestamp,
        "lyrics": lyrics_extracted,
        "hardware_a": hw_a,
        "hardware_b": hw_b,
        "system_time_a": sys_time_a,
        "system_time_b": sys_time_b,
        "gateway_time_a": gw_time_a,
        "gateway_time_b": gw_time_b,
        "duration_a": a_meta.get("duration"),
        "duration_b": b_meta.get("duration"),
        "sample_rate_a": a_meta.get("sample_rate"),
        "sample_rate_b": b_meta.get("sample_rate"),
        "listen_data_a": listen_data_a_str,
        "listen_data_b": listen_data_b_str,
    }


def generate_metadata_files(
    batch_stats: dict, target_dir: Path, non_public_set: set
):
    """Generate per-period markdown summary files."""
    print(f"\nGenerating {len(batch_stats)} metadata files in {target_dir}...")
    target_dir.mkdir(parents=True, exist_ok=True)

    for month_folder, stats in batch_stats.items():
        try:
            parts = month_folder.split("-")
            num_part = parts[0].lstrip("0") + "."
            year_part = parts[1][:4]
            months_raw = parts[1][4:]
            month_list = [months_raw[i : i + 3] for i in range(0, len(months_raw), 3)]
            formatted_months = " & ".join(month_list)
            title = f"{num_part} {year_part} {formatted_months}"
        except Exception:
            title = month_folder

        model_table_rows = [
            f"| {model:<20} | {count:<16} |"
            for model, count in stats["model_counts"].most_common()
        ]

        content = f"""---
# Music Arena Dataset: {title}

## Data Summary
- **Number of Battles**: {stats["num_battles"]}
- **Total Possible Audio Files**: {stats["num_battles"] * 2}
- **Audio Files Excluded (Not Publicly Released)**: {stats["excluded_audio_count"]}
- **Audio Files Included in Release**: {stats["included_audio_count"]}

## Model Appearance Counts
This table shows how many times each model appeared in a battle during this period.

| Model Name           | Appearance Count |
|----------------------|------------------|
"""
        content += "\n".join(model_table_rows)
        content += (
            f"\n\n*Note: Audio files generated by the following models are "
            f"not included in this public data release: "
            f"`{', '.join(sorted(non_public_set))}`*\n"
        )

        output_file = target_dir / f"{month_folder}.md"
        try:
            with output_file.open("w", encoding="utf-8") as f:
                f.write(content.strip())
        except Exception as e:
            print(f"Failed to write metadata for {month_folder}: {e}")

    print("Metadata generation complete.")


def preprocess_dataset(
    source_log_dir: str,
    source_audio_dir: str,
    target_dir: str = ".",
):
    """Run the full preprocessing pipeline.

    Reads raw logs, organizes them by month, copies audio files,
    and generates the HuggingFace dataset structure.

    Args:
        source_log_dir: Directory containing raw JSON battle logs
        source_audio_dir: Directory containing raw audio files
        target_dir: Output directory for the dataset
    """
    source_log_dir = Path(source_log_dir)
    source_audio_dir = Path(source_audio_dir)
    target_dir = Path(target_dir)

    target_battle_dir = target_dir / "battle_data"
    target_audio_dir = target_dir / "audio_files"
    target_metadata_dir = target_dir / "metadata"

    known_models = set(MODELS_METADATA.keys())

    print(f"Cleaning subdirectories inside: {target_dir.resolve()}")
    for d in [target_battle_dir, target_audio_dir, target_metadata_dir]:
        if d.exists():
            print(f"Removing existing subdirectory: {d.name}")
            shutil.rmtree(d)

    print(f"\nProcessing logs from: {source_log_dir}")

    if not source_log_dir.exists():
        print(f"Source log directory not found: {source_log_dir}")
        return

    all_log_files = list(source_log_dir.glob("*.json"))
    print(f"Found {len(all_log_files)} log files")

    batch_stats = defaultdict(
        lambda: {
            "num_battles": 0,
            "model_counts": Counter(),
            "excluded_audio_count": 0,
            "included_audio_count": 0,
        }
    )

    for file_path in tqdm(all_log_files, desc="Processing files"):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            model_a_tag = (
                data.get("a_metadata", {})
                .get("system_key", {})
                .get("system_tag")
            )
            model_b_tag = (
                data.get("b_metadata", {})
                .get("system_key", {})
                .get("system_tag")
            )

            if not (model_a_tag in known_models and model_b_tag in known_models):
                continue

            vote_data = data.get("vote") or {}
            session_data = data.get("prompt_session") or {}
            date_timestamp = vote_data.get(
                "preference_time"
            ) or session_data.get("create_time")

            if not date_timestamp:
                continue

            date_obj = datetime.fromtimestamp(date_timestamp, tz=EASTERN_TZ)
            month_folder = get_month_folder(date_obj)

            stats = batch_stats[month_folder]
            stats["num_battles"] += 1
            if model_a_tag:
                stats["model_counts"][model_a_tag] += 1
            if model_b_tag:
                stats["model_counts"][model_b_tag] += 1

            # Process audio files
            target_audio_folder = target_audio_dir / month_folder
            target_audio_folder.mkdir(parents=True, exist_ok=True)

            a_filename = os.path.basename(
                urlparse(data["a_audio_url"]).path
            )
            audio_a_rel_path = ""
            if model_a_tag in NON_PUBLIC_MODELS:
                stats["excluded_audio_count"] += 1
            else:
                source_audio_path = source_audio_dir / a_filename
                if source_audio_path.exists():
                    shutil.copy2(source_audio_path, target_audio_folder)
                    audio_a_rel_path = (
                        f"audio_files/{month_folder}/{a_filename}"
                    )
                    stats["included_audio_count"] += 1

            b_filename = os.path.basename(
                urlparse(data["b_audio_url"]).path
            )
            audio_b_rel_path = ""
            if model_b_tag in NON_PUBLIC_MODELS:
                stats["excluded_audio_count"] += 1
            else:
                source_audio_path = source_audio_dir / b_filename
                if source_audio_path.exists():
                    shutil.copy2(source_audio_path, target_audio_folder)
                    audio_b_rel_path = (
                        f"audio_files/{month_folder}/{b_filename}"
                    )
                    stats["included_audio_count"] += 1

            # Generate simplified JSON
            simplified_data = process_example(
                data, audio_a_rel_path, audio_b_rel_path
            )

            target_json_folder = target_battle_dir / month_folder
            target_json_folder.mkdir(parents=True, exist_ok=True)

            target_json_path = target_json_folder / file_path.name
            with target_json_path.open("w", encoding="utf-8") as f:
                json.dump(simplified_data, f, ensure_ascii=False)

        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")

    generate_metadata_files(batch_stats, target_metadata_dir, NON_PUBLIC_MODELS)

    print(f"\nPreprocessing complete!")
    print(f"Data saved to: '{target_dir.resolve()}'")
