import os
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from tqdm import tqdm
from config import METADATA_DOWNLOAD_DIR

def sum_listen_time(listen_data: list) -> float:
    """Calculates the total listening time from a listen_data log."""
    last_play_time = None; total_time = 0
    if not listen_data: return 0
    for event_data in listen_data:
        if isinstance(event_data, list) and len(event_data) == 2:
            event, timestamp = event_data
            if event == "PLAY":
                if last_play_time is None: last_play_time = timestamp
            elif event in ["PAUSE", "STOP", "TICK"]:
                if last_play_time is not None: total_time += timestamp - last_play_time
                last_play_time = timestamp if event == "TICK" else None
    return total_time

def calculate_swaps(vote_data: dict) -> int:
    """Calculates the number of times a user swapped between tracks."""
    if not vote_data.get("a_listen_data") or not vote_data.get("b_listen_data"):
        return 0

    # Add track identifier ('A' or 'B') to each event
    events_a = [(ts, 'A') for _, ts in vote_data["a_listen_data"] if _ == 'PLAY']
    events_b = [(ts, 'B') for _, ts in vote_data["b_listen_data"] if _ == 'PLAY']
    
    # Combine and sort all PLAY events by timestamp
    all_play_events = sorted(events_a + events_b)
    
    swaps = 0
    last_track = None
    for _, track in all_play_events:
        if last_track is not None and track != last_track:
            swaps += 1
        last_track = track
        
    return swaps

def compute_arena_score(battles_df: pd.DataFrame, init_rating=1000):
    """Calculates Arena Score for all models in the DataFrame."""
    models = pd.unique(battles_df[['model_a', 'model_b']].values.ravel('K'))
    model_to_idx = {model: i for i, model in enumerate(models)}
    
    battles_no_ties = battles_df[battles_df['winner'] != 'tie'].copy()
    if battles_no_ties.empty or len(battles_no_ties['winner'].unique()) < 2:
        return {model: init_rating for model in models}

    X, Y = [], []
    for _, row in battles_no_ties.iterrows():
        vec = np.zeros(len(models)); vec[model_to_idx[row['model_a']]] = 1; vec[model_to_idx[row['model_b']]] = -1
        X.append(vec)
        Y.append(1 if row['winner'] == 'model_a' else 0)

    lr = LogisticRegression(fit_intercept=False, penalty=None, tol=1e-8)
    lr.fit(X, Y)
    
    scores = 400 * lr.coef_[0] / np.log(10) + init_rating
    
    final_scores = {model: score for model, score in zip(models, scores)}
    for model in models:
        if model not in final_scores: final_scores[model] = init_rating
            
    return final_scores

def analyze_listening_behavior(log_dir: str):
    """
    Analyzes listening behavior from local logs, including swaps and correlation with leaderboard scores.
    """
    print(f"Analyzing listening behavior from directory: {log_dir}")
    
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    battle_details = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Parsing logs for analysis"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if data.get("vote") and data.get("a_metadata") and data.get("b_metadata"):
                model_a = data["a_metadata"]["system_key"]["system_tag"]
                model_b = data["b_metadata"]["system_key"]["system_tag"]
                pref = data["vote"]["preference"]
                winner = "tie"
                if pref == "A": winner = "model_a"
                elif pref == "B": winner = "model_b"

                battle_details.append({
                    "model_a": model_a,
                    "model_b": model_b,
                    "winner": winner,
                    "total_listen_time": sum_listen_time(data["vote"].get("a_listen_data", [])) + sum_listen_time(data["vote"].get("b_listen_data", [])),
                    "swaps": calculate_swaps(data["vote"])
                })
        except Exception:
            continue
            
    if not battle_details:
        print("No valid battle data found for analysis.")
        return

    battles_df = pd.DataFrame(battle_details)
    print(f"\nSuccessfully processed {len(battles_df)} voted battles.")

    # --- 1. Basic Swap Statistics ---
    print("\n--- 🎧 Basic Listening Behavior Stats ---")
    swap_stats = battles_df['swaps'].describe().round(2)
    print("How often users swap between tracks:")
    print(swap_stats)
    print("----------------------------------------")

    # --- 2. Correlation with Leaderboard Closeness ---
    print("\n--- 📈 Listening Behavior vs. Leaderboard Closeness ---")
    
    # First, calculate the leaderboard scores
    arena_scores = compute_arena_score(battles_df)
    
    # Add score difference to the DataFrame
    battles_df['score_a'] = battles_df['model_a'].map(arena_scores)
    battles_df['score_b'] = battles_df['model_b'].map(arena_scores)
    battles_df['score_diff'] = np.abs(battles_df['score_a'] - battles_df['score_b'])
    
    # Create bins for score differences
    bins = [0, 50, 150, np.inf]
    labels = ["Very Close Battle (<50)", "Moderate Battle (50-150)", "Distant Battle (>150)"]
    battles_df['closeness_group'] = pd.cut(battles_df['score_diff'], bins=bins, labels=labels, right=False)
    
    # Group by closeness and calculate average engagement
    correlation_results = battles_df.groupby('closeness_group', observed=False).agg(
        avg_total_listen_time=('total_listen_time', 'mean'),
        avg_swaps=('swaps', 'mean'),
        battle_count=('swaps', 'count')
    ).round(2)

    print("Engagement metrics based on Arena Score difference between models:")
    print(correlation_results)
    print("----------------------------------------------------------")


if __name__ == "__main__":
    analyze_listening_behavior(METADATA_DOWNLOAD_DIR)