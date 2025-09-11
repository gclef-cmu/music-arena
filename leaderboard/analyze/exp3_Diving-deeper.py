import os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration ---
BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"
MINIMUM_LISTEN_TIME = 4.0 # 최소 청취 시간 (초)

# --- Import model metadata for filtering ---
try:
    from config import MODELS_METADATA
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    print("Successfully imported model metadata for filtering.")
except ImportError:
    print("Warning: config.py not found. Cannot filter by known models.")
    KNOWN_MODELS = None

# --- Helper Functions ---
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

def find_first_play_timestamp(listen_data: list) -> float:
    """Finds the timestamp of the first 'PLAY' event."""
    if not listen_data: return float('inf')
    play_timestamps = [ts for ev, ts in listen_data if ev == "PLAY"]
    return min(play_timestamps) if play_timestamps else float('inf')

# --- Main Analysis Function ---
def run_combined_analysis(log_dir: str):
    print(f"Running combined analysis from directory: {log_dir}...")
    
    first_played_durations = []
    second_played_durations = []

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    
    for filename in tqdm(log_files, desc="Processing logs"):
        try:
            with open(os.path.join(log_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Condition 1: Must have a vote
            vote_data = data.get("vote")
            if not vote_data: continue

            # Condition 2: Both models must be known
            if KNOWN_MODELS:
                model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
                model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
                if not model_a or not model_b or model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                    continue
            
            a_listen_data = vote_data.get("a_listen_data", [])
            b_listen_data = vote_data.get("b_listen_data", [])

            duration_a = sum_listen_time(a_listen_data)
            duration_b = sum_listen_time(b_listen_data)
            
            # Condition 3: Both tracks must meet the minimum listening time
            if duration_a < MINIMUM_LISTEN_TIME or duration_b < MINIMUM_LISTEN_TIME:
                continue

            # Determine play order and append durations
            first_play_a = find_first_play_timestamp(a_listen_data)
            first_play_b = find_first_play_timestamp(b_listen_data)

            if first_play_a < first_play_b:
                first_played_durations.append(duration_a)
                second_played_durations.append(duration_b)
            elif first_play_b < first_play_a:
                first_played_durations.append(duration_b)
                second_played_durations.append(duration_a)

        except Exception:
            continue

    if not first_played_durations:
        print("\nNo data remaining after all filters. Cannot generate statistics.")
        return

    # --- Final Analysis & Visualization ---
    df = pd.DataFrame({
        'First-Played Track': pd.Series(first_played_durations), 
        'Second-Played Track': pd.Series(second_played_durations)
    }).dropna()

    # IQR Outlier Removal
    Q1 = df.quantile(0.25); Q3 = df.quantile(0.75); IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    filtered_df = df[(df <= upper_bound)].dropna()
    
    # ** IQR 이상치가 제거된 데이터의 통계를 출력 **
    print(f"\n--- Statistics for {len(filtered_df)} Battles (After IQR Outlier Removal) ---")
    print(f"Removed {len(df) - len(filtered_df)} rows as outliers.")
    print(filtered_df.describe().round(2))

    # --- Plotting (Updated Style) ---
    print("\n--- 📊 Plotting Listening Time Distribution ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7), sharey=True)

    # Column names for convenience
    col1 = 'First-Played Track'
    col2 = 'Second-Played Track'

    # --- Plot for the First-Played Track ---
    iqr1 = filtered_df[col1].quantile(0.75) - filtered_df[col1].quantile(0.25)
    bin_width1 = 2 * iqr1 / (len(filtered_df[col1])**(1/3)) if len(filtered_df[col1]) > 0 else 1
    bins1 = int((filtered_df[col1].max() - filtered_df[col1].min()) / bin_width1) if bin_width1 > 0 else 20

    sns.histplot(data=filtered_df, x=col1, bins=bins1, ax=ax1, kde=True)
    ax1.set_title('First-Played Track Distribution', fontsize=16, weight='bold')
    ax1.set_xlabel('Listening Time [s]', fontdict={'weight': 'bold', 'size': 12})
    ax1.set_ylabel('Number of Battles', fontdict={'weight': 'bold', 'size': 12})
    ax1.axvline(filtered_df[col1].median(), color='red', linestyle='--', label=f"Median: {filtered_df[col1].median():.1f}s")
    ax1.axvline(upper_bound[col1], color='purple', linestyle=':', label=f"Outlier Threshold: {upper_bound[col1]:.1f}s")
    ax1.legend(fontsize=14, loc='upper center')

    # --- Plot for the Second-Played Track ---
    iqr2 = filtered_df[col2].quantile(0.75) - filtered_df[col2].quantile(0.25)
    bin_width2 = 2 * iqr2 / (len(filtered_df[col2])**(1/3)) if len(filtered_df[col2]) > 0 else 1
    bins2 = int((filtered_df[col2].max() - filtered_df[col2].min()) / bin_width2) if bin_width2 > 0 else 20
    
    sns.histplot(data=filtered_df, x=col2, bins=bins2, ax=ax2, kde=True, color='orange')
    ax2.set_title('Second-Played Track Distribution', fontsize=16, weight='bold')
    ax2.set_xlabel('Listening Time [s]', fontdict={'weight': 'bold', 'size': 12})
    ax2.set_ylabel('') # Remove y-axis label for clarity
    ax2.axvline(filtered_df[col2].median(), color='red', linestyle='--', label=f"Median: {filtered_df[col2].median():.1f}s")
    ax2.axvline(upper_bound[col2], color='purple', linestyle=':', label=f"Outlier Threshold: {upper_bound[col2]:.1f}s")
    ax2.legend(fontsize=14, loc='upper center')
    
    fig.suptitle('Listening Time Distribution by Play Order (Outliers Removed)', fontsize=20, weight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    filename = os.path.join(OUTPUT_DIR, "listening_time_by_play_order.png")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Final distribution plot saved to {filename}")
    plt.close()

if __name__ == "__main__":
    run_combined_analysis(BATTLE_LOGS_DIR)