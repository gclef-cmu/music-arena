"""
Unit tests for the API endpoints.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()

@patch("src.api.app.get_music_api_provider")
def test_generate_audio_pair(mock_get_provider, client, mock_firebase_client, mock_gcp_client, mock_music_api):
    """Test the generate_audio_pair endpoint."""
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.config = {"base_url": "http://example.com"}
    mock_provider.generate_music.return_value = MagicMock(audio_data=b"mock_audio_data", error=None)
    mock_get_provider.return_value = mock_provider
    
    # Test request
    request_data = {
        "prompt": "Generate a happy tune",
        "userId": "test-user-123",
        "seed": 42,
        "modelKey": "musicgen-small"
    }
    
    response = client.post("/generate_audio_pair", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert "pairId" in response_data
    assert "audioItems" in response_data
    assert len(response_data["audioItems"]) == 2
    
    # Verify that the provider was called with the correct model key
    mock_get_provider.assert_called_once_with(model_key="musicgen-small")
    
    # Verify that generate_music was called twice with the correct parameters
    assert mock_provider.generate_music.call_count == 2
    mock_provider.generate_music.assert_any_call(prompt="Generate a happy tune", seed=42)
    mock_provider.generate_music.assert_any_call(prompt="Generate a happy tune", seed=43)  # seed + 1

@patch("src.api.app.get_music_api_provider")
def test_generate_audio_pair_with_default_model(mock_get_provider, client, mock_firebase_client, mock_gcp_client, mock_music_api):
    """Test the generate_audio_pair endpoint with default model."""
    # Setup mock provider
    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.config = {"base_url": "http://example.com"}
    mock_provider.generate_music.return_value = MagicMock(audio_data=b"mock_audio_data", error=None)
    mock_get_provider.return_value = mock_provider
    
    # Test request without modelKey
    request_data = {
        "prompt": "Generate a happy tune",
        "userId": "test-user-123",
        "seed": 42
    }
    
    response = client.post("/generate_audio_pair", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    
    # Verify that the provider was called with the default model key
    mock_get_provider.assert_called_once_with(model_key="musicgen-small")

@patch("src.api.app.get_music_api_provider")
def test_generate_audio_pair_error_handling(mock_get_provider, client, mock_firebase_client, mock_gcp_client):
    """Test error handling in the generate_audio_pair endpoint."""
    # Setup mock provider with error
    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.config = {"base_url": "http://example.com"}
    mock_provider.generate_music.return_value = MagicMock(audio_data=None, error="Test error")
    mock_get_provider.return_value = mock_provider
    
    # Test request
    request_data = {
        "prompt": "Generate a happy tune",
        "userId": "test-user-123"
    }
    
    response = client.post("/generate_audio_pair", json=request_data)
    
    # Verify response
    assert response.status_code == 500
    assert "Error generating first audio" in response.json()["detail"]

def test_upload_json(client, mock_firebase_client, mock_gcp_client):
    """Test the upload_json endpoint."""
    # Test request
    request_data = {
        "userId": "test-user-123",
        "prompt": "Test prompt",
        "audioData": "bW9ja19hdWRpb19kYXRh"  # Base64 encoded "mock_audio_data"
    }
    
    response = client.post("/upload_json", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "uploadId" in response_data
    assert "documentId" in response_data

def test_upload_audio(client, mock_firebase_client, mock_gcp_client):
    """Test the upload_audio endpoint."""
    # Create a test file
    test_file = b"mock_audio_data"
    
    # Test request
    response = client.post(
        "/upload_audio",
        files={"file": ("test.mp3", test_file, "audio/mpeg")},
        data={"user_id": "test-user-123", "metadata": json.dumps({"test": "metadata"})}
    )
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "audioId" in response_data
    assert "documentId" in response_data
    assert "audioUrl" in response_data