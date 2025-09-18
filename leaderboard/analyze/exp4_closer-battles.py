import sys, os
import pandas as pd
from tqdm import tqdm
from scipy.stats import spearmanr
import matplotlib.pyplot as plt
import seaborn as sns
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import BATTLE_LOGS_DIR, MODELS_METADATA
from scoring import compute_arena_score
from analysis import sum_listen_time
from data_loader import parse_logs, load_all_raw_logs

OUTPUT_DIR = "outputs/analysis"
KNOWN_MODELS = set(MODELS_METADATA.keys())

def calculate_engagement_data(raw_logs, scores):
    """Calculates data for correlation between score difference and listening time."""
    print("\n--- 🧐 Calculating data for: Arena Score Difference vs. Listening Time ---")
    analysis_data = []
    for log in tqdm(raw_logs, desc="Processing listening time"):
        if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
            try:
                model_a = log["a_metadata"]["system_key"]["system_tag"]
                model_b = log["b_metadata"]["system_key"]["system_tag"]
                
                if model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                    continue
                
                if model_a not in scores or model_b not in scores:
                    continue

                score_diff = abs(scores[model_a] - scores[model_b])
                time_a = sum_listen_time(log["vote"].get("a_listen_data", []))
                time_b = sum_listen_time(log["vote"].get("b_listen_data", []))
                total_listen_time = time_a + time_b

                analysis_data.append({
                    "score_difference": score_diff,
                    "total_listen_time": total_listen_time
                })
            except (KeyError, TypeError):
                continue
    
    if not analysis_data:
        print("No valid data for listening time correlation.")
        return pd.DataFrame()
        
    df = pd.DataFrame(analysis_data)

    Q1 = df['total_listen_time'].quantile(0.25)
    Q3 = df['total_listen_time'].quantile(0.75)
    IQR = Q3 - Q1
    threshold = Q3 + 1.5 * IQR
    filtered_df = df[df['total_listen_time'] <= threshold]
    print(f"Removed {len(df) - len(filtered_df)} outliers from listening time (Threshold > {threshold:.2f}s).")
    return filtered_df

def calculate_swaps_data(raw_logs, scores):
    """Calculates data for correlation between score difference and number of swaps."""
    print("\n--- 🔄 Calculating data for: Arena Score Difference vs. Number of Swaps ---")
    analysis_data = []
    for log in tqdm(raw_logs, desc="Processing swaps"):
        if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
            try:
                model_a = log["a_metadata"]["system_key"]["system_tag"]
                model_b = log["b_metadata"]["system_key"]["system_tag"]

                if model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                    continue
                
                if model_a not in scores or model_b not in scores:
                    continue

                score_diff = abs(scores[model_a] - scores[model_b])
                
                vote_data = log["vote"]
                events_a = [e[0] for e in vote_data.get("a_listen_data", []) if isinstance(e, list) and len(e) > 0]
                events_b = [e[0] for e in vote_data.get("b_listen_data", []) if isinstance(e, list) and len(e) > 0]
                num_swaps = max(0, events_a.count('PLAY') + events_b.count('PLAY') - 1)

                analysis_data.append({
                    "score_difference": score_diff,
                    "num_swaps": num_swaps
                })
            except (KeyError, TypeError):
                continue
    
    if not analysis_data:
        print("No valid data for swap correlation.")
        return pd.DataFrame()
        
    return pd.DataFrame(analysis_data)

def plot_engagement_correlation(engagement_df):
    """Plots and saves the Total Listening Time vs. closeness correlation figure."""
    if engagement_df.empty: return

    print("\n--- 📊 Plotting Listening Time Correlation ---")
    spearman_corr, p_value = spearmanr(engagement_df['score_difference'], engagement_df['total_listen_time'])
    print(f"Spearman Correlation (Listen Time): {spearman_corr:.3f} (p-value: {p_value:.3f})")

    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(12, 8))
    
    sns.regplot(data=engagement_df, x='score_difference', y='total_listen_time',
                scatter_kws={'alpha':0.3, 's':50}, line_kws={'color':'red', 'linestyle':'--'})
    
    plt.title('Total Listening Time vs. Arena Score Difference', fontsize=16, weight='bold')
    plt.xlabel('Arena Score Difference', fontdict={'weight': 'bold', 'size': 12})
    plt.ylabel('Total Listening Time [s]', fontdict={'weight': 'bold', 'size': 12})
    
    plt.text(0.5, 0.95, f'Spearman correlation = {spearman_corr:.3f}', 
             ha='center', va='top', transform=plt.gca().transAxes, fontsize=14)
    
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, "exp4_closer-battles(listening-time).png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[INFO] Plot saved to {filename}")
    plt.close()

def plot_swaps_correlation(swaps_df):
    """Plots and saves the swaps vs. closeness correlation figure."""
    if swaps_df.empty: return
        
    print("\n--- 📊 Plotting Swaps Correlation ---")
    spearman_corr, p_value = spearmanr(swaps_df['score_difference'], swaps_df['num_swaps'])
    print(f"Spearman Correlation (Swaps): {spearman_corr:.3f} (p-value: {p_value:.3f})")

    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(12, 8))
    
    sns.regplot(data=swaps_df, x='score_difference', y='num_swaps', x_jitter=0.05,
                scatter_kws={'alpha':0.2, 's':50}, line_kws={'color':'blue', 'linestyle':'--'})
    
    plt.title('Number of Swaps vs. Arena Score Difference', fontsize=16, weight='bold')
    plt.xlabel('Arena Score Difference', fontdict={'weight': 'bold', 'size': 12})
    plt.ylabel('Number of Swaps', fontdict={'weight': 'bold', 'size': 12})
    plt.yticks(range(int(swaps_df['num_swaps'].max()) + 2))
    
    plt.text(0.5, 0.95, f'Spearman correlation = {spearman_corr:.3f}', 
             ha='center', va='top', transform=plt.gca().transAxes, fontsize=14)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, "exp4_closer-battles(swaps).png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[INFO] Plot saved to {filename}")
    plt.close()

if __name__ == "__main__":
    print("--- 🚀 Starting Full Correlation Analysis ---")
    
    all_raw_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
    battles_df, _ = parse_logs(BATTLE_LOGS_DIR)
    
    if battles_df.empty:
        print("Not enough battle data to compute scores. Exiting.")
    else:
        battles_df = battles_df[battles_df['model_a'].isin(KNOWN_MODELS) & battles_df['model_b'].isin(KNOWN_MODELS)]
        print(f"\nFiltered battles to {len(battles_df)} rows with known models.")

        scores = compute_arena_score(battles_df)
        print("\nSuccessfully computed Arena Scores for known models.")
        
        engagement_data = calculate_engagement_data(all_raw_logs, scores)
        swaps_data = calculate_swaps_data(all_raw_logs, scores)
        
        plot_engagement_correlation(engagement_data)
        plot_swaps_correlation(swaps_data)
        
        print("\n--- ✅ Analysis Complete ---")
        
"""
python analyze/exp4_closer-battles.py > analyze/exp4_closer-battles.txt
"""