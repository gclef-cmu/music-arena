"""Arena Score computation using Bradley-Terry model and RTF calculation."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


def compute_arena_score(
    battles_df: pd.DataFrame, scale=400, base=10, init_rating=1000
):
    """
    Calculates Arena Score using a Bradley-Terry model.

    - L2 Regularization to prevent score explosion on perfect win/loss records.
    - Mean Centering to stabilize the baseline across bootstrap iterations.
    - Ties are split into two weighted samples (0.5 win for A, 0.5 win for B).
    """
    models = pd.unique(battles_df[["model_a", "model_b"]].values.ravel("K"))
    model_to_idx = {model: i for i, model in enumerate(models)}

    X, Y, weights = [], [], []

    for _, row in battles_df.iterrows():
        vec = np.zeros(len(models))
        vec[model_to_idx[row["model_a"]]] = 1
        vec[model_to_idx[row["model_b"]]] = -1

        winner = row["winner"]

        if winner == "tie":
            # Split tie: A wins (weight 0.5) + B wins (weight 0.5)
            X.append(vec)
            Y.append(1)
            weights.append(0.5)

            X.append(vec)
            Y.append(0)
            weights.append(0.5)
        else:
            X.append(vec)
            Y.append(1 if winner == "model_a" else 0)
            weights.append(1.0)

    if len(np.unique(Y)) < 2:
        return {model: init_rating for model in models}

    lr = LogisticRegression(
        fit_intercept=False,
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        tol=1e-6,
        max_iter=10000,
    )

    try:
        lr.fit(X, Y, sample_weight=weights)
    except Exception as e:
        print(f"Warning: Logistic Regression failed. {e}")
        return {model: init_rating for model in models}

    scores = scale * lr.coef_[0] / np.log(base)
    scores = scores - np.mean(scores) + init_rating  # Mean Centering

    final_scores = {model: score for model, score in zip(models, scores)}

    for model in models:
        if model not in final_scores:
            final_scores[model] = init_rating

    return final_scores


def calculate_rtf(battles_df: pd.DataFrame, models: list):
    """Calculates the Median Real-Time Factor (RTF) for each model."""
    rtfs = {}
    for model in models:
        df_a = battles_df[battles_df["model_a"] == model]
        if not df_a.empty:
            rtf_a = df_a["duration_a"] / df_a["generation_time_a"]
        else:
            rtf_a = pd.Series(dtype=float)

        df_b = battles_df[battles_df["model_b"] == model]
        if not df_b.empty:
            rtf_b = df_b["duration_b"] / df_b["generation_time_b"]
        else:
            rtf_b = pd.Series(dtype=float)

        all_rtfs = pd.concat([rtf_a, rtf_b])
        all_rtfs = all_rtfs.replace([np.inf, -np.inf], np.nan).dropna()

        rtfs[model] = all_rtfs.median() if not all_rtfs.empty else np.nan
    return rtfs


def compute_hardware_ratios(logs_dir):
    """Compute hardware speed ratios relative to reference (A6000) from raw logs.

    Finds open-weights models that ran on multiple hardware types, computes
    the median RTF on each, and derives the global speed ratio.

    Usage:
        ma-leaderboard compute-baselines
        # Copy the HARDWARE_RTF_RATIOS output into config.py
    """
    import json
    from collections import defaultdict
    from pathlib import Path

    from .config import MODELS_METADATA, REFERENCE_HARDWARE

    open_models = {
        m
        for m, meta in MODELS_METADATA.items()
        if meta.get("access") == "Open weights"
    }

    # (model, hardware) -> [rtf, ...]
    data = defaultdict(list)

    logs_path = Path(logs_dir)
    if not logs_path.exists():
        print(f"Logs directory not found: {logs_dir}")
        return

    for f in logs_path.glob("*.json"):
        with open(f) as fh:
            try:
                d = json.load(fh)
            except Exception:
                continue

        raw_str = json.dumps(d)

        for side in ["a", "b"]:
            meta = d.get(f"{side}_metadata") or {}
            tag = (meta.get("system_key") or {}).get("system_tag")
            if tag not in open_models:
                continue

            dur = meta.get("duration")
            gw_start = meta.get("gateway_time_started")
            gw_end = meta.get("gateway_time_completed")

            if not (dur and gw_start and gw_end):
                continue

            gw_time = float(gw_end) - float(gw_start)
            if gw_time <= 0:
                continue

            hw = (
                "A5000"
                if "music-arena.org-new-a5000-machine" in raw_str
                else "A6000"
            )
            data[(tag, hw)].append(dur / gw_time)

    # Find hardware types
    all_hw = sorted({hw for _, hw in data.keys()})
    print(f"Reference hardware: {REFERENCE_HARDWARE}")
    print(f"Hardware types found: {all_hw}\n")

    # Per-model ratios
    print(f"{'Model':<22s}", end="")
    for hw in all_hw:
        print(f"  {hw:>12s}", end="")
    print(f"  {'Ratio':>10s}")
    print("-" * (22 + 14 * len(all_hw) + 12))

    per_model_ratios = defaultdict(list)
    for model in sorted(open_models):
        print(f"{model:<22s}", end="")
        ref_rtf = None
        model_rtfs = {}
        for hw in all_hw:
            vals = data.get((model, hw), [])
            med = np.median(vals) if vals else float("nan")
            model_rtfs[hw] = med
            if hw == REFERENCE_HARDWARE and vals:
                ref_rtf = med
            n = len(vals)
            print(f"  {med:>8.3f} ({n:>3d})", end="")

        for hw in all_hw:
            if hw != REFERENCE_HARDWARE and ref_rtf and not np.isnan(
                model_rtfs.get(hw, float("nan"))
            ):
                ratio = model_rtfs[hw] / ref_rtf
                per_model_ratios[hw].append(ratio)
                print(f"  {ratio:>10.3f}", end="")
        print()

    # Global ratios
    print(f"\n--- Global Hardware Ratios (for config.py) ---\n")
    print("HARDWARE_RTF_RATIOS = {")
    print(f'    "{REFERENCE_HARDWARE}": 1.0,')
    for hw in all_hw:
        if hw == REFERENCE_HARDWARE:
            continue
        if per_model_ratios[hw]:
            global_ratio = np.median(per_model_ratios[hw])
            n = len(per_model_ratios[hw])
            print(f'    "{hw}": {global_ratio:.3f},  # from {n} models')
    print("}")
