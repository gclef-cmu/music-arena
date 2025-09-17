import os
import json
import pandas as pd
from google.cloud import storage
from tqdm import tqdm
from datetime import datetime, timezone
from config import MODELS_METADATA

def load_all_raw_logs(log_dir: str) -> list:
    """
    Load all the original JSON logts into list from the designated directory.
    """
    if not os.path.exists(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return []
    
    raw_logs = []
    log_files = [f for f in os.listdir(log_dir) if f.endswith(".json")]
    for filename in tqdm(log_files, desc="Loading all raw log files"):
        filepath = os.path.join(log_dir, filename)
        with open(filepath, 'r') as f:
            try:
                raw_logs.append(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for file {filename}")
                continue
    return raw_logs

def download_logs_from_gcs(project_id, bucket_name, download_dir, start_date=None, end_date=None):
    """
    Downloads new .json files from a GCS bucket, skipping existing ones.
    Optionally filters by a date range based on file creation time.
    """
    os.makedirs(download_dir, exist_ok=True)
    print(f"Checking for new battle logs in GCS bucket: {bucket_name}...")
    
    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        
        local_files = set(os.listdir(download_dir))
        
        if start_date and end_date:
            print(f"Filtering files created between {start_date.date()} and {end_date.date()} UTC...")
            blobs = [
                blob for blob in blobs
                if blob.time_created and start_date <= blob.time_created <= end_date
            ]

        new_blobs_to_download = [
            blob for blob in blobs
            if blob.name.endswith(".json") and os.path.basename(blob.name) not in local_files
        ]

        if not new_blobs_to_download:
            print("No new files to download. Local directory is up to date.")
            return

        print(f"Found {len(new_blobs_to_download)} new files to download.")
        for blob in tqdm(new_blobs_to_download, desc="Downloading new JSON logs"):
            dest_path = os.path.join(download_dir, os.path.basename(blob.name))
            blob.download_to_filename(dest_path)
            
    except Exception as e:
        print(f"Error during download from GCS: {e}")
    print(f"\nDownload complete. Local directory '{download_dir}/' is now synchronized.")

def parse_logs(log_dir, start_date=None, end_date=None):
    """
    Parses local logs with robust date filtering and returns a DataFrame and raw logs.
    """
    print(f"\nParsing logs from: {log_dir}")
    if start_date and end_date:
        print(f"Filtering between {start_date.date()} and {end_date.date()} UTC...")

    parsed_data = []
    raw_logs = []
    known_models = set(MODELS_METADATA.keys())
    skipped_unknown_model_count = 0

    for filename in tqdm(os.listdir(log_dir), desc="Parsing files"):
        if not filename.endswith(".json"): continue

        filepath = os.path.join(log_dir, filename)
        with open(filepath, 'r') as f: data = json.load(f)

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

        raw_logs.append(data)

        if data.get("vote") and data.get("a_metadata") and data.get("b_metadata"):
            try:
                model_a = data["a_metadata"]["system_key"]["system_tag"]
                model_b = data["b_metadata"]["system_key"]["system_tag"]
                
                if model_a not in known_models or model_b not in known_models:
                    skipped_unknown_model_count += 1
                    continue
                
                pref = data["vote"]["preference"]
                winner = "tie"
                if pref == "A": winner = "model_a"
                elif pref == "B": winner = "model_b"

                parsed_data.append({
                    "model_a": model_a, "model_b": model_b, "winner": winner,
                    "duration_a": data["a_metadata"]["duration"],
                    "generation_time_a": data["a_metadata"]["gateway_time_completed"] - data["a_metadata"]["gateway_time_started"],
                    "duration_b": data["b_metadata"]["duration"],
                    "generation_time_b": data["b_metadata"]["gateway_time_completed"] - data["b_metadata"]["gateway_time_started"]
                })
            except (KeyError, TypeError):
                continue

    return pd.DataFrame(parsed_data), raw_logs