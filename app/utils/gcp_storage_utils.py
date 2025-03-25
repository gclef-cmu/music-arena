import logging
import os
from google.cloud import storage
from typing import Optional

logger = logging.getLogger(__name__)

def upload_to_gcp_storage(
    bucket_name: str,
    source_file_data: bytes,
    destination_blob_name: str
) -> Optional[str]:
    """
    Upload data to Google Cloud Storage.
    
    Args:
        bucket_name (str): The name of the GCS bucket
        source_file_data (bytes): The file data to upload
        destination_blob_name (str): The name of the blob in GCS
        
    Returns:
        Optional[str]: The public URL of the uploaded file if successful, None otherwise
    """
    try:
        # Initialize the GCS client
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        
        # Upload the file data
        blob.upload_from_string(source_file_data, content_type='audio/mpeg')
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Get the public URL
        public_url = blob.public_url
        
        logger.info(f"Successfully uploaded file to GCS: {destination_blob_name}")
        logger.info(f"Public URL: {public_url}")
        
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        return None