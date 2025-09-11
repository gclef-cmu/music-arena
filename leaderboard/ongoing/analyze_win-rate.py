import os
import json
from tqdm import tqdm

# --- 설정 ---
BATTLE_LOGS_DIR = "battle_data"

# --- 헬퍼 함수 (이전과 동일) ---
def find_first_play_timestamp(listen_data: list) -> float:
    """
    listen_data 리스트에서 첫 번째 'PLAY' 이벤트의 타임스탬프를 찾습니다.
    """
    if not listen_data: return float('inf')
    play_timestamps = [ts for ev, ts in listen_data if ev == "PLAY"]
    return min(play_timestamps) if play_timestamps else float('inf')

# --- 메인 분석 함수 ---
def analyze_first_played_outcomes(log_dir: str):
    """
    먼저 재생된 트랙의 관점에서 승리/패배/무승부 횟수와 비율을 계산합니다.
    """
    print(f"Analyzing outcomes (Win/Loss/Tie) for the first-played track from: {log_dir}...")

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    win_count = 0
    loss_count = 0
    tie_count = 0
    total_battles_with_preference = 0

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Processing logs"):
        try:
            with open(os.path.join(log_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)

            vote_data = data.get("vote")
            preference = vote_data.get("preference") if vote_data else None
            
            # 유효한 preference가 있는 모든 로그를 분석 대상으로 함
            if not preference:
                continue

            a_listen_data = vote_data.get("a_listen_data")
            b_listen_data = vote_data.get("b_listen_data")

            first_play_a_time = find_first_play_timestamp(a_listen_data)
            first_play_b_time = find_first_play_timestamp(b_listen_data)

            first_played_track = None
            if first_play_a_time < first_play_b_time:
                first_played_track = "A"
            elif first_play_b_time < first_play_a_time:
                first_played_track = "B"
            else:
                # 유효한 첫 재생 이벤트가 없는 경우는 건너뜀
                continue

            # 결과 판별
            if preference == first_played_track:
                win_count += 1
            elif preference in ["TIE", "BOTH_BAD"]:
                tie_count += 1
            else: # 선호도가 다른 트랙인 경우 (패배)
                loss_count += 1
            
            total_battles_with_preference += 1

        except Exception:
            continue

    if total_battles_with_preference == 0:
        print("\nNo valid battle data found to analyze outcomes.")
        return

    # --- 승률/패배율/무승부율 계산 및 결과 출력 ---
    win_rate = (win_count / total_battles_with_preference) * 100
    loss_rate = (loss_count / total_battles_with_preference) * 100
    tie_rate = (tie_count / total_battles_with_preference) * 100

    print("\n--- Outcomes for the First-Played Track ---")
    print(f"Total Battles with Preference: {total_battles_with_preference}")
    print("-" * 43)
    # f-string 정렬을 사용하여 깔끔하게 출력
    print(f"Wins:   {win_count:<5} ({win_rate:.2f}%)")
    print(f"Losses: {loss_count:<5} ({loss_rate:.2f}%)")
    print(f"Ties:   {tie_count:<5} ({tie_rate:.2f}%)")
    print("-" * 43)


# --- 스크립트 실행 ---
if __name__ == "__main__":
    analyze_first_played_outcomes(BATTLE_LOGS_DIR)