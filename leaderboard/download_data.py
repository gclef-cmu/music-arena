# download_data.py
# Downloads battle logs and audio for battles that have a valid vote
# AND involve two known models, mirroring the data_loader.py logic.

import os
import json
from google.cloud import storage
from tqdm import tqdm
from datetime import datetime, timezone
import argparse
from urllib.parse import urlparse
from config import (MODELS_METADATA, GCP_PROJECT_ID, METADATA_BUCKET_NAME, 
                    AUDIO_BUCKET_NAME, METADATA_DOWNLOAD_DIR, AUDIO_DOWNLOAD_DIR)

def download_filtered_data(project_id: str, metadata_bucket_name: str, audio_bucket_name: str,
                           metadata_dir: str, audio_dir: str,
                           start_date: datetime, end_date: datetime):
    """
    Downloads battle logs and audio based on the same filtering logic as data_loader.py.
    """
    os.makedirs(metadata_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    try:
        storage_client = storage.Client(project=project_id)
        metadata_bucket = storage_client.bucket(metadata_bucket_name)
        audio_bucket = storage_client.bucket(audio_bucket_name)
    except Exception as e:
        print(f"Error initializing GCS client: {e}")
        return

    print(f"Fetching and filtering file list from {metadata_bucket_name}...")
    all_blobs = list(metadata_bucket.list_blobs())
    
    filtered_blobs = [
        blob for blob in all_blobs
        if blob.time_created and start_date <= blob.time_created <= end_date
    ]
    
    print(f"Found {len(filtered_blobs)} total logs in date range. Now filtering for valid, known-model battles...")

    local_metadata_files = set(os.listdir(metadata_dir))
    local_audio_files = set(os.listdir(audio_dir))
    known_models = set(MODELS_METADATA.keys())
    
    for blob in tqdm(filtered_blobs, desc="Processing and Downloading Data"):
        if not blob.name.endswith(".json"):
            continue

        try:
            metadata_content = blob.download_as_string()
            data = json.loads(metadata_content)

            # --- FILTERING LOGIC ---
            # Condition 1: Ensure a valid vote object exists
            if data.get("vote") is None:
                continue
            
            # Condition 2: Exclude Health Checks by ensuring a user session exists
            if data.get("prompt_session") is None:
                health_check_count += 1
                continue
            
            # Condition 3: Ensure both models are known models from our list
            model_a = data.get("a_metadata", {}).get("system_key", {}).get("system_tag")
            model_b = data.get("b_metadata", {}).get("system_key", {}).get("system_tag")
            if not model_a or not model_b or model_a not in known_models or model_b not in known_models:
                continue
            # --------------------------------

            # If conditions pass, proceed with download
            metadata_filename = os.path.basename(blob.name)
            if metadata_filename not in local_metadata_files:
                with open(os.path.join(metadata_dir, metadata_filename), 'wb') as f:
                    f.write(metadata_content)

            audio_urls = [data.get("a_audio_url"), data.get("b_audio_url")]
            for url in audio_urls:
                if url:
                    audio_filename = os.path.basename(urlparse(url).path)
                    if audio_filename and audio_filename not in local_audio_files:
                        audio_blob = audio_bucket.blob(audio_filename)
                        if audio_blob.exists():
                            destination_path = os.path.join(audio_dir, audio_filename)
                            audio_blob.download_to_filename(destination_path)

        except Exception as e:
            print(f"Warning: Could not process file {blob.name}. Error: {e}")

    print("\nDownload and filtering process completed.")

def main():
    parser = argparse.ArgumentParser(description="Download valid Music Arena battle data and audio from GCS.")
    parser.add_argument('--start_date', type=str, required=True, help="Start date (YYYY-MM-DD format).")
    parser.add_argument('--end_date', type=str, required=True, help="End date (YYYY-MM-DD format).")
    args = parser.parse_args()

    try:
        start_date_obj = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date_obj = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    except ValueError:
        print("Error: Date format is incorrect. Please use YYYY-MM-DD.")
        return

    download_filtered_data(
        GCP_PROJECT_ID, METADATA_BUCKET_NAME, AUDIO_BUCKET_NAME,
        METADATA_DOWNLOAD_DIR, AUDIO_DOWNLOAD_DIR,
        start_date_obj, end_date_obj
    )

if __name__ == "__main__":
    main()