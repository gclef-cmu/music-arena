"""Leaderboard generation from HuggingFace public dataset.

Fetches battle data transparently from the public HuggingFace dataset,
computes Arena Scores using Bradley-Terry model, and generates leaderboards.
"""

import json

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

from .config import HARDWARE_RTF_RATIOS, MODELS_METADATA, REFERENCE_HARDWARE
from .scoring import calculate_rtf, compute_arena_score


def fetch_hf_battles(repo_id="music-arena/music-arena-dataset"):
    """
    Fetches battle data from the public HuggingFace dataset via the Datasets Server API.

    This is the transparent data path: all data is publicly available
    and anyone can reproduce the leaderboard from this source.
    """
    print(f"Querying HuggingFace Datasets Server API for {repo_id}...")
    api_url = f"https://datasets-server.huggingface.co/parquet?dataset={repo_id}"

    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to query HF Datasets Server: {e}")
        return pd.DataFrame()

    parquet_items = [
        item
        for item in data.get("parquet_files", [])
        if item.get("split") == "train"
    ]

    if not parquet_items:
        print("No parquet files found. The dataset might still be processing.")
        return pd.DataFrame()

    all_dfs = []
    print(
        f"   - Found {len(parquet_items)} aggregated parquet configs. "
        "Loading directly into memory..."
    )

    for item in parquet_items:
        url = item["url"]
        config_name = item.get("config", "unknown_config")
        print(f"   - Streaming config [{config_name}]...")
        try:
            df = pd.read_parquet(url)
            all_dfs.append(df)
        except Exception as e:
            print(f"Failed to load config [{config_name}]: {e}")

    if not all_dfs:
        print("No data could be loaded.")
        return pd.DataFrame()

    full_df = pd.concat(all_dfs, ignore_index=True)
    print(f"Successfully streamed and merged {len(full_df)} total battles.")

    # Column mapping: HF dataset schema -> internal schema
    mapping = {}
    if "system_a" in full_df.columns:
        mapping["system_a"] = "model_a"
    if "system_b" in full_df.columns:
        mapping["system_b"] = "model_b"
    if "is_instrumental" in full_df.columns:
        mapping["is_instrumental"] = "instrumental"

    if mapping:
        full_df = full_df.rename(columns=mapping)

    # Convert preference values (A/B/TIE/BOTH_BAD) to winner labels
    if "preference" in full_df.columns:
        pref_map = {"A": "model_a", "B": "model_b", "TIE": "tie"}
        original_len = len(full_df)
        # Exclude BOTH_BAD: semantically different from TIE
        full_df = full_df[full_df["preference"].isin(pref_map.keys())].copy()
        excluded = original_len - len(full_df)
        if excluded > 0:
            print(
                f"   - Excluded {excluded} battles with BOTH_BAD preference "
                f"({excluded / original_len * 100:.1f}%)"
            )
        full_df["winner"] = full_df["preference"].map(pref_map)
        full_df = full_df.drop(columns=["preference"])
    elif "winner" not in full_df.columns:
        print("Warning: No 'preference' or 'winner' column found.")
        return pd.DataFrame()

    # Resolve timing column for RTF calculation.
    # Priority: gateway_time (user-perceived) > system_time > generation_time (legacy)
    for prefix in ["a", "b"]:
        target_col = f"generation_time_{prefix}"
        gw_col = f"gateway_time_{prefix}"
        sys_col = f"system_time_{prefix}"

        if gw_col in full_df.columns:
            full_df[target_col] = full_df[gw_col]
        elif sys_col in full_df.columns:
            full_df[target_col] = full_df[sys_col]
        # else: generation_time_{prefix} already exists (legacy HF data)

    return full_df


def compute_bootstrap_ci(battles_df, main_scores, n_resamples=1000):
    """Compute 95% confidence intervals via bootstrap resampling."""
    print(
        f"Computing bootstrap CIs (Standard Error Method) "
        f"with {n_resamples} resamples..."
    )

    models = pd.unique(battles_df[["model_a", "model_b"]].values.ravel("K"))
    all_scores = {model: [] for model in models}

    for _ in tqdm(range(n_resamples), desc="Bootstrap Resampling"):
        sample_df = battles_df.sample(n=len(battles_df), replace=True)
        scores = compute_arena_score(sample_df)

        for model in models:
            val = scores.get(model, main_scores.get(model))
            all_scores[model].append(val)

    cis = {}
    for model, dist in all_scores.items():
        if not dist:
            continue

        main_score = main_scores.get(model, 1000)
        std_dev = np.std(dist)
        margin = 1.96 * std_dev

        ci_lower = main_score - margin
        ci_upper = main_score + margin
        cis[model] = (ci_lower, ci_upper)

    return cis


def _normalize_rtfs_by_hardware(rtfs, battles_df, open_models):
    """Normalize open-weights model RTFs to reference hardware using global ratio.

    For each open-weights model, computes a weighted RTF where battles on
    non-reference hardware are corrected by the hardware speed ratio.
    Proprietary (API) models are left unchanged.
    """
    if "hardware_a" not in battles_df.columns:
        return rtfs  # No hardware info, skip normalization

    normalized = dict(rtfs)

    for model in open_models:
        if model not in rtfs or np.isnan(rtfs[model]):
            continue

        all_rtfs = []
        for prefix in ["a", "b"]:
            hw_col = f"hardware_{prefix}"
            model_col = f"model_{prefix}"
            dur_col = f"duration_{prefix}"
            gen_col = f"generation_time_{prefix}"

            mask = battles_df[model_col] == model
            sub = battles_df[mask][[dur_col, gen_col, hw_col]].dropna(
                subset=[dur_col, gen_col]
            )

            for _, row in sub.iterrows():
                if row[gen_col] <= 0:
                    continue
                measured_rtf = row[dur_col] / row[gen_col]
                if np.isinf(measured_rtf):
                    continue

                hw = row[hw_col] if pd.notna(row[hw_col]) else REFERENCE_HARDWARE
                ratio = HARDWARE_RTF_RATIOS.get(hw, 1.0)
                # Normalize to reference hardware
                corrected_rtf = measured_rtf / ratio
                all_rtfs.append(corrected_rtf)

        if all_rtfs:
            normalized[model] = round(np.median(all_rtfs), 2)

    return normalized


def generate_leaderboard(
    battles_df, models_metadata=None, leaderboard_type="instrumental"
):
    """
    Generate a leaderboard DataFrame from battle data.

    Args:
        battles_df: DataFrame with columns [model_a, model_b, winner, ...]
        models_metadata: Model metadata dict (defaults to config.MODELS_METADATA)
        leaderboard_type: "instrumental" or "vocal"

    Returns:
        DataFrame with Rank, Model, Arena Score, 95% CI, # Votes, etc.
    """
    if models_metadata is None:
        models_metadata = MODELS_METADATA

    vocal_models = {
        m for m, meta in models_metadata.items() if meta.get("supports_lyrics")
    }

    if leaderboard_type == "vocal":
        filtered_df = battles_df[
            battles_df["model_a"].isin(vocal_models)
            & battles_df["model_b"].isin(vocal_models)
        ].copy()
    else:
        filtered_df = battles_df[
            ~(
                battles_df["model_a"].isin(vocal_models)
                & battles_df["model_b"].isin(vocal_models)
            )
        ].copy()

    if filtered_df.shape[0] < 30:
        print(f"Not enough data to generate {leaderboard_type} leaderboard.")
        return pd.DataFrame()

    models = pd.unique(filtered_df[["model_a", "model_b"]].values.ravel("K"))

    # Compute scores (all battles including ties with 0.5 weight)
    scores = compute_arena_score(filtered_df)
    # Bootstrap CI must use same data distribution as main scores
    confidence_intervals = compute_bootstrap_ci(
        filtered_df,
        main_scores=scores,
        n_resamples=1000,
    )
    rtfs = calculate_rtf(filtered_df, models)

    # Hardware normalization for open-weights models:
    # If a model ran on non-reference hardware, normalize RTF using the
    # global hardware speed ratio. This only affects leaderboard display.
    open_models = {
        m for m, meta in models_metadata.items()
        if meta.get("access") == "Open weights"
    }
    rtfs = _normalize_rtfs_by_hardware(
        rtfs, filtered_df, open_models
    )

    votes = pd.concat(
        [filtered_df["model_a"], filtered_df["model_b"]]
    ).value_counts()

    data = []
    for model in models:
        main_score = scores.get(model)
        ci = confidence_intervals.get(model)
        if ci and main_score is not None:
            margin = (ci[1] - ci[0]) / 2
            ci_str = f"\u00b1{margin:.0f}"
        else:
            ci_str = "N/A"

        model_data = {
            "Model": model,
            "Arena Score": main_score,
            "95% CI": ci_str,
            "# Votes": votes.get(model, 0),
            "Generation Speed (RTF)": rtfs.get(model),
        }
        model_data.update(models_metadata.get(model, {}))
        data.append(model_data)

    df = (
        pd.DataFrame(data)
        .dropna(subset=["Arena Score"])
        .sort_values("Arena Score", ascending=False)
        .reset_index(drop=True)
    )
    df.index += 1
    df = df.rename_axis("Rank")

    df["Arena Score"] = df["Arena Score"].round(0).astype(int)
    if "Generation Speed (RTF)" in df.columns:
        df["Generation Speed (RTF)"] = df["Generation Speed (RTF)"].round(2)

    return df
