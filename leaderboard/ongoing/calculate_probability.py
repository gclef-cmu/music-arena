import os
import json
from tqdm import tqdm

# --- 설정 ---
# 실제 battle log 데이터가 있는 디렉토리 경로를 지정해주세요.
BATTLE_LOGS_DIR = "battle_data" 

# --- 헬퍼 함수 ---
def find_first_play_timestamp(listen_data: list) -> float:
    """
    listen_data 리스트에서 첫 번째 'PLAY' 이벤트의 타임스탬프를 찾습니다.
    'PLAY' 이벤트가 없으면 무한대(inf) 값을 반환하여 비교에서 항상 지도록 합니다.
    """
    if not listen_data:
        return float('inf')

    play_timestamps = [timestamp for event, timestamp in listen_data if event == "PLAY"]
    return min(play_timestamps) if play_timestamps else float('inf')

# --- 메인 분석 함수 ---
def calculate_first_choice_probability(log_dir: str):
    """
    유효 데이터에 대해 Track A 또는 Track B가 먼저 선택될 확률을 계산합니다.
    """
    print(f"Calculating first choice probability from directory: {log_dir}...")

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    # 카운터 초기화
    a_chosen_first_count = 0
    b_chosen_first_count = 0
    skipped_logs_count = 0

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 1. 유효 데이터 필터링 ('vote' 객체 존재 여부 확인)
            vote_data = data.get("vote")
            if not vote_data:
                skipped_logs_count += 1
                continue

            a_listen_data = vote_data.get("a_listen_data")
            b_listen_data = vote_data.get("b_listen_data")

            # 2. 각 트랙의 첫 'PLAY' 이벤트 타임스탬프 탐색
            first_play_a_time = find_first_play_timestamp(a_listen_data)
            first_play_b_time = find_first_play_timestamp(b_listen_data)

            # 3. 타임스탬프 비교를 통해 첫 선택 판별 및 카운트
            if first_play_a_time < first_play_b_time:
                a_chosen_first_count += 1
            elif first_play_b_time < first_play_a_time:
                b_chosen_first_count += 1
            else:
                # PLAY 이벤트가 없거나 타임스탬프가 동일한 예외적인 경우
                skipped_logs_count += 1
                
        except (json.JSONDecodeError, TypeError, KeyError):
            skipped_logs_count += 1
            continue

    # --- 4. 확률 계산 및 결과 출력 ---
    total_valid_battles = a_chosen_first_count + b_chosen_first_count
    
    if total_valid_battles == 0:
        print("\nAnalysis complete. No valid battles found to calculate probabilities.")
        return

    prob_a_first = a_chosen_first_count / total_valid_battles
    prob_b_first = b_chosen_first_count / total_valid_battles

    print("\n--- First Choice Probability Analysis ---")
    print(f"Total Valid Battles Analyzed: {total_valid_battles}")
    print(f"Skipped Logs (unvoted or no play data): {skipped_logs_count}")
    print("-" * 39)
    print(f"Count(A chosen first): {a_chosen_first_count}")
    print(f"Count(B chosen first): {b_chosen_first_count}")
    print("-" * 39)
    print(f"P(A is chosen first): {prob_a_first:.4f} or {prob_a_first:.2%}")
    print(f"P(B is chosen first): {prob_b_first:.4f} or {prob_b_first:.2%}")
    print("-----------------------------------------")


# --- 스크립트 실행 ---
if __name__ == "__main__":
    # 이 스크립트를 실행하기 전에 BATTLE_LOGS_DIR 변수를
    # 실제 데이터가 있는 디렉토리 경로로 변경해주세요.
    calculate_first_choice_probability(BATTLE_LOGS_DIR)