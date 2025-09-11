# comprehensive_analysis.py
import os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
import re
from collections import Counter
from wordcloud import WordCloud
import nltk
from nltk.corpus import stopwords

# --- Configuration ---
BATTLE_LOGS_DIR = "battle_logs"
OUTPUT_DIR = "outputs/analysis"
# NLTK stopwords 다운로드 (최초 실행 시 필요할 수 있음)
try:
    STOPWORDS = set(stopwords.words('english'))
except LookupError:
    print("Downloading nltk stopwords...")
    nltk.download('stopwords')
    STOPWORDS = set(stopwords.words('english'))

# --- Helper Functions ---
def load_all_raw_logs(log_dir: str) -> list:
    """지정된 디렉토리에서 모든 원본 JSON 로그를 리스트로 불러옵니다."""
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return []
    
    raw_logs = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    for filename in tqdm(log_files, desc="Loading all log files"):
        filepath = os.path.join(log_dir, filename)
        with open(filepath, 'r') as f:
            try:
                raw_logs.append(json.load(f))
            except json.JSONDecodeError:
                continue
    return raw_logs

# --- Analysis Functions ---

def analyze_engagement_levels(raw_logs):
    """사용자별 투표 횟수를 분석하여 참여도 수준을 파악합니다."""
    print("\n--- 👥 Analyzing User Engagement Levels ---")
    user_votes = Counter()
    for log in raw_logs:
        if log.get("vote") and log.get("vote_user"):
            user_id = log["vote_user"].get("salted_ip")
            if user_id:
                user_votes[user_id] += 1
    
    if not user_votes:
        print("No valid user vote data found.")
        return

    vote_counts = pd.Series(list(user_votes.values())).value_counts().sort_index()
    df = vote_counts.reset_index()
    df.columns = ['Number of Votes', 'Number of Users']
    
    print("Distribution of votes per user:")
    print(df.to_string(index=False))

    # Visualize
    plt.figure(figsize=(12, 6))
    sns.barplot(x='Number of Votes', y='Number of Users', data=df.head(10)) # 상위 10개만 시각화
    plt.title('User Engagement Levels (Top 10)', fontsize=16)
    plt.xlabel('Number of Votes Submitted by a Single User', fontsize=12)
    plt.ylabel('Number of Users', fontsize=12)
    plt.yscale('log')
    
    filename = os.path.join(OUTPUT_DIR, "engagement_levels.png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Engagement levels plot saved to {filename}")
    plt.close()

def analyze_keywords(raw_logs):
    """긍정/부정 피드백에서 자주 사용되는 키워드를 분석하고 워드클라우드를 생성합니다."""
    print("\n--- 💬 Analyzing Feedback Keywords ---")
    positive_feedback = []
    negative_feedback = []

    for log in raw_logs:
        if log.get("vote"):
            vote = log["vote"]
            pref = vote.get("preference")
            
            if pref == "A":
                if vote.get("a_feedback"): positive_feedback.append(vote["a_feedback"])
                if vote.get("b_feedback"): negative_feedback.append(vote["b_feedback"])
            elif pref == "B":
                if vote.get("b_feedback"): positive_feedback.append(vote["b_feedback"])
                if vote.get("a_feedback"): negative_feedback.append(vote["a_feedback"])
            elif pref == "BOTH_BAD":
                if vote.get("a_feedback"): negative_feedback.append(vote["a_feedback"])
                if vote.get("b_feedback"): negative_feedback.append(vote["b_feedback"])

    if not positive_feedback and not negative_feedback:
        print("No feedback data found.")
        return

    def get_word_counts(feedback_list):
        text = " ".join(feedback_list).lower()
        words = re.findall(r'\b\w+\b', text)
        return Counter(word for word in words if word not in STOPWORDS and len(word) > 2)

    positive_counts = get_word_counts(positive_feedback)
    negative_counts = get_word_counts(negative_feedback)

    print("\nTop 10 Positive Keywords:")
    print(pd.DataFrame(positive_counts.most_common(10), columns=['Keyword', 'Count']).to_string(index=False))
    
    print("\nTop 10 Negative Keywords:")
    print(pd.DataFrame(negative_counts.most_common(10), columns=['Keyword', 'Count']).to_string(index=False))
    
    # Generate Word Clouds
    if positive_counts:
        wc_pos = WordCloud(width=800, height=400, background_color='white').generate_from_frequencies(positive_counts)
        plt.figure(figsize=(10, 5)); plt.imshow(wc_pos, interpolation='bilinear'); plt.axis('off')
        filename_pos = os.path.join(OUTPUT_DIR, "positive_keywords_wordcloud.png")
        plt.savefig(filename_pos, dpi=300, bbox_inches='tight'); plt.close()
        print(f"\n[INFO] Positive keywords word cloud saved to {filename_pos}")

    if negative_counts:
        wc_neg = WordCloud(width=800, height=400, background_color='black', colormap='autumn').generate_from_frequencies(negative_counts)
        plt.figure(figsize=(10, 5)); plt.imshow(wc_neg, interpolation='bilinear'); plt.axis('off')
        filename_neg = os.path.join(OUTPUT_DIR, "negative_keywords_wordcloud.png")
        plt.savefig(filename_neg, dpi=300, bbox_inches='tight'); plt.close()
        print(f"[INFO] Negative keywords word cloud saved to {filename_neg}")

def analyze_prompt_length(raw_logs):
    """사용자 프롬프트의 길이 분포를 분석합니다."""
    print("\n--- 📝 Analyzing Prompt Lengths ---")
    prompt_lengths = []
    for log in raw_logs:
        if log.get("prompt_session") and not log.get("prompt_prebaked", False):
            prompt_text = log.get("prompt_detailed", {}).get("overall_prompt")
            if prompt_text:
                prompt_lengths.append(len(prompt_text.split())) # 단어 수 기준

    if not prompt_lengths:
        print("No user-written prompts found.")
        return

    df = pd.DataFrame(prompt_lengths, columns=['Prompt Length (words)'])
    print("\nPrompt Length Statistics:")
    print(df.describe().round(2))

    # Visualize
    plt.figure(figsize=(12, 6))
    sns.histplot(data=df, x='Prompt Length (words)', bins=50, kde=True)
    plt.title('Distribution of User Prompt Lengths', fontsize=16)
    plt.xlabel('Prompt Length (Number of Words)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.xlim(0, 200)
    
    filename = os.path.join(OUTPUT_DIR, "prompt_length_distribution.png")
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Prompt length distribution plot saved to {filename}")
    plt.close()

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("Running comprehensive analysis on local battle logs...")
    all_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
    
    if all_logs:
        # 1. Engagement Levels
        analyze_engagement_levels(all_logs)
        
        # 2. Keyword Analysis (and Categorize Feedback helper)
        analyze_keywords(all_logs)
        
        # 3. Prompt Length
        analyze_prompt_length(all_logs)
    else:
        print("No log files found to analyze.")