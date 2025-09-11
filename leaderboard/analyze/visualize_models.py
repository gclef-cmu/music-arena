import os
import json
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr

# --- 설정 ---
BATTLE_LOGS_DIR = "battle_data"
OUTPUT_DIR = "outputs/analysis"
MIN_GAMES_FOR_ANALYSIS = 10 

# --- 헬퍼 함수 ---
def sum_listen_time_official(listen_data: list) -> float:
    last_play_timestamp = None
    total_time = 0.0
    if not listen_data: return 0.0
    for event, timestamp in listen_data:
        if event == "PLAY": last_play_timestamp = timestamp
        elif event in ["PAUSE", "TICK"] and last_play_timestamp is not None:
            play_time = timestamp - last_play_timestamp
            if play_time > 0: total_time += play_time
            if event == "PAUSE": last_play_timestamp = None
            else: last_play_timestamp = timestamp
    return total_time

def run_full_analysis_with_tables(log_dir: str):
    print(f"Running full analysis from: {log_dir}...")
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found."); return

    # --- 1. 통합 데이터 수집 ---
    battle_records = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    for filename in tqdm(log_files, desc="Processing logs"):
        try:
            with open(os.path.join(log_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
            prompt_details = data.get("prompt_detailed", {})
            is_instrumental = prompt_details.get("instrumental")
            if is_instrumental is None: continue
            vote_data = data.get("vote")
            if not vote_data: continue
            duration_a = sum_listen_time_official(vote_data.get("a_listen_data"))
            duration_b = sum_listen_time_official(vote_data.get("b_listen_data"))
            if duration_a < 4 or duration_b < 4: continue
            model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
            model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
            preference = vote_data.get("preference")
            if not model_a or not model_b or not preference: continue
            prompt_type = "Instrumental" if is_instrumental else "Vocal"
            battle_records.append({
                "model_a": model_a, "model_b": model_b,
                "duration_a": duration_a, "duration_b": duration_b,
                "preference": preference, "prompt_type": prompt_type
            })
        except Exception:
            continue
    df_battles = pd.DataFrame(battle_records)

    # (통계표 출력 부분은 이전과 동일하게 유지됩니다)
    listen_records = []
    for _, row in df_battles.iterrows():
        listen_records.append({'model': row['model_a'], 'duration': row['duration_a'], 'prompt_type': row['prompt_type']})
        listen_records.append({'model': row['model_b'], 'duration': row['duration_b'], 'prompt_type': row['prompt_type']})
    df_listen = pd.DataFrame(listen_records)
    
    print("\n\n--- Detailed Listening Time Statistics ---")
    for p_type in ["Instrumental", "Vocal"]:
        df_subset = df_listen[df_listen['prompt_type'] == p_type]
        if df_subset.empty:
            print(f"\nNo data found for {p_type} Prompts.")
            continue
        print(f"\n{'='*20} Statistics for {p_type} Prompts {'='*20}")
        per_model_stats = df_subset.groupby('model')['duration'].describe()
        total_stats = df_subset['duration'].describe().to_frame().T
        total_stats.index = ['Total']
        final_stats_table = pd.concat([per_model_stats, total_stats])
        print(final_stats_table.round(2).sort_values(by='50%', ascending=False).to_string())

    # --- 3. 모델별 승률 분석 ---
    outcome_records = []
    for _, row in df_battles.iterrows():
        if row['preference'] in ['A', 'B']:
            outcome_records.append({'model': row['model_a'], 'prompt_type': row['prompt_type'], 'outcome': 1 if row['preference'] == 'A' else 0})
            outcome_records.append({'model': row['model_b'], 'prompt_type': row['prompt_type'], 'outcome': 1 if row['preference'] == 'B' else 0})
    df_outcomes = pd.DataFrame(outcome_records)

    win_rate_stats = df_outcomes.groupby(['model', 'prompt_type'])['outcome'].agg(['sum', 'count']).reset_index()
    win_rate_stats.rename(columns={'sum': 'wins', 'count': 'total_games'}, inplace=True)
    win_rate_stats['win_rate'] = win_rate_stats['wins'] / win_rate_stats['total_games']
    df_win_rate = win_rate_stats[['model', 'prompt_type', 'win_rate', 'total_games']]

    # --- 4. 상관관계 분석 ---
    df_median_listen = df_listen.groupby(['model', 'prompt_type'])['duration'].median().reset_index()
    df_median_listen.rename(columns={'duration': 'median_duration'}, inplace=True)
    df_final = pd.merge(df_median_listen, df_win_rate, on=['model', 'prompt_type'])
    df_final = df_final[df_final['total_games'] >= MIN_GAMES_FOR_ANALYSIS].copy()

    print(f"\n\n{'='*20} Correlation Analysis: Listening Time vs. Win Rate {'='*20}")
    print(f"Analysis is based on model performances with at least {MIN_GAMES_FOR_ANALYSIS} games in each category.")
    
    plt.figure(figsize=(14, 10))
    
    # --- 수정된 부분 시작 ---
    
    # 1. 마커 모양을 직접 지정하는 딕셔너리 생성
    markers = {"Instrumental": "o", "Vocal": "^"}
    
    ax = sns.scatterplot(
        data=df_final, 
        x='median_duration', 
        y='win_rate', 
        hue='prompt_type', 
        alpha=0.8, 
        style='prompt_type',
        markers=markers, # 마커 지정
        size='total_games', 
        sizes=(50, 500)
    )
    # --- 수정 끝 ---

    for i, row in df_final.iterrows():
        plt.text(row['median_duration'] + 0.5, row['win_rate'], row['model'], fontsize=14)
        
    plt.title('Model Win Rate vs. Median Listening Time', fontsize=18, weight='bold')
    plt.xlabel('Median Listening Time [s]', fontdict={'weight': 'bold', 'size': 16})
    plt.xticks(fontsize=12)
    plt.ylabel('Win Rate', fontdict={'weight': 'bold', 'size': 16})
    plt.yticks(fontsize=12)
    plt.grid(True)

    # --- 수정된 부분 시작 ---
    # 2. 범례(legend)를 재구성하여 'total_games'에 대한 범례를 제거
    handles, labels = ax.get_legend_handles_labels()
    # 'prompt_type'에 대한 핸들과 라벨만 필터링 (보통 리스트의 앞부분에 위치)
    type_legend_indices = [i for i, label in enumerate(labels) if label in ["Prompt Type", "Instrumental", "Vocal"]]
    type_legend_handles = [handles[i] for i in type_legend_indices]
    type_legend_labels = [labels[i] for i in type_legend_indices]
    ax.legend(type_legend_handles, type_legend_labels, title='Prompt Type', title_fontsize=16, fontsize=14)
    # --- 수정 끝 ---
    
    instrumental_subset = df_final[df_final['prompt_type'] == 'Instrumental']
    vocal_subset = df_final[df_final['prompt_type'] == 'Vocal']
    if len(instrumental_subset) > 1:
        corr_instr, p_instr = pearsonr(instrumental_subset['median_duration'], instrumental_subset['win_rate'])
        print(f"\nPearson Correlation (Instrumental): r={corr_instr:.4f}, p-value={p_instr:.4f}")
    if len(vocal_subset) > 1:
        corr_vocal, p_vocal = pearsonr(vocal_subset['median_duration'], vocal_subset['win_rate'])
        print(f"Pearson Correlation (Vocal): r={corr_vocal:.4f}, p-value={p_vocal:.4f}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, "win_rate_vs_listen_time_final.png")
    plt.savefig(filename, dpi=300)
    print(f"\n[INFO] Final correlation plot saved to {filename}")
    plt.close()

# --- 스크립트 실행 ---
if __name__ == "__main__":
    run_full_analysis_with_tables(BATTLE_LOGS_DIR)