import requests
import json
import base64
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API base URL
BASE_URL = "http://localhost:12000"

def test_health():
    """Test the health check endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health check response: {response.status_code}")
    print(response.json())

def test_upload_json():
    """Test uploading JSON data."""
    # Sample data
    data = {
        "userId": "test_user_123",
        "metadata": {
            "title": "Test Audio",
            "description": "This is a test audio file"
        }
    }
    
    # If you have a sample audio file, you can include it as base64
    sample_audio_path = "sample_audio.mp3"
    if os.path.exists(sample_audio_path):
        with open(sample_audio_path, "rb") as f:
            audio_data = f.read()
            data["audioData"] = base64.b64encode(audio_data).decode("utf-8")
    
    # Send request
    response = requests.post(f"{BASE_URL}/upload_json", json=data)
    print(f"Upload JSON response: {response.status_code}")
    print(response.json())

def test_upload_audio():
    """Test uploading an audio file."""
    # Sample data
    user_id = "test_user_123"
    metadata = json.dumps({
        "title": "Test Audio File",
        "description": "This is a test audio file upload"
    })
    
    # Sample audio file
    sample_audio_path = "sample_audio.mp3"
    if not os.path.exists(sample_audio_path):
        print(f"Sample audio file not found: {sample_audio_path}")
        return
    
    # Send request
    with open(sample_audio_path, "rb") as f:
        files = {"file": f}
        data = {"user_id": user_id, "metadata": metadata}
        response = requests.post(f"{BASE_URL}/upload_audio", files=files, data=data)
        print(f"Upload audio response: {response.status_code}")
        print(response.json())

if __name__ == "__main__":
    print("Testing API endpoints...")
    test_health()
    test_upload_json()
    # Uncomment to test audio upload if you have a sample file
    # test_upload_audio()