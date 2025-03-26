"""
Basic unit tests to verify the test setup.
"""
import pytest
from src.api.music_api import CustomServerMusicAPIProvider

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

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