import os
import base64
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

class FirebaseClient:
    def __init__(self):
        """
        Initialize Firebase client with credentials from either a config file or environment variables.
        """
        firebase_config_path = "config/firebase_config.json"
        if os.path.exists(firebase_config_path):
            self.cred = credentials.Certificate(firebase_config_path)
        else:
            load_dotenv(find_dotenv())
            encoded_key = os.getenv("FIREBASE_ACCOUNT_KEY")
            if not encoded_key:
                raise ValueError("FIREBASE_ACCOUNT_KEY environment variable not set")
            config_dict = json.loads(base64.b64decode(encoded_key).decode("utf-8"))
            self.cred = credentials.Certificate(config_dict)
        
        # Initialize Firebase app if not already initialized
        if not firebase_admin._apps:
            firebase_admin.initialize_app(self.cred)
        
        self.db = firestore.client()
    
    def upload_data(self, collection_name: str, data: dict):
        """
        Upload data to a Firebase Firestore collection.
        
        Args:
            collection_name: Name of the collection to upload to
            data: Dictionary containing the data to upload
        """
        try:
            collection_ref = self.db.collection(collection_name)
            doc_ref = collection_ref.add(data)
            logger.info(f"Data uploaded to Firebase collection '{collection_name}'")
            return doc_ref[1].id  # Return the document ID
        except Exception as e:
            logger.error(f"Error uploading data to Firebase: {str(e)}")
            raise