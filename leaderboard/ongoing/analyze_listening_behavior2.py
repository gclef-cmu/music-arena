import os
import json
from tqdm import tqdm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# --- 설정 ---
BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"

# --- 헬퍼 함수 ---

def calculate_total_listen_time(listen_data):
    """
    listen_data 리스트에서 총 청취 시간을 계산합니다.
    PLAY/STOP, PLAY/PAUSE 쌍을 찾아 시간을 합산합니다.
    """
    if not listen_data:
        return 0.0

    total_duration = 0.0
    play_start_time = None

    for event, timestamp in listen_data:
        if event == "PLAY" and play_start_time is None:
            play_start_time = timestamp
        elif event in ["STOP", "PAUSE"] and play_start_time is not None:
            duration = timestamp - play_start_time
            total_duration += duration
            play_start_time = None # 다음 PLAY 이벤트를 위해 초기화

    return total_duration

def find_first_play_timestamp(listen_data):
    """
    listen_data 리스트에서 첫 번째 'PLAY' 이벤트의 타임스탬프를 찾습니다.
    """
    if not listen_data:
        return float('inf')
    play_timestamps = [timestamp for event, timestamp in listen_data if event == "PLAY"]
    return min(play_timestamps) if play_timestamps else float('inf')

# --- 메인 분석 함수 ---

def analyze_listen_time_by_play_order(log_dir: str):
    """
    먼저 재생된 트랙과 두 번째로 재생된 트랙의 총 청취 시간을 비교 분석하고 시각화합니다.
    """
    print("Analyzing listening time based on play order...")

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    first_played_durations = []
    second_played_durations = []
    
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            vote_data = data.get("vote")
            if not vote_data:
                continue

            a_listen_data = vote_data.get("a_listen_data")
            b_listen_data = vote_data.get("b_listen_data")

            # 1. 총 청취 시간 계산
            duration_A = calculate_total_listen_time(a_listen_data)
            duration_B = calculate_total_listen_time(b_listen_data)
            
            # 2. 먼저 재생된 트랙 판별
            first_play_A_time = find_first_play_timestamp(a_listen_data)
            first_play_B_time = find_first_play_timestamp(b_listen_data)

            # 3. 데이터 그룹화
            if first_play_A_time < first_play_B_time:
                first_played_durations.append(duration_A)
                second_played_durations.append(duration_B)
            elif first_play_B_time < first_play_A_time:
                first_played_durations.append(duration_B)
                second_played_durations.append(duration_A)

        except Exception:
            continue
            
    if not first_played_durations or not second_played_durations:
        print("Not enough data to perform analysis.")
        return

    # --- 4. 통계 분석 ---
    print("\n--- Statistical Analysis of Listening Time ---")
    mean_first = np.mean(first_played_durations)
    median_first = np.median(first_played_durations)
    mean_second = np.mean(second_played_durations)
    median_second = np.median(second_played_durations)

    print(f"First-Played Track: Mean={mean_first:.2f}s, Median={median_first:.2f}s")
    print(f"Second-Played Track: Mean={mean_second:.2f}s, Median={median_second:.2f}s")
    
    # 대응표본 T-검정 (Paired T-test)
    # 귀무가설(H0): 두 그룹의 평균 차이가 0이다.
    # 대립가설(H1): 두 그룹의 평균 차이가 0이 아니다.
    ttest_result = stats.ttest_rel(first_played_durations, second_played_durations)
    print(f"\nPaired T-test result: T-statistic={ttest_result.statistic:.4f}, P-value={ttest_result.pvalue}")

    if ttest_result.pvalue < 0.05:
        print("The P-value is less than 0.05, so we reject the null hypothesis.")
        print("Conclusion: The difference in listening time is statistically significant.")
    else:
        print("The P-value is not less than 0.05.")
        print("Conclusion: The difference in listening time is not statistically significant.")

    # --- 5. 시각화 ---
    print("\nGenerating visualization...")
    
    # 데이터프레임 생성
    df_list = []
    for duration in first_played_durations:
        df_list.append({'Play Order': 'First-Played Track', 'Listen Duration (s)': duration})
    for duration in second_played_durations:
        df_list.append({'Play Order': 'Second-Played Track', 'Listen Duration (s)': duration})
    df = pd.DataFrame(df_list)

    # 박스 플롯 생성
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(10, 6))
    sns.boxplot(x='Play Order', y='Listen Duration (s)', data=df, palette='viridis')
    
    plt.title('Comparison of Listening Duration by Play Order', fontsize=16)
    plt.xlabel('Track Play Order', fontsize=12)
    plt.ylabel('Total Listening Duration (seconds)', fontsize=12)
    
    # 결과 이미지 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "listen_duration_by_play_order.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    print(f"Visualization saved to: {output_path}")
    plt.show()

# --- 스크립트 실행 ---
if __name__ == "__main__":
    # 데모를 위한 더미 로그 파일 생성 (실제 환경에서는 이 부분 제거)
    if not os.path.exists(BATTLE_LOGS_DIR):
        os.makedirs(BATTLE_LOGS_DIR)
        # B를 먼저 재생했고, B를 더 오래 들은 케이스
        log1 = {"vote": {"a_listen_data": [["PLAY", 10], ["STOP", 15]], "b_listen_data": [["PLAY", 5], ["STOP", 20]]}}
        # A를 먼저 재생했고, A를 더 오래 들은 케이스
        log2 = {"vote": {"a_listen_data": [["PLAY", 30], ["STOP", 55]], "b_listen_data": [["PLAY", 60], ["STOP", 68]]}}
        with open(os.path.join(BATTLE_LOGS_DIR, "log1.json"), "w") as f: json.dump(log1, f)
        with open(os.path.join(BATTLE_LOGS_DIR, "log2.json"), "w") as f: json.dump(log2, f)
        
    analyze_listen_time_by_play_order(BATTLE_LOGS_DIR)