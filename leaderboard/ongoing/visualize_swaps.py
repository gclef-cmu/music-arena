import os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration ---
BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs/plots"
OUTLIER_CAP_SECONDS = 300  # 이상치로 간주할 최대 시간 (초)

def sum_listen_time(listen_data: list) -> float:
    """
    주어진 listen_data 로그로부터 총 청취 시간을 정확하게 계산합니다.
    """
    last_play_time = None
    total_time = 0
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

def analyze_and_plot_listening_distribution(log_dir: str):
    """
    로컬 로그를 분석하여 청취 시간 분포를 시각화하고, 확률과 카운트를 함께 표시합니다.
    """
    print(f"Analyzing listening times from directory: {log_dir}...")
    
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    listen_times_a, listen_times_b = [], []
    timestamps = []
    
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if data.get("vote"):
                vote_data = data["vote"]
                if "a_listen_data" in vote_data and vote_data["a_listen_data"]:
                    listen_times_a.append(sum_listen_time(vote_data["a_listen_data"]))
                if "b_listen_data" in vote_data and vote_data["b_listen_data"]:
                    listen_times_b.append(sum_listen_time(vote_data["b_listen_data"]))
                
                session_time = data.get("prompt_session", {}).get("create_time") or data.get("a_metadata", {}).get("gateway_time_completed")
                if session_time:
                    timestamps.append(datetime.fromtimestamp(session_time, tz=timezone.utc))
        except Exception:
            continue
            
    if not listen_times_a or not listen_times_b:
        print("No valid listening data found to analyze.")
        return

    # --- 이상치 제거 및 데이터프레임 생성 ---
    df_a = pd.DataFrame(listen_times_a, columns=['listen_time'])
    df_b = pd.DataFrame(listen_times_b, columns=['listen_time'])
    filtered_a = df_a[df_a['listen_time'] <= OUTLIER_CAP_SECONDS]
    filtered_b = df_b[df_b['listen_time'] <= OUTLIER_CAP_SECONDS]

    # --- 날짜 범위 문자열 생성 ---
    date_range_str = ""
    if timestamps:
        min_date = min(timestamps).strftime('%Y-%m-%d')
        max_date = max(timestamps).strftime('%Y-%m-%d')
        date_range_str = f"({min_date} to {max_date})"

    # --- 분포도 시각화 ---
    print("\n--- 📊 Plotting Listening Time Distribution ---")
    plt.style.use('seaborn-v0_8-ticks')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8), sharey=True)

    # Plot for Track A
    sns.histplot(data=filtered_a, x='listen_time', bins=60, ax=ax1, stat='probability', kde=True)
    ax1.set_title('Track A Listening Distribution', fontsize=18, weight='bold')
    ax1.set_xlabel('Listen Time (seconds)', fontsize=14)
    ax1.set_ylabel('Probability (Count)', fontsize=14)
    
    # Add count labels on top of bars for Track A
    for p in ax1.patches:
        height = p.get_height()
        count = int(height * len(filtered_a))
        ax1.text(p.get_x() + p.get_width() / 2., height + 0.005, f'({count})', ha='center', va='bottom', fontsize=9)

    # Plot for Track B
    sns.histplot(data=filtered_b, x='listen_time', bins=60, ax=ax2, stat='probability', kde=True, color='orange')
    ax2.set_title('Track B Listening Distribution', fontsize=18, weight='bold')
    ax2.set_xlabel('Listen Time (seconds)', fontsize=14)
    ax2.set_ylabel('')

    # Add count labels on top of bars for Track B
    for p in ax2.patches:
        height = p.get_height()
        count = int(height * len(filtered_b))
        ax2.text(p.get_x() + p.get_width() / 2., height + 0.005, f'({count})', ha='center', va='bottom', fontsize=9)

    fig.suptitle(f'Listening Time Distribution {date_range_str}', fontsize=22, weight='bold')
    sns.despine()
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, "listening_time_distribution.png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Distribution plot saved to {filename}")
    plt.close(fig)

if __name__ == "__main__":
    analyze_and_plot_listening_distribution(BATTLE_LOGS_DIR)