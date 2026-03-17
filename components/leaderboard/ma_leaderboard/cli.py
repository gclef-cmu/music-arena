"""CLI for Music Arena Leaderboard generation.

Usage:
    ma-leaderboard leaderboard [--output-dir DIR] [--hf-repo REPO]
    ma-leaderboard update-frontend [--output-dir DIR] [--frontend-dir DIR]
    ma-leaderboard download --logs-dir DIR --audio-dir DIR [--start DATE] [--end DATE]
    ma-leaderboard preprocess --logs-dir DIR --audio-dir DIR [--target-dir DIR]
"""

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _get_component_root():
    """Get the root directory of the leaderboard component."""
    return Path(__file__).parent.parent


def _get_music_arena_root():
    """Get the root directory of the music-arena project."""
    return _get_component_root().parent.parent


def cmd_leaderboard(args):
    """Generate leaderboard from HuggingFace public dataset."""
    from .config import MIN_VOTES_THRESHOLD, MODELS_METADATA
    from .leaderboard import fetch_hf_battles, generate_leaderboard
    from .visualizer import plot_leaderboard

    output_dir = Path(args.output_dir)
    leaderboards_dir = output_dir / "leaderboards"
    plots_dir = output_dir / "plots"
    leaderboards_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch battle data from HuggingFace
    print("\nStarting Transparent Leaderboard Generation via HuggingFace...")
    battles_df = fetch_hf_battles(repo_id=args.hf_repo)

    if battles_df.empty:
        print("No battle data found from HuggingFace.")
        return

    # 2. Determine date range
    date_str = "all_time"
    period_display = "HuggingFace Dataset (All Time)"

    if "date" in battles_df.columns:
        try:
            dt_series = pd.to_datetime(battles_df["date"])
            min_dt = dt_series.min().strftime("%Y-%m-%d")
            max_dt = dt_series.max().strftime("%Y-%m-%d")
            period_display = f"{min_dt} ~ {max_dt}"
            date_str = (
                f"{min_dt.replace('-', '')}_to_{max_dt.replace('-', '')}"
            )
        except Exception as e:
            print(f"Date parsing info: {e}")

    # 3. Split into instrumental / vocal
    inst_col = (
        "instrumental"
        if "instrumental" in battles_df.columns
        else "is_instrumental"
    )

    if inst_col in battles_df.columns:
        battles_inst = battles_df[battles_df[inst_col] == True].copy()
        battles_vocal = battles_df[battles_df[inst_col] == False].copy()
    else:
        print(
            "Warning: 'instrumental' column not found. "
            "Using full dataset for both."
        )
        battles_inst = battles_df
        battles_vocal = battles_df

    print(f"Battle Counts:")
    print(f"   Instrumental: {len(battles_inst)}")
    print(f"   Vocal       : {len(battles_vocal)}")
    print(f"   Total       : {len(battles_df)}")

    # 4. Generate leaderboards
    inst_df = _generate_and_save(
        battles_inst,
        "instrumental",
        date_str,
        period_display,
        leaderboards_dir,
        MODELS_METADATA,
        MIN_VOTES_THRESHOLD,
    )
    vocal_df = _generate_and_save(
        battles_vocal,
        "vocal",
        date_str,
        period_display,
        leaderboards_dir,
        MODELS_METADATA,
        MIN_VOTES_THRESHOLD,
    )

    # 5. Generate plots
    if not inst_df.empty or not vocal_df.empty:
        subtitle_text = f"Period: {period_display}"

        # Look for logo files
        logo_path = None
        qr_path = None
        for search_dir in [_get_component_root(), _get_music_arena_root()]:
            candidate = search_dir / "musicarena_logo.png"
            if candidate.exists():
                logo_path = str(candidate)
            candidate = search_dir / "musicarena_qr.png"
            if candidate.exists():
                qr_path = str(candidate)

        plot_leaderboard(
            inst_df=inst_df,
            vocal_df=vocal_df,
            inst_filename=str(plots_dir / f"instrumental_plot_{date_str}.png"),
            vocal_filename=str(plots_dir / f"vocal_plot_{date_str}.png"),
            combined_filename=str(plots_dir / "combined_unused.png"),
            subtitle=subtitle_text,
            logo_path=logo_path,
            qr_path=qr_path,
        )
        # Remove combined plot (not needed)
        (plots_dir / "combined_unused.png").unlink(missing_ok=True)

    print(f"\nLeaderboard generation complete. Results in: {output_dir}")


def _generate_and_save(
    battles_df,
    model_type,
    date_str,
    period_str,
    output_dir,
    models_metadata,
    min_votes,
):
    """Generate leaderboard, filter, rank, save to TSV."""
    from .leaderboard import generate_leaderboard

    df = generate_leaderboard(battles_df, models_metadata, model_type)

    # Display filtering (min votes)
    if not df.empty and "# Votes" in df.columns:
        df = df[df["# Votes"] >= min_votes].copy()

    if not df.empty:
        if "Arena Score" in df.columns:
            df = df.sort_values(by="Arena Score", ascending=False)
        df = df.reset_index(drop=True)
        df["Rank"] = range(1, len(df) + 1)

    desired_columns = [
        "Rank",
        "Model",
        "Arena Score",
        "95% CI",
        "# Votes",
        "Generation Speed (RTF)",
        "organization",
        "training_data",
        "supports_lyrics",
        "access",
    ]
    final_columns = [col for col in desired_columns if col in df.columns]
    df = df[final_columns]

    if not df.empty:
        label = "Instrumental" if model_type == "instrumental" else "Vocal"
        print(f"\n--- {label} Leaderboard ---")
        print(df.to_string(index=False))

        tsv_path = output_dir / f"{model_type}_leaderboard_{date_str}.tsv"
        df.to_csv(tsv_path, sep="\t", index=False)
        print(f"Saved to: {tsv_path}")
    else:
        print(
            f"\n--- {model_type.capitalize()} Leaderboard ---\n"
            f"No models meet the minimum vote threshold ({min_votes} votes)."
        )

    return df


def cmd_update_frontend(args):
    """Copy generated leaderboard results to the frontend directory."""
    output_dir = Path(args.output_dir)
    frontend_dir = Path(args.frontend_dir)

    leaderboards_dir = output_dir / "leaderboards"
    plots_dir = output_dir / "plots"

    if not leaderboards_dir.exists():
        print(
            f"No leaderboard results found in {output_dir}. "
            "Run 'ma-leaderboard leaderboard' first."
        )
        return

    # Determine date folder from the leaderboard filenames (e.g., ..._to_20260228.tsv -> 20260228)
    tsv_files = list(leaderboards_dir.glob("*.tsv"))
    if tsv_files:
        # Extract end date from filename like "instrumental_leaderboard_20250728_to_20260228.tsv"
        stem = tsv_files[0].stem  # e.g., "instrumental_leaderboard_20250728_to_20260228"
        parts = stem.split("_to_")
        date_str = parts[-1] if len(parts) > 1 else datetime.now(timezone.utc).strftime("%Y%m%d")
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    target_dir = frontend_dir / date_str
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy TSV files
    for tsv_file in leaderboards_dir.glob("*.tsv"):
        shutil.copy2(tsv_file, target_dir)
        print(f"Copied: {tsv_file.name} -> {target_dir}")

    # Copy PNG files
    for png_file in plots_dir.glob("*.png"):
        shutil.copy2(png_file, target_dir)
        print(f"Copied: {png_file.name} -> {target_dir}")

    print(f"\nFrontend updated: {target_dir}")


def _infer_start_date(logs_dir):
    """Infer start date from existing downloaded logs.

    Scans all log files to find the latest battle timestamp.
    If no data exists, starts from the Music Arena launch date.
    """
    import json as _json

    LAUNCH_DATE = datetime(2025, 7, 28, tzinfo=timezone.utc)
    logs_path = Path(logs_dir)

    files = list(logs_path.glob("*.json")) if logs_path.exists() else []

    if not files:
        print(f"  No existing data found. Starting from launch date: {LAUNCH_DATE.date()}")
        return LAUNCH_DATE

    print(f"  Scanning {len(files)} existing logs for latest date...")

    latest_ts = None
    for f in files:
        try:
            with open(f) as fh:
                data = _json.load(fh)
            ts = (
                data.get("prompt_session", {}).get("create_time")
                or data.get("a_metadata", {}).get("gateway_time_completed")
            )
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts
        except Exception:
            continue

    if latest_ts:
        dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
        print(f"  Latest data: {dt.date()} (from {len(files)} files)")
        return dt.replace(hour=0, minute=0, second=0)

    print(f"  Could not parse dates. Starting from launch date.")
    return LAUNCH_DATE


def _infer_end_date():
    """Infer end date as end of previous month."""
    now = datetime.now(timezone.utc)
    # Last day of previous month
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_of_prev_month = first_of_this_month - pd.Timedelta(seconds=1)
    end = last_of_prev_month.replace(hour=23, minute=59, second=59)
    print(f"  End date (end of last month): {end.date()}")
    return end


def cmd_download(args):
    """Download battle logs and audio from GCP."""
    from .data_loader import download_filtered_logs_and_audio

    # Auto-infer dates if not provided
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    else:
        start_date = _infer_start_date(args.logs_dir)

    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    else:
        end_date = _infer_end_date()

    print(f"\nDownload range: {start_date.date()} ~ {end_date.date()}")

    if start_date.date() >= end_date.date():
        print("Already up to date. Nothing to download.")
        logs_path = Path(args.logs_dir)
        count = len(list(logs_path.glob("*.json"))) if logs_path.exists() else 0
        print(f"  {count} total log files in {args.logs_dir}")
        return

    download_filtered_logs_and_audio(
        logs_dir=args.logs_dir,
        audio_dir=args.audio_dir,
        start_date=start_date,
        end_date=end_date,
    )

    # Print sanity check summary
    logs_path = Path(args.logs_dir)
    count = len(list(logs_path.glob("*.json"))) if logs_path.exists() else 0
    print(f"\nSanity check: {count} total log files in {args.logs_dir}")


def cmd_preprocess(args):
    """Preprocess raw logs into HuggingFace dataset format."""
    from .preprocess import preprocess_dataset

    preprocess_dataset(
        source_log_dir=args.logs_dir,
        source_audio_dir=args.audio_dir,
        target_dir=args.target_dir,
    )


def cmd_compute_baselines(args):
    """Compute hardware speed ratios from raw logs."""
    from .scoring import compute_hardware_ratios

    print("Computing hardware speed ratios from raw logs...\n")
    compute_hardware_ratios(args.logs_dir)


def _fetch_hf_raw_count(hf_repo):
    """Fetch raw battle count from HuggingFace without any filtering."""
    import requests

    api_url = f"https://datasets-server.huggingface.co/parquet?dataset={hf_repo}"
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to query HF: {e}")
        return 0, pd.DataFrame()

    parquet_items = [
        item for item in data.get("parquet_files", [])
        if item.get("split") == "train"
    ]

    all_dfs = []
    for item in parquet_items:
        try:
            df = pd.read_parquet(item["url"], columns=["preference"])
            all_dfs.append(df)
        except Exception:
            continue

    if not all_dfs:
        return 0, pd.DataFrame()

    full_df = pd.concat(all_dfs, ignore_index=True)
    return len(full_df), full_df


def cmd_sanity_check(args):
    """Compare local data counts with HuggingFace dataset."""
    print("=== Sanity Check: Local vs HuggingFace ===\n")

    # 1. Count local logs
    logs_path = Path(args.logs_dir)
    local_count = 0
    if logs_path.exists():
        local_count = len(list(logs_path.glob("*.json")))
    print(f"Local logs: {local_count} files in {args.logs_dir}")

    # 2. Fetch raw HF count (no filtering)
    hf_repo = args.hf_repo
    if not hf_repo:
        from .config import HF_REPO_ID
        hf_repo = HF_REPO_ID

    print(f"\nFetching raw counts from HuggingFace ({hf_repo})...")
    hf_total, hf_df = _fetch_hf_raw_count(hf_repo)

    # 3. Breakdown by preference
    print(f"\nHuggingFace dataset:")
    print(f"  Total battles: {hf_total}")
    if not hf_df.empty and "preference" in hf_df.columns:
        counts = hf_df["preference"].value_counts()
        for pref, count in counts.items():
            print(f"    {pref}: {count} ({count/hf_total*100:.1f}%)")

    # 4. Compare raw totals
    print(f"\nComparison (raw totals, no filtering):")
    print(f"  Local: {local_count}")
    print(f"  HF:    {hf_total}")
    diff = local_count - hf_total
    if diff > 0:
        print(f"  Local has {diff} MORE → new data not yet pushed to HF")
    elif diff < 0:
        print(f"  HF has {abs(diff)} MORE → local data may be incomplete")
    else:
        print(f"  Counts match!")


def main():
    parser = argparse.ArgumentParser(
        description="Music Arena Leaderboard Generator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # leaderboard command
    lb_parser = subparsers.add_parser(
        "leaderboard",
        help="Generate leaderboard from HuggingFace public dataset",
    )
    lb_parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Output directory for results (default: results/)",
    )
    lb_parser.add_argument(
        "--hf-repo",
        type=str,
        default=None,
        help="HuggingFace dataset repository ID",
    )

    # update-frontend command
    uf_parser = subparsers.add_parser(
        "update-frontend",
        help="Copy results to frontend leaderboard directory",
    )
    uf_parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Source results directory (default: results/)",
    )
    default_frontend_dir = str(
        _get_music_arena_root()
        / "components"
        / "frontend"
        / "ma_frontend"
        / "leaderboard"
    )
    uf_parser.add_argument(
        "--frontend-dir",
        type=str,
        default=default_frontend_dir,
        help="Frontend leaderboard directory",
    )

    # Default data directories under components/leaderboard/data/
    default_data_dir = _get_component_root() / "data"
    default_logs_dir = str(default_data_dir / "logs")
    default_audio_dir = str(default_data_dir / "audio")
    default_dataset_dir = str(default_data_dir / "dataset")

    # download command (requires GCP auth + env vars)
    dl_parser = subparsers.add_parser(
        "download",
        help="Download battle logs and audio from GCP (requires credentials)",
    )
    dl_parser.add_argument(
        "--logs-dir",
        type=str,
        default=default_logs_dir,
        help=f"Directory for log files (default: {default_logs_dir})",
    )
    dl_parser.add_argument(
        "--audio-dir",
        type=str,
        default=default_audio_dir,
        help=f"Directory for audio files (default: {default_audio_dir})",
    )
    dl_parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    dl_parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")

    # preprocess command
    pp_parser = subparsers.add_parser(
        "preprocess",
        help="Preprocess raw logs into HuggingFace dataset format",
    )
    pp_parser.add_argument(
        "--logs-dir",
        type=str,
        default=default_logs_dir,
        help=f"Source log directory (default: {default_logs_dir})",
    )
    pp_parser.add_argument(
        "--audio-dir",
        type=str,
        default=default_audio_dir,
        help=f"Source audio directory (default: {default_audio_dir})",
    )
    pp_parser.add_argument(
        "--target-dir",
        type=str,
        default=default_dataset_dir,
        help=f"Output directory (default: {default_dataset_dir})",
    )

    # sanity-check command
    sc_parser = subparsers.add_parser(
        "sanity-check",
        help="Compare local data counts with HuggingFace dataset",
    )
    sc_parser.add_argument(
        "--logs-dir",
        type=str,
        default=default_logs_dir,
        help=f"Local log directory (default: {default_logs_dir})",
    )
    sc_parser.add_argument(
        "--hf-repo",
        type=str,
        default=None,
        help="HuggingFace dataset repository ID",
    )

    # compute-baselines command
    cb_parser = subparsers.add_parser(
        "compute-baselines",
        help="Compute A6000 RTF baselines from raw logs (for config.py)",
    )
    cb_parser.add_argument(
        "--logs-dir",
        type=str,
        default=default_logs_dir,
        help=f"Raw log directory (default: {default_logs_dir})",
    )

    args = parser.parse_args()

    if args.command == "leaderboard":
        if args.hf_repo is None:
            from .config import HF_REPO_ID

            args.hf_repo = HF_REPO_ID
        cmd_leaderboard(args)
    elif args.command == "update-frontend":
        cmd_update_frontend(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "preprocess":
        cmd_preprocess(args)
    elif args.command == "sanity-check":
        cmd_sanity_check(args)
    elif args.command == "compute-baselines":
        cmd_compute_baselines(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
