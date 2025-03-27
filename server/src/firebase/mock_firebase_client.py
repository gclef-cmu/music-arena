import logging
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MockFirebaseClient:
    """
    Mock Firebase client for testing without a real Firebase connection.
    """
    def __init__(self):
        """
        Initialize mock client with an in-memory database.
        """
        self.data = {}
        logger.info("Initialized MockFirebaseClient")
    
    def upload_data(self, collection_name: str, data: dict):
        """
        Upload data to a mock collection.
        
        Args:
            collection_name: Name of the collection to upload to
            data: Dictionary containing the data to upload
            
        Returns:
            str: The ID of the created document
        """
        if collection_name not in self.data:
            self.data[collection_name] = {}
        
        doc_id = str(uuid.uuid4())
        self.data[collection_name][doc_id] = data.copy()
        logger.info(f"Mock data uploaded to collection '{collection_name}' with ID {doc_id}")
        return doc_id
    
    def get_collection_data(self, collection_name: str):
        """
        Get all documents from a mock collection.
        
        Args:
            collection_name: Name of the collection to retrieve
            
        Returns:
            dict: Dictionary of document IDs to document data
        """
        if collection_name not in self.data:
            self.data[collection_name] = {}
        
        logger.info(f"Retrieved {len(self.data[collection_name])} documents from mock collection '{collection_name}'")
        return self.data[collection_name]