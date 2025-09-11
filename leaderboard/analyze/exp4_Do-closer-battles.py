# import os
# import json
# import pandas as pd
# import numpy as np
# from tqdm import tqdm
# from scipy.stats import pearsonr, spearmanr
# import matplotlib.pyplot as plt
# import seaborn as sns

# # Import from your existing modules
# from config import BATTLE_LOGS_DIR, MODELS_METADATA
# from scoring import compute_arena_score
# from analysis import sum_listen_time
# from data_loader import parse_logs, load_all_raw_logs

# def analyze_engagement_vs_closeness_correlation(raw_logs):
#     """
#     Analyzes and visualizes the correlation between leaderboard closeness
#     (Arena Score difference) and user engagement (total listening time).
#     """
#     print("\n--- 🧐 Analyzing Correlation between Arena Score Difference and Listening Time ---")
    
#     # 1. First, build a leaderboard to get scores for all models
#     battles_df, _ = parse_logs(BATTLE_LOGS_DIR) # Use the main parser
#     if battles_df.empty:
#         print("Not enough battle data to compute scores.")
#         return
    
#     scores = compute_arena_score(battles_df)
#     print("Successfully computed Arena Scores for all models.")
    
#     # 2. Create a dataset of (score_difference, total_listen_time) for each battle
#     analysis_data = []
#     for log in tqdm(raw_logs, desc="Calculating per-battle stats"):
#         if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
#             try:
#                 model_a = log["a_metadata"]["system_key"]["system_tag"]
#                 model_b = log["b_metadata"]["system_key"]["system_tag"]
                
#                 # Ensure both models have scores
#                 if model_a not in scores or model_b not in scores:
#                     continue

#                 score_diff = abs(scores[model_a] - scores[model_b])
                
#                 time_a = sum_listen_time(log["vote"].get("a_listen_data", []))
#                 time_b = sum_listen_time(log["vote"].get("b_listen_data", []))
#                 total_listen_time = time_a + time_b

#                 analysis_data.append({
#                     "score_difference": score_diff,
#                     "total_listen_time": total_listen_time
#                 })
#             except (KeyError, TypeError):
#                 continue
    
#     if not analysis_data:
#         print("No valid voted battles to analyze for correlation.")
#         return
        
#     df = pd.DataFrame(analysis_data)

#     # 3. Remove outliers from listening time using IQR method for a clearer plot
#     Q1 = df['total_listen_time'].quantile(0.25)
#     Q3 = df['total_listen_time'].quantile(0.75)
#     IQR = Q3 - Q1
#     threshold = Q3 + 1.5 * IQR
#     filtered_df = df[df['total_listen_time'] <= threshold]
    
#     print(f"Removed {len(df) - len(filtered_df)} outliers based on listening time (Threshold > {threshold:.2f}s).")

#     # 4. Calculate Pearson and Spearman correlation
#     pearson_corr, p_pearson = pearsonr(filtered_df['score_difference'], filtered_df['total_listen_time'])
#     spearman_corr, p_spearman = spearmanr(filtered_df['score_difference'], filtered_df['total_listen_time'])

#     print("\n--- Correlation Results ---")
#     print(f"Pearson Correlation: {pearson_corr:.3f} (p-value: {p_pearson:.3f})")
#     print(f"Spearman Correlation: {spearman_corr:.3f} (p-value: {p_spearman:.3f})")
#     print("---------------------------\n")


#     # 5. Plotting the visualization
#     print("--- 📊 Plotting Correlation ---")
#     plt.style.use('seaborn-v0_8-whitegrid')
#     plt.figure(figsize=(12, 8))
    
#     # Use regplot to show scatter plot and regression line
#     sns.regplot(
#         data=filtered_df,
#         x='score_difference',
#         y='total_listen_time',
#         scatter_kws={'alpha':0.3, 's':50},
#         line_kws={'color':'red', 'linestyle':'--'}
#     )
    
#     plt.title('Total Listening Time vs. Arena Score Difference', fontsize=16, weight='bold')
#     plt.xlabel('Arena Score Difference', fontsize=12)
#     plt.ylabel('Total Listening Time [s]', fontsize=12)
    
#     # Add correlation info to the plot
#     plt.text(0.95, 0.95, f'Spearman R = {spearman_corr:.3f}', 
#              ha='center', va='top', transform=plt.gca().transAxes, fontsize=14,
#              bbox=dict(boxstyle='round,pad=0.5'))

#     plt.tight_layout()
    
#     filename = "listening_time_vs_closeness_correlation.png"
#     plt.savefig(filename, dpi=300, bbox_inches='tight')
#     print(f"\n[INFO] Correlation plot saved to {filename}")
#     plt.close()

# if __name__ == "__main__":
#     # Assuming these modules and functions exist from your project structure
#     all_raw_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
#     analyze_engagement_vs_closeness_correlation(all_raw_logs)



# import os
# import pandas as pd
# from tqdm import tqdm
# from scipy.stats import pearsonr, spearmanr
# import matplotlib.pyplot as plt
# import seaborn as sns

# # Import from your existing modules
# from config import BATTLE_LOGS_DIR
# from scoring import compute_arena_score
# from analysis import sum_listen_time
# from data_loader import parse_logs, load_all_raw_logs

# def calculate_engagement_data(raw_logs, scores):
#     """Calculates data for correlation between score difference and listening time."""
#     print("\n--- 🧐 Calculating data for: Arena Score Difference vs. Listening Time ---")
#     analysis_data = []
#     for log in tqdm(raw_logs, desc="Processing listening time"):
#         if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
#             try:
#                 model_a = log["a_metadata"]["system_key"]["system_tag"]
#                 model_b = log["b_metadata"]["system_key"]["system_tag"]
                
#                 if model_a not in scores or model_b not in scores:
#                     continue

#                 score_diff = abs(scores[model_a] - scores[model_b])
#                 time_a = sum_listen_time(log["vote"].get("a_listen_data", []))
#                 time_b = sum_listen_time(log["vote"].get("b_listen_data", []))
#                 total_listen_time = time_a + time_b

#                 analysis_data.append({
#                     "score_difference": score_diff,
#                     "total_listen_time": total_listen_time
#                 })
#             except (KeyError, TypeError):
#                 continue
    
#     if not analysis_data:
#         print("No valid data for listening time correlation.")
#         return pd.DataFrame()
        
#     df = pd.DataFrame(analysis_data)

#     # Remove outliers
#     Q1 = df['total_listen_time'].quantile(0.25)
#     Q3 = df['total_listen_time'].quantile(0.75)
#     IQR = Q3 - Q1
#     threshold = Q3 + 1.5 * IQR
#     filtered_df = df[df['total_listen_time'] <= threshold]
#     print(f"Removed {len(df) - len(filtered_df)} outliers from listening time (Threshold > {threshold:.2f}s).")
#     return filtered_df

# def calculate_swaps_data(raw_logs, scores):
#     """Calculates data for correlation between score difference and number of swaps."""
#     print("\n--- 🔄 Calculating data for: Arena Score Difference vs. Number of Swaps ---")
#     analysis_data = []
#     for log in tqdm(raw_logs, desc="Processing swaps"):
#         if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
#             try:
#                 model_a = log["a_metadata"]["system_key"]["system_tag"]
#                 model_b = log["b_metadata"]["system_key"]["system_tag"]
                
#                 if model_a not in scores or model_b not in scores:
#                     continue

#                 score_diff = abs(scores[model_a] - scores[model_b])
                
#                 vote_data = log["vote"]
#                 events_a = [e[0] for e in vote_data.get("a_listen_data", []) if isinstance(e, list) and len(e) > 0]
#                 events_b = [e[0] for e in vote_data.get("b_listen_data", []) if isinstance(e, list) and len(e) > 0]
#                 num_swaps = max(0, events_a.count('PLAY') + events_b.count('PLAY') - 1)

#                 analysis_data.append({
#                     "score_difference": score_diff,
#                     "num_swaps": num_swaps
#                 })
#             except (KeyError, TypeError):
#                 continue
    
#     if not analysis_data:
#         print("No valid data for swap correlation.")
#         return pd.DataFrame()
        
#     return pd.DataFrame(analysis_data)

# def plot_combined_correlations(engagement_df, swaps_df):
#     """Plots the two correlation analyses side-by-side in a single figure."""
#     print("\n--- 📊 Plotting Combined Correlation Figure ---")
#     plt.style.use('seaborn-v0_8-whitegrid')
#     fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8)) # 1 row, 2 columns

#     # --- Plot 1: Total Listening Time vs. Closeness ---
#     if not engagement_df.empty:
#         spearman_corr, _ = spearmanr(engagement_df['score_difference'], engagement_df['total_listen_time'])
#         sns.regplot(data=engagement_df, x='score_difference', y='total_listen_time',
#                     scatter_kws={'alpha':0.3, 's':50}, line_kws={'color':'red', 'linestyle':'--'}, ax=ax1)
#         ax1.set_title('Total Listening Time vs. Arena Score Difference', fontsize=16, weight='bold')
#         ax1.set_xlabel('Arena Score Difference', fontsize=12)
#         ax1.set_ylabel('Total Listening Time [s]', fontsize=12)
        
#         ax1.text(0.5, 0.95, f'Spearman R = {spearman_corr:.3f}', 
#                  ha='center', va='top', transform=ax1.transAxes, fontsize=14)
        
#         print(f"Spearman Correlation (Listen Time): {spearman_corr:.3f}")

#     # --- Plot 2: Swaps vs. Closeness ---
#     if not swaps_df.empty:
#         spearman_corr, _ = spearmanr(swaps_df['score_difference'], swaps_df['num_swaps'])
#         sns.regplot(data=swaps_df, x='score_difference', y='num_swaps', x_jitter=0.05,
#                     scatter_kws={'alpha':0.2, 's':50}, line_kws={'color':'blue', 'linestyle':'--'}, ax=ax2)
#         ax2.set_title('Number of Swaps vs. Arena Score Difference', fontsize=16, weight='bold')
#         ax2.set_xlabel('Arena Score Difference', fontsize=12)
#         ax2.set_ylabel('Number of Swaps', fontsize=12)
#         ax2.set_yticks(range(int(swaps_df['num_swaps'].max()) + 2))
        
#         ax2.text(0.5, 0.95, f'Spearman R = {spearman_corr:.3f}', 
#                  ha='center', va='top', transform=ax2.transAxes, fontsize=14)
        
#         print(f"Spearman Correlation (Swaps): {spearman_corr:.3f}")

#     # --- Final Touches ---
#     fig.suptitle('Arena Score Difference vs. User Engagement Metrics', fontsize=20, weight='bold')
#     plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
#     filename = "combined_correlation_analysis.png"
#     plt.savefig(filename, dpi=300, bbox_inches='tight')
#     print(f"\n[INFO] Combined plot saved to {filename}")
#     plt.close()

# if __name__ == "__main__":
#     print("--- 🚀 Starting Full Correlation Analysis ---")
    
#     all_raw_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
#     battles_df, _ = parse_logs(BATTLE_LOGS_DIR)
    
#     if battles_df.empty:
#         print("Not enough battle data to compute scores. Exiting.")
#     else:
#         scores = compute_arena_score(battles_df)
#         print("\nSuccessfully computed Arena Scores for all models.")
        
#         # 1. Calculate data for both analyses
#         engagement_data = calculate_engagement_data(all_raw_logs, scores)
#         swaps_data = calculate_swaps_data(all_raw_logs, scores)
        
#         # 2. Pass the data to the combined plotting function
#         plot_combined_correlations(engagement_data, swaps_data)
        
#         print("\n--- ✅ Analysis Complete ---")

import sys, os
import pandas as pd
from tqdm import tqdm
from scipy.stats import spearmanr
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import BATTLE_LOGS_DIR
from scoring import compute_arena_score
from analysis import sum_listen_time
from data_loader import parse_logs, load_all_raw_logs

def calculate_engagement_data(raw_logs, scores):
    """Calculates data for correlation between score difference and listening time."""
    print("\n--- 🧐 Calculating data for: Arena Score Difference vs. Listening Time ---")
    analysis_data = []
    for log in tqdm(raw_logs, desc="Processing listening time"):
        if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
            try:
                model_a = log["a_metadata"]["system_key"]["system_tag"]
                model_b = log["b_metadata"]["system_key"]["system_tag"]
                
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
    if engagement_df.empty:
        return

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
    
    filename = "listening_time_vs_closeness_correlation.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"[INFO] Plot saved to {filename}")
    plt.close()

def plot_swaps_correlation(swaps_df):
    """Plots and saves the swaps vs. closeness correlation figure."""
    if swaps_df.empty:
        return
        
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

    filename = "swaps_vs_closeness_correlation.png"
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
        scores = compute_arena_score(battles_df)
        print("\nSuccessfully computed Arena Scores for all models.")
        
        # 1. Calculate data for both analyses
        engagement_data = calculate_engagement_data(all_raw_logs, scores)
        swaps_data = calculate_swaps_data(all_raw_logs, scores)
        
        # 2. Plot each analysis in a separate figure
        plot_engagement_correlation(engagement_data)
        plot_swaps_correlation(swaps_data)
        
        print("\n--- ✅ Analysis Complete ---")