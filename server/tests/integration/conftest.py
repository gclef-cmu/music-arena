"""
Configuration for integration tests.
"""
import os
import pytest
import requests
from fastapi.testclient import TestClient
from src.api.app import app

@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.
    """
    return TestClient(app)

@pytest.fixture
def test_prompt():
    """
    Return a test prompt for music generation.
    """
    return "Create a short, gentle melody with piano"

@pytest.fixture
def test_user_id():
    """
    Return a test user ID.
    """
    return "integration-test-user"

@pytest.fixture
def is_server_reachable():
    """
    Function to check if a server is reachable.
    """
    def _is_server_reachable(url):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    return _is_server_reachable

@pytest.fixture(scope="session")
def test_output_dir():
    """
    Create and return the test output directory.
    """
    output_dir = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir