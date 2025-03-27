import logging

logger = logging.getLogger(__name__)

class MockGCPClient:
    """
    Mock GCP client for testing without a real GCP connection.
    """
    def __init__(self):
        """
        Initialize mock client.
        """
        self.uploaded_files = {}
        logger.info("Initialized MockGCPClient")
    
    def upload_file(self, bucket_name: str, file_data: bytes, destination_blob_name: str):
        """
        Upload a file to a mock GCS bucket.
        
        Args:
            bucket_name: Name of the bucket to upload to
            file_data: Binary data to upload
            destination_blob_name: Name of the destination blob
            
        Returns:
            str: A mock URL for the uploaded file
        """
        if bucket_name not in self.uploaded_files:
            self.uploaded_files[bucket_name] = {}
        
        self.uploaded_files[bucket_name][destination_blob_name] = file_data
        logger.info(f"Mock file uploaded to bucket '{bucket_name}' as '{destination_blob_name}'")
        
        # Return a mock URL
        return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"