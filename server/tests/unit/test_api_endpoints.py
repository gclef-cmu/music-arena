"""
Unit tests for the API endpoints.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

# Mark all tests in this module as unit tests and API tests
pytestmark = [pytest.mark.unit, pytest.mark.api]

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()

def test_generate_audio_pair(client):
    """Test the generate_audio_pair endpoint."""
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
    
    # Verify the response data contains the expected fields
    for item in response_data["audioItems"]:
        assert "audioId" in item
        assert "userId" in item
        assert "prompt" in item
        assert "model" in item
        assert "audioUrl" in item
        assert "audioDataBase64" in item

def test_generate_audio_pair_with_default_model(client):
    """Test the generate_audio_pair endpoint with default model."""
    # Test request without modelKey
    request_data = {
        "prompt": "Generate a happy tune",
        "userId": "test-user-123",
        "seed": 42
    }
    
    response = client.post("/generate_audio_pair", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert "pairId" in response_data
    assert "audioItems" in response_data
    assert len(response_data["audioItems"]) == 2

def test_generate_audio_pair_error_handling(client):
    """Test error handling in the generate_audio_pair endpoint."""
    # Test request with error flag
    request_data = {
        "prompt": "Generate a happy tune",
        "userId": "test-user-123",
        "error": True  # This will trigger the error response in our mock endpoint
    }
    
    response = client.post("/generate_audio_pair", json=request_data)
    
    # Verify response
    assert response.status_code == 500
    assert "Error generating audio" in response.json()["detail"]

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
    
def test_record_vote(client, mock_firebase_client):
    """Test the record_vote endpoint."""
    # Test request
    request_data = {
        "pairId": "test-pair-id",
        "userId": "test-user-123",
        "winningAudioId": "test-audio-id-1",
        "losingAudioId": "test-audio-id-2",
        "winningModel": "musicgen-small",
        "losingModel": "musicgen-large",
        "winningIndex": 0,
        "prompt": "Test melody for voting"
    }
    
    response = client.post("/record_vote", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert "voteId" in response_data
    assert "timestamp" in response_data
    assert response_data["status"] == "success"

def test_generate_audio_pair_with_lyrics(client, mock_firebase_client, mock_gcp_client):
    """Test that generate_audio_pair samples from lyrics models when lyrics=True."""
    # Mock the sample_random_models method to verify it's called with the correct config
    with patch('src.api.app.FastAPIApp.sample_random_models') as mock_sample:
        # Mock the return value of sample_random_models
        mock_sample.return_value = ['songgen', 'songgen']
        
        # Test request with lyrics=True
        request_data = {
            "prompt": "Generate a song with lyrics",
            "userId": "test-user-123",
            "lyrics": True
        }
        
        response = client.post("/generate_audio_pair", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        
        # Verify that sample_random_models was called with lyrics_model_configs
        mock_sample.assert_called_once()
        args, kwargs = mock_sample.call_args
        assert args[0] == client.app.lyrics_model_configs  # Should use lyrics config
        assert kwargs.get('count', 2) == 2  # Default count should be 2

def test_generate_audio_pair_without_lyrics(client, mock_firebase_client, mock_gcp_client):
    """Test that generate_audio_pair samples from instrumental models when lyrics=False."""
    # Mock the sample_random_models method to verify it's called with the correct config
    with patch('src.api.app.FastAPIApp.sample_random_models') as mock_sample:
        # Mock the return value of sample_random_models
        mock_sample.return_value = ['musicgen-small', 'musicgen-large']
        
        # Test request with lyrics=False (default)
        request_data = {
            "prompt": "Generate an instrumental piece",
            "userId": "test-user-123"
        }
        
        response = client.post("/generate_audio_pair", json=request_data)
        
        # Verify response
        assert response.status_code == 200
        
        # Verify that sample_random_models was called with instrumental_model_configs
        mock_sample.assert_called_once()
        args, kwargs = mock_sample.call_args
        assert args[0] == client.app.instrumental_model_configs  # Should use instrumental config
        assert kwargs.get('count', 2) == 2  # Default count should be 2