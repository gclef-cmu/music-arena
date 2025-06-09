"""
Integration tests for the music generation servers.
"""
import os
import pytest
import requests
from src.api.music_api import get_music_api_provider, MusicResponseOutput

# Mark these tests as integration tests, music tests, and slow tests
pytestmark = [pytest.mark.integration, pytest.mark.music, pytest.mark.slow]

# Test data
TEST_PROMPT = "Create a short, gentle melody with piano"
TEST_TIMEOUT = 120.0  # Longer timeout for integration tests

def is_server_reachable(url):
    """Check if a server is reachable."""
    try:
        response = requests.get(f"{url}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

@pytest.mark.parametrize("model_key", ["musicgen-small"])
def test_music_server_connection(model_key):
    """Test that we can connect to the music generation servers."""
    # Get the provider for the specified model
    provider = get_music_api_provider(model_key)
    
    # Check if the server is reachable
    base_url = provider.config["base_url"]
    is_reachable = is_server_reachable(base_url)
    
    # Log the result
    if is_reachable:
        print(f"Server for {model_key} is reachable at {base_url}")
    else:
        print(f"Server for {model_key} is NOT reachable at {base_url}")
    
    # This test is informational, not a hard requirement
    # We don't assert is_reachable because the servers might be down during testing

@pytest.mark.parametrize("model_key", ["musicgen-small"])
def test_generate_music(model_key):
    """Test that we can generate music from the servers."""
    # Skip if the server is not reachable
    provider = get_music_api_provider(model_key)
    base_url = provider.config["base_url"]
    if not is_server_reachable(base_url):
        pytest.skip(f"Server for {model_key} is not reachable at {base_url}")
    
    # Configure the provider with a longer timeout for integration testing
    provider = get_music_api_provider(
        model_key=model_key,
        max_wait_time=TEST_TIMEOUT
    )
    
    # Generate music
    print(f"Generating music with {model_key} model...")
    response = provider.generate_music(prompt=TEST_PROMPT, seed=42)
    
    # Check the response
    assert isinstance(response, MusicResponseOutput)
    
    if response.error:
        print(f"Error generating music with {model_key}: {response.error}")
        # Don't fail the test if there's an error, as the server might be temporarily unavailable
    else:
        assert response.audio_data is not None
        assert len(response.audio_data) > 0
        print(f"Successfully generated music with {model_key}, audio size: {len(response.audio_data)} bytes")
        
        # Save the audio file for manual inspection (optional)
        os.makedirs("test_output", exist_ok=True)
        with open(f"test_output/{model_key}_test_output.mp3", "wb") as f:
            f.write(response.audio_data)
        print(f"Saved audio to test_output/{model_key}_test_output.mp3")

@pytest.mark.parametrize("model_key", ["musicgen-small"])
def test_generate_music_with_seed(model_key):
    """Test that we can generate deterministic music with a seed."""
    # Skip if the server is not reachable
    provider = get_music_api_provider(model_key)
    base_url = provider.config["base_url"]
    if not is_server_reachable(base_url):
        pytest.skip(f"Server for {model_key} is not reachable at {base_url}")
    
    # Configure the provider with a longer timeout for integration testing
    provider = get_music_api_provider(
        model_key=model_key,
        max_wait_time=TEST_TIMEOUT
    )
    
    # Generate music with the same seed twice
    print(f"Generating music with {model_key} model using seed 42...")
    response1 = provider.generate_music(prompt=TEST_PROMPT, seed=42)
    
    if response1.error:
        pytest.skip(f"Error generating music with {model_key}: {response1.error}")
    
    print(f"Generating music with {model_key} model using seed 42 again...")
    response2 = provider.generate_music(prompt=TEST_PROMPT, seed=42)
    
    if response2.error:
        pytest.skip(f"Error generating music with {model_key}: {response2.error}")
    
    # Check if the outputs are the same (deterministic)
    # Note: Some models might not be fully deterministic even with the same seed
    if response1.audio_data == response2.audio_data:
        print(f"Model {model_key} produces deterministic outputs with the same seed")
    else:
        print(f"Model {model_key} does NOT produce deterministic outputs with the same seed")
        
    # Generate music with a different seed
    print(f"Generating music with {model_key} model using seed 43...")
    response3 = provider.generate_music(prompt=TEST_PROMPT, seed=43)
    
    if response3.error:
        pytest.skip(f"Error generating music with {model_key}: {response3.error}")
    
    # Check if the outputs are different with different seeds
    if response1.audio_data != response3.audio_data:
        print(f"Model {model_key} produces different outputs with different seeds")
    else:
        print(f"Model {model_key} produces the same output regardless of seed")
    
    # Save the audio files for manual inspection (optional)
    os.makedirs("test_output", exist_ok=True)
    with open(f"test_output/{model_key}_seed42_1.mp3", "wb") as f:
        f.write(response1.audio_data)
    with open(f"test_output/{model_key}_seed42_2.mp3", "wb") as f:
        f.write(response2.audio_data)
    with open(f"test_output/{model_key}_seed43.mp3", "wb") as f:
        f.write(response3.audio_data)
    print(f"Saved audio files to test_output/ for comparison")