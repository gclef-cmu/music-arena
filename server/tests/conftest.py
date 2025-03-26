"""
Configuration for pytest.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create a mock app for testing
app = FastAPI(title="Music Arena API Test", version="0.1.0")

# Add test routes to the mock app
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}

@app.post("/generate_audio_pair")
async def generate_audio_pair(request: Request):
    """Mock generate_audio_pair endpoint."""
    data = await request.json()
    
    # Check if there's an error condition to simulate
    if "error" in data:
        return JSONResponse(status_code=500, content={"detail": "Error generating audio"})
    
    # Create mock audio items
    audio_items = [
        {
            "audioId": "test-audio-id-1",
            "userId": data.get("userId", "test-user"),
            "prompt": data.get("prompt", "test prompt"),
            "model": "test-model",
            "latency": 1.0,
            "seed": data.get("seed", 42),
            "pairAudioId": "test-audio-id-2",
            "pairIndex": 0,
            "audioUrl": "https://example.com/test1.mp3",
            "audioData": "bW9ja19hdWRpb19kYXRh"  # Base64 encoded "mock_audio_data"
        },
        {
            "audioId": "test-audio-id-2",
            "userId": data.get("userId", "test-user"),
            "prompt": data.get("prompt", "test prompt"),
            "model": "test-model",
            "latency": 1.0,
            "seed": data.get("seed", 43) if data.get("seed") is not None else 43,
            "pairAudioId": "test-audio-id-1",
            "pairIndex": 1,
            "audioUrl": "https://example.com/test2.mp3",
            "audioData": "bW9ja19hdWRpb19kYXRh"  # Base64 encoded "mock_audio_data"
        }
    ]
    
    return {"pairId": "test-pair-id", "audioItems": audio_items}

@app.post("/upload_json")
async def upload_json(request: Request):
    """Mock upload_json endpoint."""
    return {"status": "success", "uploadId": "test-upload-id", "documentId": "test-doc-id"}

@app.post("/upload_audio")
async def upload_audio(request: Request):
    """Mock upload_audio endpoint."""
    return {"status": "success", "audioId": "test-audio-id", "documentId": "test-doc-id", "audioUrl": "https://example.com/test.mp3"}

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