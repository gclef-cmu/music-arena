# analysis.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from config import MODELS_METADATA

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

def analyze_battle_stats(raw_logs, start_date=None, end_date=None):
    """
    Analyzes raw logs, filtering for known models, to provide a summary.
    """
    KNOWN_MODELS = set(MODELS_METADATA.keys())
    
    stats = {
        "total_in_range": 0, 
        "health_check": 0, 
        "user_unvoted": 0, 
        "voted_with_unknown_models": 0,
        "voted": 0
    }
    listen_times_a, listen_times_b = [], []

    for data in raw_logs:
        if start_date and end_date:
            session_time_unix = None
            prompt_session = data.get("prompt_session")
            if isinstance(prompt_session, dict):
                session_time_unix = prompt_session.get("create_time")

            if not session_time_unix:
                a_metadata = data.get("a_metadata")
                if isinstance(a_metadata, dict):
                    session_time_unix = a_metadata.get("gateway_time_completed")

            if session_time_unix:
                session_time_dt = datetime.fromtimestamp(session_time_unix, tz=timezone.utc)
                if not (start_date <= session_time_dt <= end_date):
                    continue
            else:
                continue
        
        stats["total_in_range"] += 1
        
        is_prebaked, has_vote = data.get("prompt_prebaked", False), data.get("vote") is not None

        if is_prebaked and not has_vote: 
            stats["health_check"] += 1
        elif not is_prebaked and not has_vote: 
            stats["user_unvoted"] += 1
        elif has_vote:
            model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
            model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
            
            if model_a in KNOWN_MODELS and model_b in KNOWN_MODELS:
                stats["voted"] += 1
                listen_times_a.append(sum_listen_time(data["vote"].get("a_listen_data", [])))
                listen_times_b.append(sum_listen_time(data["vote"].get("b_listen_data", [])))
            else:
                stats["voted_with_unknown_models"] += 1
    
    print("\n--- 📊 Analysis Results ---")
    for key, value in stats.items(): print(f"{key.replace('_', ' ').title()}: {value}")

    if stats["voted"] > 0:
        stats_df = pd.DataFrame({
            'Metric': ['Average', 'Std. Dev.', 'Min', 'Max'],
            'Track A (sec)': [np.mean(listen_times_a), np.std(listen_times_a), np.min(listen_times_a), np.max(listen_times_a)],
            'Track B (sec)': [np.mean(listen_times_b), np.std(listen_times_b), np.min(listen_times_b), np.max(listen_times_b)]
        }).round(2)
        print("\n--- Listening Time Statistics (for voted battles with known models) ---")
        print(stats_df.to_string(index=False))
    print("--------------------------")