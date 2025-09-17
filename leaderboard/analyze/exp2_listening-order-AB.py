import sys, os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"

try:
    from config import MODELS_METADATA
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    print("Successfully imported model metadata for filtering.")
except ImportError:
    print("Warning: config.py not found. Cannot filter by known models.")
    KNOWN_MODELS = None

def sum_listen_time(listen_data: list) -> float:
    last_play_time = None
    total_time = 0
    if not listen_data:
        return 0
    for event_data in listen_data:
        if isinstance(event_data, list) and len(event_data) == 2:
            event, timestamp = event_data
            if event == "PLAY":
                if last_play_time is None:
                    last_play_time = timestamp
            elif event in ["PAUSE", "STOP", "TICK"]:
                if last_play_time is not None:
                    total_time += timestamp - last_play_time
                last_play_time = timestamp if event == "TICK" else None
    return total_time

def analyze_and_visualize_listening_time(log_dir: str):

    print(f"Analyzing listening times from local directory: {log_dir}...")
    
    listen_times_a = []
    listen_times_b = []

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    
    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            has_vote = "vote" in data and data["vote"] is not None
            if not has_vote:
                continue

            if KNOWN_MODELS:
                model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
                model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
                if not model_a or not model_b or model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                    continue
                
            vote_data = data["vote"]
            if "a_listen_data" in vote_data and vote_data["a_listen_data"]:
                listen_times_a.append(sum_listen_time(vote_data["a_listen_data"]))
            if "b_listen_data" in vote_data and vote_data["b_listen_data"]:
                listen_times_b.append(sum_listen_time(vote_data["b_listen_data"]))
        except Exception:
            continue

    if not listen_times_a or not listen_times_b:
        print("No valid listening data found to analyze.")
        return

    df = pd.DataFrame({'Track A': listen_times_a, 'Track B': listen_times_b})

    print("\n--- Listening Time Statistics (Raw Data from Valid Battles) ---")
    print(df.describe().round(2))

    Q1 = df.quantile(0.25)
    Q3 = df.quantile(0.75)
    IQR = Q3 - Q1
    outlier_threshold = Q3 + 1.5 * IQR
    
    print("\n--- IQR-based Outlier Thresholds ---")
    print(outlier_threshold.round(2))
    print("--------------------------------------")

    filtered_df = df[
        (df['Track A'] <= outlier_threshold['Track A']) &
        (df['Track B'] <= outlier_threshold['Track B'])
    ]
    
    print(f"\n--- Statistics after removing outliers ---")
    print(f"Removed {len(df) - len(filtered_df)} rows containing outliers.")
    print(filtered_df.describe().round(2))

    print("\n--- 📊 Plotting Listening Time Distribution ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7), sharey=True)

    iqr_a = filtered_df['Track A'].quantile(0.75) - filtered_df['Track A'].quantile(0.25)
    bin_width_a = 2 * iqr_a / (len(filtered_df['Track A'])**(1/3)) if len(filtered_df['Track A']) > 0 else 1
    bins_a = int((filtered_df['Track A'].max() - filtered_df['Track A'].min()) / bin_width_a) if bin_width_a > 0 else 20

    sns.histplot(data=filtered_df, x='Track A', bins=bins_a, ax=ax1, kde=True)
    ax1.set_title('Track A Listening Time Distribution', fontsize=16, weight='bold')
    ax1.set_xlabel('Listen Time [s]', fontdict={'weight': 'bold', 'size': 12})
    ax1.set_ylabel('Number of Battles', fontdict={'weight': 'bold', 'size': 12})
    ax1.axvline(filtered_df['Track A'].median(), color='red', linestyle='--', label=f"Median: {filtered_df['Track A'].median():.1f}s")
    ax1.axvline(outlier_threshold['Track A'], color='purple', linestyle=':', label=f"IQR Outlier Threshold: {outlier_threshold['Track A']:.1f}s")
    ax1.legend(fontsize=14, loc='upper center')

    iqr_b = filtered_df['Track B'].quantile(0.75) - filtered_df['Track B'].quantile(0.25)
    bin_width_b = 2 * iqr_b / (len(filtered_df['Track B'])**(1/3)) if len(filtered_df['Track B']) > 0 else 1
    bins_b = int((filtered_df['Track B'].max() - filtered_df['Track B'].min()) / bin_width_b) if bin_width_b > 0 else 20

    sns.histplot(data=filtered_df, x='Track B', bins=bins_b, ax=ax2, kde=True, color='orange')
    ax2.set_title('Track B Listening Time Distribution', fontsize=16, weight='bold')
    ax2.set_xlabel('Listen Time [s]', fontdict={'weight': 'bold', 'size': 12})
    ax2.set_ylabel('')
    ax2.axvline(filtered_df['Track B'].median(), color='red', linestyle='--', label=f"Median: {filtered_df['Track B'].median():.1f}s")
    ax2.axvline(outlier_threshold['Track B'], color='purple', linestyle=':', label=f"IQR Outlier Threshold: {outlier_threshold['Track B']:.1f}s")
    ax2.legend(fontsize=14, loc='upper center')

    fig.suptitle('Listening Time Distribution (IQR Outliers Removed)', fontsize=20, weight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    filename = "exp2_listening-order-AB.png"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Distribution plot (IQR filtered) saved to {os.path.join(OUTPUT_DIR, filename)}")
    plt.close()

if __name__ == "__main__":
    analyze_and_visualize_listening_time(BATTLE_LOGS_DIR)
    
"""
python analyze/exp2_listening-order-AB.py > analyze/exp2_listening-order-AB.txt
"""