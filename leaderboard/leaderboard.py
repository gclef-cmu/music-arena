# leaderboard.py
import pandas as pd
import numpy as np
from tqdm import tqdm
from scoring import compute_arena_score, calculate_rtf

def compute_bootstrap_ci(battles_df, n_resamples=100):
    """Calculates 95% confidence intervals for Arena Scores using bootstrapping."""
    print(f"Computing bootstrap CIs with {n_resamples} resamples...")
    
    all_scores = {model: [] for model in pd.unique(battles_df[['model_a', 'model_b']].values.ravel('K'))}

    for i in tqdm(range(n_resamples), desc="Bootstrap Resampling"):
        # Create a bootstrap sample by resampling with replacement
        sample_df = battles_df.sample(n=len(battles_df), replace=True)
        
        # Calculate scores for the sample
        scores = compute_arena_score(sample_df)
        
        for model, score in scores.items():
            all_scores[model].append(score)
            
    # Calculate the 2.5th and 97.5th percentiles for the 95% CI
    cis = {}
    for model, score_distribution in all_scores.items():
        if score_distribution:
            lower = np.percentile(score_distribution, 2.5)
            upper = np.percentile(score_distribution, 97.5)
            cis[model] = (lower, upper)
    return cis

def generate_leaderboard(battles_df, models_metadata, leaderboard_type="instrumental"):
    """
    Generates the leaderboard DataFrame with corrected filtering logic and includes confidence intervals.
    """
    # Identify the set of models that support lyrics
    vocal_models = {m for m, meta in models_metadata.items() if meta.get("supports_lyrics")}

    if leaderboard_type == "vocal":
        # Vocal leaderboard: only battles where BOTH models are vocal-supporting
        filtered_df = battles_df[
            battles_df['model_a'].isin(vocal_models) & battles_df['model_b'].isin(vocal_models)
        ].copy()
    else:  # instrumental
        # Instrumental leaderboard: ALL battles EXCEPT those between two vocal-supporting models
        filtered_df = battles_df[
            ~(battles_df['model_a'].isin(vocal_models) & battles_df['model_b'].isin(vocal_models))
        ].copy()

    if filtered_df.shape[0] < 10:
        print(f"Not enough data to generate {leaderboard_type} leaderboard.")
        return pd.DataFrame()
    
    models = pd.unique(filtered_df[['model_a', 'model_b']].values.ravel('K'))
    
    # Calculate main scores, CIs, RTF, and votes on the filtered data
    scores = compute_arena_score(filtered_df)
    confidence_intervals = compute_bootstrap_ci(filtered_df[filtered_df['winner'] != 'tie'])
    rtfs = calculate_rtf(filtered_df, models)
    votes = pd.concat([filtered_df['model_a'], filtered_df['model_b']]).value_counts()
    
    data = []
    for model in models:
        main_score = scores.get(model)
        ci = confidence_intervals.get(model)
        ci_str = f"+{(ci[1] - main_score):.1f} / -{(main_score - ci[0]):.1f}" if ci and main_score is not None else "N/A"

        # Combine all data points
        model_data = {
            "Model": model, 
            "Arena Score": main_score, 
            "95% CI": ci_str,
            "# Votes": votes.get(model, 0), 
            "Generation Speed (RTF)": rtfs.get(model)
        }
        model_data.update(models_metadata.get(model, {}))
        data.append(model_data)

    df = pd.DataFrame(data).dropna(subset=["Arena Score"]).sort_values("Arena Score", ascending=False).reset_index(drop=True)
    df.index += 1
    df = df.rename_axis("Rank")
    
    # Formatting
    df['Arena Score'] = df['Arena Score'].round(1)
    if 'Generation Speed (RTF)' in df.columns:
      df['Generation Speed (RTF)'] = df['Generation Speed (RTF)'].round(2)

    return df