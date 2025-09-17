import os
import json
import pandas as pd
from tqdm import tqdm
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re
import nltk
from nltk.corpus import stopwords

BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs/analysis"

try:
    from config import MODELS_METADATA
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    print("Successfully imported model metadata for filtering.")
except ImportError:
    print("Warning: config.py not found. Cannot filter by known models.")
    KNOWN_MODELS = None

try:
    STOPWORDS = set(stopwords.words('english'))
except LookupError:
    print("Downloading nltk stopwords...")
    nltk.download('stopwords')
    STOPWORDS = set(stopwords.words('english'))

STOPWORDS.update(['music', 'song', 'track', 'beat', 'style', 'sound', 'audio', 'genre'])

def analyze_prompt_keywords(log_dir: str):
    
    print(f"Analyzing prompt keywords from directory: {log_dir}...")
    
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    user_prompts = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    
    for filename in tqdm(log_files, desc="Processing logs"):
        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if (data.get("prompt_session") and 
                not data.get("prompt_prebaked", False) and 
                data.get("vote") is not None):
                
                if KNOWN_MODELS:
                    model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
                    model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
                    if not model_a or not model_b or model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                        continue 
                
                prompt_text = data.get("prompt_detailed", {}).get("overall_prompt")
                if prompt_text:
                    user_prompts.append(prompt_text)
        except Exception:
            continue

    if not user_prompts:
        print("No valid user-written prompts from voted battles found to analyze.")
        return

    text = " ".join(user_prompts).lower() 
    words = re.findall(r'\b\w+\b', text) 

    word_counts = Counter(word for word in words 
                        if word not in STOPWORDS 
                        and len(word) > 2 
                        and re.match(r'^[a-zA-Z]+$', word)) 

    print(f"\nSuccessfully analyzed {len(user_prompts)} user-written prompts from valid, voted battles.")
    
    top_keywords_df = pd.DataFrame(word_counts.most_common(15), columns=['Keyword', 'Frequency'])
    print("\n--- 📝 Top 15 Prompt Keywords (from Voted Battles) ---")
    print(top_keywords_df.to_string(index=False))
    print("-----------------------------------------------------\n")
    
    if word_counts:
        wc = WordCloud(width=1200, height=600, background_color='white', colormap='viridis').generate_from_frequencies(word_counts)
        plt.figure(figsize=(15, 7))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis('off')
        
        filename = os.path.join(OUTPUT_DIR, "exp7_what-kind-of-music.png")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[INFO] Prompt keywords word cloud (voted battles) saved to {filename}")
        plt.close()

if __name__ == "__main__":
    analyze_prompt_keywords(BATTLE_LOGS_DIR)
    
"""
python analyze/exp7_what-kind-of-music.py > analyze/exp7_what-kind-of-music.txt
"""