import argparse
from datetime import datetime, timezone
import os
from config import GCP_PROJECT_ID, METADATA_BUCKET_NAME, BATTLE_LOGS_DIR, OUTPUT_DIR, MODELS_METADATA
from data_loader import download_logs_from_gcs, parse_logs
from analysis import analyze_battle_stats
from leaderboard import generate_leaderboard
from visualizer import plot_leaderboard

def main():
    parser = argparse.ArgumentParser(description="A modular script to download, analyze, and generate leaderboards for Music Arena.")
    parser.add_argument('--action', type=str, choices=['download', 'analyze', 'leaderboard'], required=True, help="Action to perform.")
    parser.add_argument('--start_date', type=str, help="Start date (YYYY-MM-DD) for filtering.")
    parser.add_argument('--end_date', type=str, help="End date (YYYY-MM-DD) for filtering.")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.start_date else None
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc) if args.end_date else None
    
    os.makedirs(os.path.join(OUTPUT_DIR, 'leaderboards'), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, 'plots'), exist_ok=True)

    if args.action == 'download':
        download_logs_from_gcs(GCP_PROJECT_ID, METADATA_BUCKET_NAME, BATTLE_LOGS_DIR, start_date, end_date)
    
    elif args.action == 'analyze':
        _, raw_logs = parse_logs(BATTLE_LOGS_DIR, start_date, end_date)
        analyze_battle_stats(raw_logs, start_date, end_date)
        
    elif args.action == 'leaderboard':
        battles_df, raw_logs_for_time = parse_logs(BATTLE_LOGS_DIR)
        
        if start_date and end_date:
            battles_df, _ = parse_logs(BATTLE_LOGS_DIR, start_date, end_date)
            date_str = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        else:
            all_times = []
            for log in raw_logs_for_time:
                session_time_unix = None
                prompt_session = log.get("prompt_session")
                if isinstance(prompt_session, dict):
                    session_time_unix = prompt_session.get("create_time")

                if not session_time_unix:
                    a_metadata = log.get("a_metadata")
                    if isinstance(a_metadata, dict):
                        session_time_unix = a_metadata.get("gateway_time_completed")
                
                if session_time_unix:
                    all_times.append(datetime.fromtimestamp(session_time_unix, tz=timezone.utc))
            
            if all_times:
                min_date = min(all_times).strftime('%Y%m%d')
                max_date = max(all_times).strftime('%Y%m%d')
                date_str = f"{min_date}_to_{max_date}"
            else:
                date_str = "all_time"

        if not battles_df.empty:
            inst_df = generate_leaderboard(battles_df, MODELS_METADATA, "instrumental")
            if not inst_df.empty:
                print("\n--- 🎹 Instrumental Leaderboard ---")
                print(inst_df.to_string())
                inst_df.to_csv(f"{OUTPUT_DIR}/leaderboards/instrumental_leaderboard_{date_str}.tsv", sep='\t')
                plot_leaderboard(inst_df, "Instrumental Leaderboard", f"{OUTPUT_DIR}/plots/instrumental_plot_{date_str}.png")

            vocal_df = generate_leaderboard(battles_df, MODELS_METADATA, "vocal")
            if not vocal_df.empty:
                print("\n--- 🎤 Vocal Leaderboard ---")
                print(vocal_df.to_string())
                vocal_df.to_csv(f"{OUTPUT_DIR}/leaderboards/vocal_leaderboard_{date_str}.tsv", sep='\t')
                plot_leaderboard(vocal_df, "Vocal Leaderboard", f"{OUTPUT_DIR}/plots/vocal_plot_{date_str}.png")


if __name__ == "__main__":
    main()