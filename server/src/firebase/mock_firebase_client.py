import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class MockFirebaseClient:
    """
    Mock implementation of FirebaseClient for testing without actual Firebase connection.
    """
    def __init__(self):
        """Initialize the mock client."""
        self.data_dir = "mock_data"
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info("Initialized MockFirebaseClient")
    
    def upload_data(self, collection_name: str, data: dict):
        """
        Mock upload data to a collection.
        
        Args:
            collection_name: Name of the collection
            data: Dictionary containing the data to upload
        """
        collection_dir = os.path.join(self.data_dir, collection_name)
        os.makedirs(collection_dir, exist_ok=True)
        
        # Generate a document ID
        doc_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(data)}"
        
        # Save the data to a JSON file
        file_path = os.path.join(collection_dir, f"{doc_id}.json")
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Mock data uploaded to collection '{collection_name}' with ID '{doc_id}'")
        return doc_id