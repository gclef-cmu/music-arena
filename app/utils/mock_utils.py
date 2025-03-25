import logging
import os
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Flag to enable/disable mocking
ENABLE_MOCKING = os.environ.get('ENABLE_MOCKING', 'true').lower() == 'true'

def mock_firebase_upload(collection: str, document_id: str, data: Dict[str, Any]) -> bool:
    """
    Mock implementation of Firebase upload for testing.
    
    Args:
        collection (str): The collection name
        document_id (str): The document ID
        data (Dict[str, Any]): The data to upload
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not ENABLE_MOCKING:
        return False
        
    logger.info(f"MOCK: Uploaded to Firebase: {collection}/{document_id}")
    logger.info(f"MOCK: Data: {data}")
    return True

def mock_gcp_upload(bucket_name: str, source_file_data: bytes, destination_blob_name: str) -> Optional[str]:
    """
    Mock implementation of GCP Storage upload for testing.
    
    Args:
        bucket_name (str): The name of the GCS bucket
        source_file_data (bytes): The file data to upload
        destination_blob_name (str): The name of the blob in GCS
        
    Returns:
        Optional[str]: The public URL of the uploaded file if successful, None otherwise
    """
    if not ENABLE_MOCKING:
        return None
        
    mock_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"
    logger.info(f"MOCK: Uploaded to GCP Storage: {destination_blob_name}")
    logger.info(f"MOCK: URL: {mock_url}")
    return mock_url

def mock_generate_audio(model_key: str, prompt: str, seed: Optional[int] = None) -> bytes:
    """
    Mock implementation of audio generation for testing.
    
    Args:
        model_key (str): The model key
        prompt (str): The text prompt
        seed (Optional[int]): Optional seed for reproducible generation
        
    Returns:
        bytes: Mock audio data
    """
    if not ENABLE_MOCKING:
        raise NotImplementedError("Real audio generation not implemented")
        
    # Generate a mock MP3 file (just some random bytes)
    mock_audio_data = b'MOCK_AUDIO_DATA_' + str(uuid.uuid4()).encode('utf-8')
    
    logger.info(f"MOCK: Generated audio with {model_key}")
    logger.info(f"MOCK: Prompt: {prompt}")
    if seed is not None:
        logger.info(f"MOCK: Seed: {seed}")
        
    return mock_audio_data