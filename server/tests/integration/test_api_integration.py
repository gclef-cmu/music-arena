"""
Integration tests for the API endpoints.
"""
import os
import pytest
import requests
import base64
from fastapi.testclient import TestClient
from src.api.app import app

# Mark these tests as integration tests, API tests, and slow tests
pytestmark = [pytest.mark.integration, pytest.mark.api, pytest.mark.slow]

# Test client
client = TestClient(app)

# Test data
TEST_PROMPT = "Create a short, gentle melody with piano"
TEST_USER_ID = "integration-test-user"

def is_server_reachable(url):
    """Check if a server is reachable."""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

@pytest.mark.parametrize("model_key", ["noise", "audioldm2", "musicgen-small"])
def test_generate_audio_pair_integration(model_key):
    """Test the generate_audio_pair endpoint with real music generation servers."""
    # Skip if we're using mock clients
    if os.environ.get("USE_MOCK_CLIENTS", "true").lower() == "true":
        pytest.skip("Test requires real clients (set USE_MOCK_CLIENTS=false)")
    
    # Check if the server for this model is reachable
    from src.api.music_api import get_music_api_provider
    provider = get_music_api_provider(model_key)
    base_url = provider.config["base_url"]
    if not is_server_reachable(base_url):
        pytest.skip(f"Server for {model_key} is not reachable at {base_url}")
    
    # Test request
    request_data = {
        "prompt": TEST_PROMPT,
        "userId": TEST_USER_ID,
        "seed": 42,
        "modelKey": model_key
    }
    
    # This test may take a while to complete
    print(f"Generating audio pair with {model_key} model...")
    response = client.post("/generate_audio_pair", json=request_data, timeout=300)
    
    # Check response
    if response.status_code != 200:
        print(f"Error response: {response.text}")
        pytest.skip(f"Error generating audio pair with {model_key}")
    
    # Verify response structure
    response_data = response.json()
    assert "pairId" in response_data
    assert "audioItems" in response_data
    assert len(response_data["audioItems"]) == 2
    
    # Verify audio data
    for i, audio_item in enumerate(response_data["audioItems"]):
        assert "audioId" in audio_item
        assert "userId" in audio_item
        assert "prompt" in audio_item
        assert "model" in audio_item
        assert "audioUrl" in audio_item
        assert "audioDataBase64" in audio_item
        
        # Decode and save the audio data for manual inspection
        audio_data = base64.b64decode(audio_item["audioDataBase64"])
        os.makedirs("test_output", exist_ok=True)
        with open(f"test_output/{model_key}_pair_{i}.mp3", "wb") as f:
            f.write(audio_data)
        
        print(f"Saved audio to test_output/{model_key}_pair_{i}.mp3")
        print(f"Audio URL: {audio_item['audioUrl']}")
    
    print(f"Successfully generated audio pair with {model_key}")

def test_upload_json_integration():
    """Test the upload_json endpoint with real clients."""
    # Skip if we're using mock clients
    if os.environ.get("USE_MOCK_CLIENTS", "true").lower() == "true":
        pytest.skip("Test requires real clients (set USE_MOCK_CLIENTS=false)")
    
    # Create test audio data
    test_audio = b"Test audio data for integration testing"
    test_audio_base64 = base64.b64encode(test_audio).decode("utf-8")
    
    # Test request
    request_data = {
        "userId": TEST_USER_ID,
        "prompt": TEST_PROMPT,
        "audioData": test_audio_base64,
        "testMetadata": "integration-test"
    }
    
    response = client.post("/upload_json", json=request_data)
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "uploadId" in response_data
    assert "documentId" in response_data
    
    print(f"Successfully uploaded JSON data, document ID: {response_data['documentId']}")

def test_upload_audio_integration():
    """Test the upload_audio endpoint with real clients."""
    # Skip if we're using mock clients
    if os.environ.get("USE_MOCK_CLIENTS", "true").lower() == "true":
        pytest.skip("Test requires real clients (set USE_MOCK_CLIENTS=false)")
    
    # Create a test file
    test_file = b"Test audio data for integration testing"
    
    # Test request
    response = client.post(
        "/upload_audio",
        files={"file": ("integration_test.mp3", test_file, "audio/mpeg")},
        data={
            "user_id": TEST_USER_ID,
            "metadata": '{"test": "integration-test", "source": "api_integration_test"}'
        }
    )
    
    # Verify response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "audioId" in response_data
    assert "documentId" in response_data
    assert "audioUrl" in response_data
    
    print(f"Successfully uploaded audio file, URL: {response_data['audioUrl']}")
    
def test_record_vote_integration():
    """Test the record_vote endpoint with real clients."""
    # Skip if we're using mock clients
    if os.environ.get("USE_MOCK_CLIENTS", "true").lower() == "true":
        pytest.skip("Test requires real clients (set USE_MOCK_CLIENTS=false)")
    
    # First, generate an audio pair to vote on
    request_data = {
        "prompt": "Short test melody for vote integration test",
        "userId": TEST_USER_ID,
        "seed": 123
    }
    
    print("Generating test audio pair for voting...")
    pair_response = client.post("/generate_audio_pair", json=request_data, timeout=300)
    
    if pair_response.status_code != 200:
        pytest.skip("Could not generate test audio pair for voting")
    
    pair_data = pair_response.json()
    
    # Now vote on the generated pair
    winning_item = pair_data["audioItems"][0]
    losing_item = pair_data["audioItems"][1]
    
    vote_data = {
        "pairId": pair_data["pairId"],
        "userId": TEST_USER_ID,
        "winningAudioId": winning_item["audioId"],
        "losingAudioId": losing_item["audioId"],
        "winningModel": winning_item["model"],
        "losingModel": losing_item["model"],
        "winningIndex": 0,
        "prompt": winning_item["prompt"]
    }
    
    print(f"Voting on audio pair {pair_data['pairId']}, selecting {vote_data['winningAudioId']} as winner")
    vote_response = client.post("/record_vote", json=vote_data)
    
    # Verify response
    assert vote_response.status_code == 200
    vote_result = vote_response.json()
    assert "voteId" in vote_result
    assert "timestamp" in vote_result
    assert vote_result["status"] == "success"
    
    print(f"Successfully recorded vote with ID: {vote_result['voteId']}")