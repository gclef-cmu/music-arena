"""
Configuration for unit tests.
"""
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_response():
    """
    Create a mock HTTP response.
    """
    class MockResponse:
        def __init__(self, json_data=None, status_code=200, content=None):
            self.json_data = json_data
            self.status_code = status_code
            self.content = content
            
        def json(self):
            return self.json_data
            
        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP Error: {self.status_code}")
    
    return MockResponse

@pytest.fixture
def mock_model_config():
    """
    Create a mock model configuration.
    """
    return {
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
        },
        "musicgen-small": {
            "provider": "custom-server",
            "model_name": "musicgen-small",
            "config": {
                "base_url": "http://treble.cs.cmu.edu:22709",
                "check_interval": 1.0,
                "max_wait_time": 60.0
            }
        }
    }

@pytest.fixture
def mock_audio_data():
    """
    Create mock audio data.
    """
    return b"mock_audio_data"