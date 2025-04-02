import os
import logging
from google.cloud import storage
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

class GCPClient:
    def __init__(self):
        """
        Initialize Google Cloud Storage client with credentials from either a config file or environment variables.
        """
        load_dotenv(find_dotenv())
        
        # Use the same credentials file as Firebase
        credentials_path = "config/firebase_config.json"
        project_id = os.getenv("GCP_PROJECT_ID", "music-arena")
        
        if os.path.exists(credentials_path):
            self.storage_client = storage.Client.from_service_account_json(
                credentials_path, project=project_id
            )
        else:
            # If running in environment with default credentials (like GCP)
            self.storage_client = storage.Client(project=project_id)
    
    def upload_file(self, bucket_name: str, file_data: bytes, destination_blob_name: str):
        """
        Upload a file to Google Cloud Storage.
        
        Args:
            bucket_name: Name of the GCS bucket
            file_data: Binary data of the file to upload
            destination_blob_name: Path within the bucket to store the file
            
        Returns:
            GCS URI of the uploaded file
        """
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)
            
            # Upload the file
            blob.upload_from_string(file_data)
            
            logger.info(f"File uploaded to gs://{bucket_name}/{destination_blob_name}")
            
            # Return the GCS URI
            return f"gs://{bucket_name}/{destination_blob_name}"

        except Exception as e:
            logger.error(f"Error uploading file to GCS: {str(e)}")
            raise