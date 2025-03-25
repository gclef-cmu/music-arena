import logging
import os
import base64

logger = logging.getLogger(__name__)

class MockGCPClient:
    """
    Mock implementation of GCPClient for testing without actual GCP connection.
    """
    def __init__(self):
        """Initialize the mock client."""
        self.data_dir = "mock_data"
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("Initialized MockGCPClient")
    
    def upload_file(self, bucket_name: str, file_data: bytes, destination_blob_name: str):
        """
        Mock upload a file to a bucket.
        
        Args:
            bucket_name: Name of the bucket
            file_data: Binary data of the file to upload
            destination_blob_name: Path within the bucket to store the file
            
        Returns:
            Public URL of the uploaded file
        """
        bucket_dir = os.path.join(self.data_dir, bucket_name)
        os.makedirs(bucket_dir, exist_ok=True)
        
        # Create directories for the blob path if needed
        blob_path = os.path.join(bucket_dir, destination_blob_name)
        os.makedirs(os.path.dirname(blob_path), exist_ok=True)
        
        # Save the file
        with open(blob_path, 'wb') as f:
            f.write(file_data)
        
        # Generate a mock public URL
        public_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"
        
        logger.info(f"Mock file uploaded to gs://{bucket_name}/{destination_blob_name}")
        return public_url