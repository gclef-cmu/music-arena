"""
Unit tests for the music API.
"""
import os
import json
import pytest
import aiohttp
from unittest.mock import patch, mock_open
from src.api.music_api import get_music_api_provider, CustomServerMusicAPIProvider, MusicResponseOutput

# Mark all tests in this module as unit tests and music tests
pytestmark = [pytest.mark.unit, pytest.mark.music]

# Sample model configuration for testing
SAMPLE_MODEL_CONFIG = {
    "noise": {
        "provider": "custom-server",
        "model_name": "noise",
        "config": {
            "base_url": "http://treble.cs.cmu.edu:54408",
            "check_interval": 1.0,
            "max_wait_time": 5.0
        }
    },
    "audioldm2": {
        "provider": "custom-server",
        "model_name": "audioldm2",
        "config": {
            "base_url": "http://treble.cs.cmu.edu:51759",
            "check_interval": 1.0,
            "max_wait_time": 60.0
        }
    }
}

def test_custom_server_music_api_provider_validate_config():
    """Test that the CustomServerMusicAPIProvider validates its configuration correctly."""
    # Valid configuration
    valid_config = {
        "base_url": "http://example.com",
        "check_interval": 1.0,
        "max_wait_time": 60.0
    }
    provider = CustomServerMusicAPIProvider("test-model", **valid_config)
    assert provider.model_name == "test-model"
    assert provider.config == valid_config
    
    # Invalid configuration - missing required key
    invalid_config = {
        "base_url": "http://example.com",
        "check_interval": 1.0
        # Missing max_wait_time
    }
    with pytest.raises(ValueError, match="Missing required config key: max_wait_time"):
        CustomServerMusicAPIProvider("test-model", **invalid_config)

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data=json.dumps(SAMPLE_MODEL_CONFIG))
def test_get_music_api_provider_with_config_file(mock_file, mock_exists):
    """Test that get_music_api_provider loads configuration from a file."""
    mock_exists.return_value = True
    
    # Test with existing model key
    provider = get_music_api_provider("noise")
    assert provider.model_name == "noise"
    assert provider.config["base_url"] == "http://treble.cs.cmu.edu:54408"
    assert provider.config["check_interval"] == 1.0
    assert provider.config["max_wait_time"] == 5.0
    
    # Test with non-existent model key
    provider = get_music_api_provider("non-existent-model")
    assert provider.model_name == "non-existent-model"
    assert provider.config["base_url"] == "http://localhost:5000"  # Default value
    
    # Test with kwargs overriding config
    provider = get_music_api_provider("noise", base_url="http://override.example.com")
    assert provider.config["base_url"] == "http://override.example.com"

@patch("os.path.exists")
def test_get_music_api_provider_without_config_file(mock_exists):
    """Test that get_music_api_provider uses default configuration when no file exists."""
    mock_exists.return_value = False
    
    provider = get_music_api_provider("test-model")
    assert provider.model_name == "test-model"
    assert provider.config["base_url"] == "http://localhost:5000"
    assert provider.config["check_interval"] == 1.0
    assert provider.config["max_wait_time"] == 60.0

@patch("aiohttp.ClientSession.post")
@patch("aiohttp.ClientSession.get")
@pytest.mark.asyncio
async def test_generate_music_success(mock_get, mock_post):
    """Test successful music generation."""
    # Mock the API responses
    mock_post_context = mock_post.return_value.__aenter__.return_value
    mock_post_context.json.return_value = {"job_id": "test-job-id"}
    mock_post_context.raise_for_status = lambda: None
    
    # Create proper mock responses for status and download
    mock_status_context = mock_get.return_value.__aenter__.return_value
    mock_status_context.json.return_value = {"status": "COMPLETE"}
    mock_status_context.raise_for_status = lambda: None
    
    mock_download_context = mock_get.return_value.__aenter__.return_value
    mock_download_context.read.return_value = b"mock_audio_data"
    mock_download_context.raise_for_status = lambda: None
    
    # Set up the side effect sequence for get
    mock_get.return_value.__aenter__.side_effect = [mock_status_context, mock_download_context]
    
    provider = CustomServerMusicAPIProvider(
        "test-model",
        base_url="http://example.com",
        check_interval=0.1,
        max_wait_time=1.0
    )
    
    # Call the async method and await the result
    response = await provider.generate_music("test prompt", seed=42)
    
    assert isinstance(response, MusicResponseOutput)
    assert response.audio_data == b"mock_audio_data"
    assert response.error is None

@patch("aiohttp.ClientSession.post")
@patch("aiohttp.ClientSession.get")
@pytest.mark.asyncio
async def test_generate_music_error(mock_get, mock_post):
    """Test music generation with error."""
    # Mock the API responses
    mock_post_context = mock_post.return_value.__aenter__.return_value
    mock_post_context.json.return_value = {"job_id": "test-job-id"}
    mock_post_context.raise_for_status = lambda: None
    
    # Create proper mock response for status
    mock_status_context = mock_get.return_value.__aenter__.return_value
    mock_status_context.json.return_value = {"status": "ERROR"}
    mock_status_context.raise_for_status = lambda: None
    
    # Set up the side effect sequence for get
    mock_get.return_value.__aenter__.return_value = mock_status_context
    
    provider = CustomServerMusicAPIProvider(
        "test-model",
        base_url="http://localhost:5000",
        check_interval=0.1,
        max_wait_time=1.0
    )
    
    # Call the async method and await the result
    response = await provider.generate_music("test prompt")
    
    assert isinstance(response, MusicResponseOutput)
    assert response.audio_data is None
    assert "failed during processing" in response.error

@patch("aiohttp.ClientSession.post")
@patch("aiohttp.ClientSession.get")
@pytest.mark.asyncio
async def test_generate_music_timeout(mock_get, mock_post):
    """Test music generation with timeout."""
    # Mock the API responses
    mock_post_context = mock_post.return_value.__aenter__.return_value
    mock_post_context.json.return_value = {"job_id": "test-job-id"}
    mock_post_context.raise_for_status = lambda: None
    
    # Create proper mock response for status
    mock_status_context = mock_get.return_value.__aenter__.return_value
    mock_status_context.json.return_value = {"status": "PROCESSING"}
    mock_status_context.raise_for_status = lambda: None
    
    # Set up the side effect sequence for get - always return processing
    mock_get.return_value.__aenter__.return_value = mock_status_context
    
    provider = CustomServerMusicAPIProvider(
        "test-model",
        base_url="http://localhost:5000",
        check_interval=0.1,
        max_wait_time=0.2  # Very short timeout for testing
    )
    
    # Call the async method and await the result
    response = await provider.generate_music("test prompt")
    
    assert isinstance(response, MusicResponseOutput)
    assert response.audio_data is None
    assert "timed out" in response.error