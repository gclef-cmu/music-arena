"""
Configuration for pytest.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create a mock app for testing
app = FastAPI(title="Music Arena API Test", version="0.1.0")

@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.
    """
    return TestClient(app)

@pytest.fixture
def mock_firebase_client(monkeypatch):
    """
    Mock the Firebase client for testing.
    """
    class MockFirebaseClient:
        def upload_data(self, collection, data):
            return "mock-doc-id"
    
    from src.firebase.firebase_client import FirebaseClient
    monkeypatch.setattr(FirebaseClient, "upload_data", MockFirebaseClient().upload_data)
    return MockFirebaseClient()

@pytest.fixture
def mock_gcp_client(monkeypatch):
    """
    Mock the GCP client for testing.
    """
    class MockGCPClient:
        def upload_file(self, bucket_name, file_data, destination_blob_name):
            return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"
    
    from src.gcp.gcp_client import GCPClient
    monkeypatch.setattr(GCPClient, "upload_file", MockGCPClient().upload_file)
    return MockGCPClient()

@pytest.fixture
def mock_music_api(monkeypatch):
    """
    Mock the music API for testing.
    """
    class MockMusicResponseOutput:
        def __init__(self, audio_data=b"mock_audio_data", error=None):
            self.audio_data = audio_data
            self.error = error
    
    class MockMusicAPIProvider:
        def __init__(self, model_name, **config):
            self.model_name = model_name
            self.config = config
        
        def generate_music(self, prompt, seed=None):
            return MockMusicResponseOutput()
    
    from src.api.music_api import get_music_api_provider
    monkeypatch.setattr("src.api.music_api.get_music_api_provider", 
                        lambda model_key, **kwargs: MockMusicAPIProvider(model_key, **kwargs))
    return MockMusicAPIProvider