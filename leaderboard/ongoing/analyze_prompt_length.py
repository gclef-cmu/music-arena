import os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration ---
BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs/analysis"

# --- Import model metadata for filtering ---
# This assumes the script is run from the leaderboard directory
# and can access config.py
try:
    from config import MODELS_METADATA
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    print("Successfully imported model metadata for filtering.")
except ImportError:
    print("Warning: config.py not found. Cannot filter by known models.")
    KNOWN_MODELS = None

def analyze_and_visualize_prompt_length(log_dir: str):
    """
    (REVISED) Analyzes user-written prompt lengths only from valid, voted-on battles
    between known models, uses IQR to handle outliers, and visualizes the distribution.
    """
    print(f"Analyzing prompt lengths from local directory: {log_dir}...")
    
    prompt_lengths = []

    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    
    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # --- (REVISED) Filtering Logic ---
            # Condition 1: Must be a voted-on battle
            if not data.get("vote"):
                continue
            
            # Condition 2: Must be a user-initiated battle (not prebaked)
            if data.get("prompt_prebaked", False):
                continue

            # Condition 3: Both models must be in our official list
            if KNOWN_MODELS:
                model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
                model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
                if not model_a or not model_b or model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                    continue
            
            # If all conditions pass, extract the prompt length
            prompt_text = data.get("prompt_detailed", {}).get("overall_prompt")
            if prompt_text:
                prompt_lengths.append(len(prompt_text.split()))

        except Exception:
            continue

    if not prompt_lengths:
        print("No valid user-written prompts from voted battles found to analyze.")
        return

    # --- Create a DataFrame for analysis ---
    df = pd.DataFrame(prompt_lengths, columns=['Prompt Length (words)'])

    print("\n--- Prompt Length Statistics (from valid, voted battles) ---")
    print(df.describe().round(2))

    # --- Calculate IQR-based outlier threshold ---
    Q1 = int(df['Prompt Length (words)'].quantile(0.25))
    Q3 = int(df['Prompt Length (words)'].quantile(0.75))
    IQR = int(Q3 - Q1)
    outlier_threshold = Q3 + 1.5 * IQR
    
    print("\n--- IQR-based Outlier Threshold ---")
    print(f"Calculated outlier threshold: {outlier_threshold:.2f} words")
    
    # --- Filter outliers for a cleaner visualization ---
    plot_df = df[df['Prompt Length (words)'] <= outlier_threshold]
    
    print(f"\n--- Statistics for prompts within IQR range ---")
    print(f"Filtered to {len(plot_df)} prompts (out of {len(df)}).")
    print(plot_df.describe().round(2))

    # --- Plotting the distribution ---
    print("\n--- 📊 Plotting Prompt Length Distribution ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Calculate optimal bin width using Freedman-Diaconis rule
    iqr_val = plot_df['Prompt Length (words)'].quantile(0.75) - plot_df['Prompt Length (words)'].quantile(0.25)
    if iqr_val > 0:
        bin_width = 2 * iqr_val / (len(plot_df['Prompt Length (words)'])**(1/3))
        bins = int((plot_df['Prompt Length (words)'].max() - plot_df['Prompt Length (words)'].min()) / bin_width)
    else:
        bins = 20 # Fallback for low variance data

    sns.histplot(data=plot_df, x='Prompt Length (words)', bins=bins, ax=ax, kde=True)
    ax.set_title('Distribution of User Prompt Lengths (Voted Battles)', fontsize=16, weight='bold')
    ax.set_xlabel('Prompt Length (Number of Words)', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    
    median_val = int(plot_df['Prompt Length (words)'].median())
    threshold_val = int(outlier_threshold)

    ax.axvline(median_val, color='red', linestyle='--', label=f"Median: {median_val} words")
    ax.axvline(threshold_val, color='purple', linestyle=':', label=f"IQR Outlier Threshold: {threshold_val} words")
  
    ax.legend(fontsize=12, loc='upper center')
    
    plt.tight_layout()
    
    filename = os.path.join(OUTPUT_DIR, "prompt_length_distribution_voted_iqr.png")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Distribution plot (voted, IQR filtered) saved to {filename}")
    plt.close()

if __name__ == "__main__":
    analyze_and_visualize_prompt_length(BATTLE_LOGS_DIR)