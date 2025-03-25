import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Initialize Firebase
try:
    # Check if already initialized
    firebase_admin.get_app()
except ValueError:
    # Initialize with service account
    try:
        cred = credentials.Certificate("firebase-credentials.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")

def upload_to_firebase(
    collection: str, 
    document_id: str, 
    data: Dict[str, Any]
) -> bool:
    """
    Upload data to Firebase Firestore.
    
    Args:
        collection (str): The collection name
        document_id (str): The document ID
        data (Dict[str, Any]): The data to upload
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        db = firestore.client()
        doc_ref = db.collection(collection).document(document_id)
        doc_ref.set(data)
        logger.info(f"Successfully uploaded data to Firebase: {collection}/{document_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload data to Firebase: {e}")
        return False

def get_from_firebase(
    collection: str, 
    document_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get data from Firebase Firestore.
    
    Args:
        collection (str): The collection name
        document_id (str): The document ID
        
    Returns:
        Optional[Dict[str, Any]]: The data if successful, None otherwise
    """
    try:
        db = firestore.client()
        doc_ref = db.collection(collection).document(document_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            logger.warning(f"Document {collection}/{document_id} does not exist")
            return None
    except Exception as e:
        logger.error(f"Failed to get data from Firebase: {e}")
        return None