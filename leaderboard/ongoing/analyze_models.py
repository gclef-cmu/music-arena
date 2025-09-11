import os
import json
import pandas as pd
from collections import Counter
from tqdm import tqdm

# --- 설정 ---
BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"

# --- 메인 분석 함수 ---
def analyze_model_appearance_frequency(log_dir: str):
    """
    각 모델이 Track A와 Track B 슬롯에 얼마나 자주 나타나는지 빈도와 비율을 분석합니다.
    """
    print(f"Analyzing model appearance frequency from: {log_dir}...")

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    # Counter를 사용하여 모델별 빈도수를 쉽게 계산합니다.
    model_counts_A = Counter()
    model_counts_B = Counter()
    total_battles_processed = 0

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]

    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # .get()을 연쇄적으로 사용하여 키가 없는 경우에도 오류 없이 안전하게 접근합니다.
            model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
            model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")

            # 두 트랙 모두에 모델 정보가 있는 유효한 배틀만 카운트합니다.
            if model_a and model_b:
                total_battles_processed += 1
                model_counts_A[model_a] += 1
                model_counts_B[model_b] += 1

        except Exception:
            continue

    if total_battles_processed == 0:
        print("No valid battle logs with model metadata found.")
        return

    # --- 결과 처리 및 출력 ---
    # A 또는 B에 한 번이라도 등장한 모든 모델의 목록을 만듭니다.
    all_models = sorted(list(set(model_counts_A.keys()) | set(model_counts_B.keys())))

    results_data = []
    for model in all_models:
        count_a = model_counts_A.get(model, 0)
        percent_a = (count_a / total_battles_processed) * 100
        count_b = model_counts_B.get(model, 0)
        percent_b = (count_b / total_battles_processed) * 100
        
        results_data.append({
            "Model": model,
            "Track A Count": count_a,
            "Track A %": f"{percent_a:.2f}%",
            "Track B Count": count_b,
            "Track B %": f"{percent_b:.2f}%"
        })

    # Pandas DataFrame으로 변환하여 보기 좋게 출력합니다.
    df_results = pd.DataFrame(results_data)
    # Track A에 많이 등장한 순서로 정렬합니다.
    df_results = df_results.sort_values(by="Track A Count", ascending=False)

    print(f"\n--- Model Appearance Frequency (Total Battles Analyzed: {total_battles_processed}) ---")
    # to_string()을 사용하여 전체 표가 잘리지 않고 출력되도록 합니다.
    print(df_results.to_string(index=False))

    # 결과를 CSV 파일로 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "model_appearance_frequency.csv")
    df_results.to_csv(output_path, index=False)
    print(f"\n[INFO] Full results have been saved to: {output_path}")


# --- 스크립트 실행 ---
if __name__ == "__main__":
    analyze_model_appearance_frequency(BATTLE_LOGS_DIR)