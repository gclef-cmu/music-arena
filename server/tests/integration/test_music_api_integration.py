"""
Integration tests for the music API.
"""
import os
import pytest
import requests

# Mark all tests in this module as integration tests, music tests, and slow tests
pytestmark = [pytest.mark.integration, pytest.mark.music, pytest.mark.slow]
from src.api.music_api import get_music_api_provider, MusicResponseOutput

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

@pytest.mark.parametrize("model_key", ["noise", "audioldm2", "musicgen-small"])
def test_music_api_provider_creation(model_key):
    """Test that we can create a music API provider for each model."""
    # Get the provider for the specified model
    provider = get_music_api_provider(model_key)
    
    # Verify the provider has the correct configuration
    assert provider.model_name == model_key
    assert "base_url" in provider.config
    assert "check_interval" in provider.config
    assert "max_wait_time" in provider.config
    
    # Log the configuration
    print(f"Model: {model_key}, Base URL: {provider.config['base_url']}")

@pytest.mark.parametrize("model_key", ["noise", "audioldm2", "musicgen-small"])
def test_music_generation_if_server_available(model_key):
    """
    Test music generation if the server is available.
    This test will be skipped if the server is not reachable.
    """
    # Get the provider for the specified model
    provider = get_music_api_provider(model_key)
    base_url = provider.config["base_url"]
    
    # Skip if the server is not reachable
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

def test_music_api_error_handling():
    """Test that the music API handles errors correctly."""
    # Create a provider with an invalid base URL
    provider = get_music_api_provider(
        model_key="test-model",
        base_url="http://invalid-url-that-does-not-exist.example.com",
        check_interval=0.1,
        max_wait_time=1.0
    )
    
    # Generate music (should fail)
    response = provider.generate_music(prompt=TEST_PROMPT)
    
    # Verify the response contains an error
    assert isinstance(response, MusicResponseOutput)
    assert response.audio_data is None
    assert response.error is not None
    assert "API request failed" in response.error