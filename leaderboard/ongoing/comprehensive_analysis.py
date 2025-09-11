import os
import json
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime, timezone
import pytz

# Import from your existing modules
from config import BATTLE_LOGS_DIR, MODELS_METADATA
from scoring import compute_arena_score
from data_loader import parse_logs # Make sure parse_logs is available

def sum_listen_time(listen_data: list) -> float:
    """Calculates the total listening time from a listen_data log."""
    last_play_time = None; total_time = 0
    if not listen_data: return 0
    for event_data in listen_data:
        if isinstance(event_data, list) and len(event_data) == 2:
            event, timestamp = event_data
            if event == "PLAY":
                if last_play_time is None: last_play_time = timestamp
            elif event in ["PAUSE", "STOP", "TICK"]:
                if last_play_time is not None: total_time += timestamp - last_play_time
                last_play_time = timestamp if event == "TICK" else None
    return total_time

def load_all_raw_logs(log_dir):
    """Loads all JSON logs from a directory into a list."""
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

def analyze_prompt_usage(raw_logs):
    """
    (REVISED) Analyzes prompt usage, counting only battles between known models.
    """
    user_written_total = 0
    prebaked_total = 0
    user_written_voted = 0
    prebaked_voted = 0
    known_models = set(MODELS_METADATA.keys())

    for log in raw_logs:
        if log.get("prompt_session"):
            
            # --- Filter by known models ---
            model_a = log.get("a_metadata", {}).get("system_key", {}).get("system_tag")
            model_b = log.get("b_metadata", {}).get("system_key", {}).get("system_tag")
            if not model_a or not model_b or model_a not in known_models or model_b not in known_models:
                continue
            # ------------------------------------

            has_vote = log.get("vote") is not None
            is_prebaked = log.get("prompt_prebaked", False)

            if is_prebaked:
                prebaked_total += 1
                if has_vote:
                    prebaked_voted += 1
            else:
                user_written_total += 1
                if has_vote:
                    user_written_voted += 1
    
    total_battles = user_written_total + prebaked_total
    total_voted = user_written_voted + prebaked_voted

    if total_battles > 0:
        prompt_stats = [
            {"Prompt Type": "User-Written", "Total Battles": user_written_total, "Voted Battles": user_written_voted, "Vote Ratio (%)": (user_written_voted / user_written_total * 100) if user_written_total > 0 else 0},
            {"Prompt Type": "'Surprise Me' (Prebaked)", "Total Battles": prebaked_total, "Voted Battles": prebaked_voted, "Vote Ratio (%)": (prebaked_voted / prebaked_total * 100) if prebaked_total > 0 else 0},
            {"Prompt Type": "Total", "Total Battles": total_battles, "Voted Battles": total_voted, "Vote Ratio (%)": (total_voted / total_battles * 100) if total_battles > 0 else 0}
        ]
        
        df = pd.DataFrame(prompt_stats)
        df['Vote Ratio (%)'] = df['Vote Ratio (%)'].map('{:.2f}%'.format)

        print("\n--- 🎲 Prompt Usage & Vote Ratio (Known Models Only) ---")
        print(df.to_string(index=False))
        print("-----------------------------------------------------------\n")

def analyze_listening_behavior(raw_logs):
    """(REVISED) Calculates detailed listening stats and swap behavior for known models."""
    listen_times_a, listen_times_b, swap_counts = [], [], []
    known_models = set(MODELS_METADATA.keys()) # <<-- 추가 (Added)

    # print(f"len(raw_logs) = {len(raw_logs)}") # This will print total logs before filtering
    for log in raw_logs:
        # --- 추가: 알려진 모델만 필터링 (ADDED: Filter for known models only) ---
        model_a = log.get("a_metadata", {}).get("system_key", {}).get("system_tag")
        model_b = log.get("b_metadata", {}).get("system_key", {}).get("system_tag")
        if not model_a or not model_b or model_a not in known_models or model_b not in known_models:
            continue
        # -------------------------------------------------------------------

        if log.get("vote") and log.get("prompt_session"):
            vote_data = log["vote"]
            if vote_data.get("a_listen_data") and vote_data.get("b_listen_data"):
                listen_times_a.append(sum_listen_time(vote_data["a_listen_data"]))
                listen_times_b.append(sum_listen_time(vote_data["b_listen_data"]))
                
                # Calculate swaps
                events_a = [e[0] for e in vote_data["a_listen_data"] if isinstance(e, list) and len(e) > 0]
                events_b = [e[0] for e in vote_data["b_listen_data"] if isinstance(e, list) and len(e) > 0]
                swaps = events_a.count('PLAY') + events_b.count('PLAY') - 1
                swap_counts.append(max(0, swaps))

    print(f"Total voted battles between known models analyzed for listening behavior: {len(swap_counts)}") # <<-- 수정 (Modified)
    if not listen_times_a: return

    # Listening Time Stats
    stats_df = pd.DataFrame({
        'Metric': ['Average', 'Std. Dev.', 'Min', 'Max'],
        'Track A (sec)': [np.mean(listen_times_a), np.std(listen_times_a), np.min(listen_times_a), np.max(listen_times_a)],
        'Track B (sec)': [np.mean(listen_times_b), np.std(listen_times_b), np.min(listen_times_b), np.max(listen_times_b)]
    }).round(2)
    print("\n--- 🎧 Listening Time Statistics (Known Models Only) ---")
    print(stats_df.to_string(index=False))
    print("-----------------------------------------------------------\n")

    # Swap Behavior PMF
    swap_df = pd.Series(swap_counts).value_counts(normalize=True).sort_index().reset_index()
    swap_df.columns = ['Swaps', 'Probability']
    print("\n--- 🔄 Swap Behavior PMF (Known Models Only) ---")
    print(swap_df.to_string(index=False))
    print("--------------------------------------------------\n")

def analyze_daily_activity(raw_logs, timezone_str):
    """(REVISED) Analyzes daily battle counts and unique user counts for known models."""
    daily_activity = {}
    known_models = set(MODELS_METADATA.keys()) # <<-- 추가 (Added)
    
    for log in raw_logs:
        # --- 추가: 알려진 모델만 필터링 (ADDED: Filter for known models only) ---
        model_a = log.get("a_metadata", {}).get("system_key", {}).get("system_tag")
        model_b = log.get("b_metadata", {}).get("system_key", {}).get("system_tag")
        if not model_a or not model_b or model_a not in known_models or model_b not in known_models:
            continue
        # -------------------------------------------------------------------

        session = log.get("prompt_session")
        if session and isinstance(session, dict) and session.get("create_time"):
            utc_dt = datetime.fromtimestamp(session["create_time"], tz=timezone.utc)
            local_dt = utc_dt.astimezone(pytz.timezone(timezone_str))
            date_key = local_dt.date()
            
            if date_key not in daily_activity:
                daily_activity[date_key] = set()

            user_id = log.get("prompt_user", {}).get("salted_ip")
            if user_id:
                daily_activity[date_key].add(user_id)

    if not daily_activity: return

    df = pd.DataFrame([(date, len(users)) for date, users in daily_activity.items()], columns=['Date', 'Unique Users'])
    df = df.sort_values('Date')
    
    print("\n--- 📈 Daily User Activity (Known Models Only) ---")
    print(df.to_string(index=False))
    print("---------------------------------------------------\n")

def analyze_engagement_vs_closeness(raw_logs):
    """(REVISED) Analyzes if listening behavior changes with battle difficulty for known models."""
    battles_df, _ = parse_logs(BATTLE_LOGS_DIR)
    if battles_df.empty: return
    
    scores = compute_arena_score(battles_df)
    known_models = set(MODELS_METADATA.keys()) # <<-- 추가 (Added)
    
    close_battles, mod_battles, dist_battles = [], [], []

    for log in raw_logs:
        if log.get("vote") and log.get("a_metadata") and log.get("b_metadata"):
            try:
                model_a = log["a_metadata"]["system_key"]["system_tag"]
                model_b = log["b_metadata"]["system_key"]["system_tag"]
                
                # --- 추가: 알려진 모델만 필터링 (ADDED: Filter for known models only) ---
                if model_a not in known_models or model_b not in known_models:
                    continue
                # -------------------------------------------------------------------
                
                score_a = scores.get(model_a, 1000)
                score_b = scores.get(model_b, 1000)
                score_diff = abs(score_a - score_b)
                
                time_a = sum_listen_time(log["vote"].get("a_listen_data", []))
                time_b = sum_listen_time(log["vote"].get("b_listen_data", []))
                events_a = [e[0] for e in log["vote"]["a_listen_data"] if isinstance(e, list) and len(e) > 0]
                events_b = [e[0] for e in log["vote"]["b_listen_data"] if isinstance(e, list) and len(e) > 0]
                swaps = max(0, events_a.count('PLAY') + events_b.count('PLAY') - 1)
                
                battle_info = (time_a + time_b, swaps)

                if score_diff < 50:
                    close_battles.append(battle_info)
                elif 50 <= score_diff <= 150:
                    mod_battles.append(battle_info)
                else:
                    dist_battles.append(battle_info)
            except (KeyError, TypeError):
                continue
    
    results = []
    for name, battles in [("Very Close (<50)", close_battles), 
                          ("Moderate (50-150)", mod_battles), 
                          ("Distant (>150)", dist_battles)]:
        if battles:
            df = pd.DataFrame(battles, columns=['total_listen_time', 'swaps'])
            results.append({
                "closeness_group": name,
                "avg_total_listen_time": df['total_listen_time'].mean(),
                "avg_swaps": df['swaps'].mean(),
                "battle_count": len(df)
            })

    if results:
        results_df = pd.DataFrame(results).round(2)
        print("\n--- 🧐 Listening Behavior vs. Leaderboard Closeness (Known Models Only) ---")
        print(results_df.to_string(index=False))
        print("-----------------------------------------------------------------------------\n")

if __name__ == "__main__":
    print("Running comprehensive analysis...")
    all_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
    
    if all_logs:
        analyze_prompt_usage(all_logs)
        analyze_listening_behavior(all_logs)
        analyze_daily_activity(all_logs, 'UTC') # You can change 'UTC' to your local timezone e.g., 'America/New_York'
        analyze_engagement_vs_closeness(all_logs)
    else:
        print("No log files found or loaded. Exiting.")