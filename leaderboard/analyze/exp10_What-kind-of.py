# analyze_prompt_keywords.py
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

# --- Configuration ---
BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs/analysis"

# --- (신규) 필터링을 위한 모델 메타데이터 import ---
# 스크립트가 leaderboard 폴더에서 실행되고, config.py에 접근 가능하다고 가정합니다.
try:
    from config import MODELS_METADATA
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    print("Successfully imported model metadata for filtering.")
except ImportError:
    print("Warning: config.py not found. Cannot filter by known models.")
    KNOWN_MODELS = None

# NLTK stopwords download (only if needed)
try:
    STOPWORDS = set(stopwords.words('english'))
except LookupError:
    print("Downloading nltk stopwords...")
    nltk.download('stopwords')
    STOPWORDS = set(stopwords.words('english'))

# Add custom words to exclude from analysis
STOPWORDS.update(['music', 'song', 'track', 'beat', 'style', 'sound', 'audio', 'genre'])

def analyze_prompt_keywords(log_dir: str):
    """
    (수정됨) 알려진 모델들 간의, 투표가 완료된 전투에서 사용자가 직접 작성한
    프롬프트의 키워드를 분석하고, 테이블과 워드클라우드를 생성합니다.
    """
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

            # --- 수정된 필터링 로직 ---
            # 1. 사용자가 시작했고, 2. "Random Prompt"가 아니며, 3. 투표가 완료된 전투만 필터링
            if (data.get("prompt_session") and 
                not data.get("prompt_prebaked", False) and 
                data.get("vote") is not None):
                
                # --- (신규) 알려진 모델 간의 전투인지 추가로 필터링 ---
                if KNOWN_MODELS:
                    model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
                    model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
                    if not model_a or not model_b or model_a not in KNOWN_MODELS or model_b not in KNOWN_MODELS:
                        continue # 하나라도 모르는 모델이면 건너뜀
                # ------------------------------------
                
                prompt_text = data.get("prompt_detailed", {}).get("overall_prompt")
                if prompt_text:
                    user_prompts.append(prompt_text)
        except Exception:
            continue

    if not user_prompts:
        print("No valid user-written prompts from voted battles found to analyze.")
        return

    # --- 키워드 빈도 계산 ---
    text = " ".join(user_prompts).lower()
    # --- 키워드 빈도 계산 --- 
    text = " ".join(user_prompts).lower() 
    words = re.findall(r'\b\w+\b', text) 

    # 영어 알파벳으로만 구성된 단어만 계산하도록 조건 추가
    word_counts = Counter(word for word in words 
                        if word not in STOPWORDS 
                        and len(word) > 2 
                        and re.match(r'^[a-zA-Z]+$', word)) # <-- 이 조건이 추가/변경되었습니다.

    print(f"\nSuccessfully analyzed {len(user_prompts)} user-written prompts from valid, voted battles.")
    
    # --- 상위 15개 키워드 테이블 출력 ---
    top_keywords_df = pd.DataFrame(word_counts.most_common(15), columns=['Keyword', 'Frequency'])
    print("\n--- 📝 Top 15 Prompt Keywords (from Voted Battles) ---")
    print(top_keywords_df.to_string(index=False))
    print("-----------------------------------------------------\n")
    
    # --- 워드클라우드 생성 및 저장 ---
    if word_counts:
        wc = WordCloud(width=1200, height=600, background_color='white', colormap='viridis').generate_from_frequencies(word_counts)
        plt.figure(figsize=(15, 7))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis('off')
        
        filename = os.path.join(OUTPUT_DIR, "prompt_keywords_wordcloud_voted.png")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"[INFO] Prompt keywords word cloud (voted battles) saved to {filename}")
        plt.close()

if __name__ == "__main__":
    analyze_prompt_keywords(BATTLE_LOGS_DIR)