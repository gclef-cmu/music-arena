import os
import json
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# --- 설정 ---
BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"

# --- 헬퍼 함수 ---

def sum_listen_time_official(listen_data: list) -> float:
    """
    arena.py의 공식 로직을 기반으로 총 청취 시간을 계산합니다.
    TICK과 TICK 사이의 시간을 누적하여 계산합니다. STOP 이벤트는 무시됩니다.
    """
    last_play_timestamp = None
    total_time = 0.0
    if not listen_data:
        return 0.0
        
    for event, timestamp in listen_data:
        # JSON에서 읽은 이벤트는 문자열이므로, 문자열로 비교합니다.
        if event == "PLAY":
            last_play_timestamp = timestamp
        elif event in ["PAUSE", "TICK"] and last_play_timestamp is not None:
            play_time = timestamp - last_play_timestamp
            if play_time > 0:
                total_time += play_time
            
            if event == "PAUSE":
                last_play_timestamp = None
            else:  # event == "TICK"
                last_play_timestamp = timestamp
    return total_time

def find_first_play_timestamp(listen_data: list) -> float:
    if not listen_data: return float('inf')
    play_timestamps = [ts for ev, ts in listen_data if ev == "PLAY"]
    return min(play_timestamps) if play_timestamps else float('inf')

# --- 메인 분석 함수 ---
def run_final_analysis(log_dir: str):
    print(f"Running final analysis with official logic from: {log_dir}...")
    
    first_played_durations = []
    second_played_durations = []
    failed_4s_filter_logs = []

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    
    for filename in tqdm(log_files, desc="Processing logs"):
        try:
            with open(os.path.join(log_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)

            vote_data = data.get("vote")
            if not vote_data: continue
                
            a_listen_data = vote_data.get("a_listen_data")
            b_listen_data = vote_data.get("b_listen_data")

            # --- 공식 계산 함수 사용 ---
            duration_a = sum_listen_time_official(a_listen_data)
            duration_b = sum_listen_time_official(b_listen_data)
            
            if duration_a < 4 or duration_b < 4:
                failed_4s_filter_logs.append({
                    "filename": filename,
                    "uuid": data.get("uuid", "N/A"),
                    "duration_a": round(duration_a, 2),
                    "duration_b": round(duration_b, 2)
                })
                continue

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
    
    # (추적 결과 보고 부분은 이전과 동일)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # ...

    if not first_played_durations:
        print("No valid data remaining after filters.")
        return

    # --- 최종 분석 ---
    df = pd.DataFrame({
        'First-Played': pd.Series(first_played_durations), 
        'Second-Played': pd.Series(second_played_durations)
    }).dropna()

    print("\n--- Final Statistics (Official Logic, >= 4s Filter) ---")
    print(df.describe().round(2))

    Q1 = df.quantile(0.25)
    Q3 = df.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    filtered_df = df[
        (df['First-Played'] >= lower_bound['First-Played']) & (df['First-Played'] <= upper_bound['First-Played']) &
        (df['Second-Played'] >= lower_bound['Second-Played']) & (df['Second-Played'] <= upper_bound['Second-Played'])
    ]
    
    print(f"\nRemoved {len(df) - len(filtered_df)} rows as outliers.")
    print("\n--- Final Statistics (After IQR Outlier Removal) ---")
    print(filtered_df.describe().round(2))

    # --- 시각화 ---
    print("\n--- 📊 Plotting Final Listening Time Distribution ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7), sharey=True)

    # --- 수정된 부분 시작 ---

    # Plot 1: First-Played Track
    sns.histplot(data=filtered_df, x='First-Played', bins=30, ax=ax1, kde=True)
    ax1.set_title('First-Played Track Distribution', fontsize=16, weight='bold')
    ax1.set_xlabel('Listening Time (seconds)', fontsize=14)
    ax1.set_ylabel('Number of Battles', fontsize=14)
    ax1.axvline(filtered_df['First-Played'].median(), color='red', linestyle='--', label=f"Median: {filtered_df['First-Played'].median():.1f}s")
    # --- ADDED: IQR Threshold line ---
    ax1.axvline(upper_bound['First-Played'], color='green', linestyle=':', label=f"IQR Outlier Threshold: {upper_bound['First-Played']:.1f}s")
    # --- MODIFIED: Legend location ---
    ax1.legend(fontsize=14, loc='upper center')

    # Plot 2: Second-Played Track
    sns.histplot(data=filtered_df, x='Second-Played', bins=30, ax=ax2, kde=True, color='orange')
    ax2.set_title('Second-Played Track Distribution', fontsize=16, weight='bold')
    ax2.set_xlabel('Listening Time (seconds)', fontsize=14)
    ax2.set_ylabel('')
    ax2.axvline(filtered_df['Second-Played'].median(), color='red', linestyle='--', label=f"Median: {filtered_df['Second-Played'].median():.1f}s")
    # --- ADDED: IQR Threshold line ---
    ax2.axvline(upper_bound['Second-Played'], color='green', linestyle=':', label=f"IQR Outlier Threshold: {upper_bound['Second-Played']:.1f}s")
    # --- MODIFIED: Legend location ---
    ax2.legend(fontsize=14, loc='upper center')

    # --- 수정된 부분 끝 ---

    fig.suptitle('Listening Time Distribution by Play Order (IQR Outliers Removed)', fontsize=20, weight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    filename = os.path.join(OUTPUT_DIR, "listening_time_distribution_official_final.png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Final distribution plot saved to {filename}")
    plt.close()

# --- 스크립트 실행 ---
if __name__ == "__main__":
    run_final_analysis(BATTLE_LOGS_DIR)