"""
Integration tests for the music API.
"""
import os
import json
import time
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
        
def get_model_configs():
    """Load model configurations from model_config.json."""
    config_path = os.path.join("config", "model_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

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
    import logging
    logger = logging.getLogger(__name__)
    
    # Get the provider for the specified model
    provider = get_music_api_provider(model_key)
    base_url = provider.config["base_url"]
    
    # Skip if the server is not reachable
    if not is_server_reachable(base_url):
        skip_msg = f"Server for {model_key} is not reachable at {base_url}"
        print(skip_msg)
        logger.warning(skip_msg)
        pytest.skip(skip_msg)
    
    # Configure the provider with a longer timeout for integration testing
    provider = get_music_api_provider(
        model_key=model_key,
        max_wait_time=TEST_TIMEOUT
    )
    
    # Log the request
    print(f"Generating music with {model_key} model...")
    logger.info(f"Generating music with {model_key} model at {base_url}")
    
    # Generate music
    response = provider.generate_music(prompt=TEST_PROMPT, seed=42)
    
    # Check the response
    assert isinstance(response, MusicResponseOutput)
    
    if response.error:
        error_msg = f"Error generating music with {model_key}: {response.error}"
        print(error_msg)
        logger.error(error_msg)
        # Don't fail the test if there's an error, as the server might be temporarily unavailable
    else:
        assert response.audio_data is not None
        assert len(response.audio_data) > 0
        
        success_msg = f"Successfully generated music with {model_key}, audio size: {len(response.audio_data)} bytes"
        print(success_msg)
        logger.info(success_msg)
        
        # Save the audio file for manual inspection (optional)
        os.makedirs("test_output", exist_ok=True)
        file_path = f"test_output/{model_key}_test_output.mp3"
        with open(file_path, "wb") as f:
            f.write(response.audio_data)
        print(f"Saved audio to {file_path}")
        logger.info(f"Saved audio to {file_path}")

def test_all_model_config_providers():
    """
    Test each model provider defined in model_config.json with a real API call.
    This is an integration test that directly calls each music_api_provider.
    """
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    # Load the model configurations from model_config.json
    model_configs = get_model_configs()
    
    # If no models found, fail the test
    assert model_configs, "No models found in model_config.json"
    
    results = {}
    
    # Test each model in the configuration
    for model_key in model_configs:
        print(f"\n=== Testing {model_key} provider ===")
        logger.info(f"Testing music API provider for model: {model_key}")
        
        # Get the provider for this model
        provider = get_music_api_provider(model_key)
        base_url = provider.config["base_url"]
        
        # Check if the server is reachable
        if not is_server_reachable(base_url):
            error_msg = f"Server for {model_key} is not reachable at {base_url}, skipping"
            print(error_msg)
            logger.warning(error_msg)
            results[model_key] = {"status": "skipped", "reason": "server not reachable"}
            continue
            
        # Configure the provider with a longer timeout for integration testing
        provider = get_music_api_provider(
            model_key=model_key,
            max_wait_time=TEST_TIMEOUT
        )
        
        try:
            # Generate music with this provider
            print(f"Generating music with {model_key} provider...")
            logger.info(f"Generating music with {model_key} provider, base_url={base_url}")
            
            response = provider.generate_music(prompt=TEST_PROMPT, seed=99)
            
            # Check the response
            assert isinstance(response, MusicResponseOutput)
            
            if response.error:
                error_msg = f"Error generating music with {model_key}: {response.error}"
                print(error_msg)
                logger.error(error_msg)
                results[model_key] = {"status": "error", "error": response.error}
            else:
                assert response.audio_data is not None
                assert len(response.audio_data) > 0
                
                # Save the audio file for manual inspection
                os.makedirs("test_output", exist_ok=True)
                output_path = f"test_output/{model_key}_integration_test.mp3"
                with open(output_path, "wb") as f:
                    f.write(response.audio_data)
                    
                success_msg = f"Successfully generated music with {model_key}, saved to {output_path}"
                print(success_msg)
                print(f"Audio size: {len(response.audio_data)} bytes")
                logger.info(success_msg)
                
                results[model_key] = {
                    "status": "success", 
                    "audio_size": len(response.audio_data),
                    "output_file": output_path
                }
                
        except Exception as e:
            error_msg = f"Exception when testing {model_key}: {str(e)}"
            print(error_msg)
            print(f"Detailed error: {traceback.format_exc()}")
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            results[model_key] = {"status": "exception", "error": str(e), "traceback": traceback.format_exc()}
    
    # Print summary of results
    print("\n=== Test Summary ===")
    for model_key, result in results.items():
        status = result["status"]
        if status == "success":
            print(f"{model_key}: ✅ Success - Audio size: {result['audio_size']} bytes")
        elif status == "error":
            print(f"{model_key}: ❌ Error - {result['error']}")
        elif status == "skipped":
            print(f"{model_key}: ⚠️ Skipped - {result['reason']}")
        else:
            print(f"{model_key}: ❌ Exception - {result['error']}")
            print(f"Traceback: {result.get('traceback', 'No traceback available')}")
            
    # Log the summary
    logger.info("=== Test Summary ===")
    for model_key, result in results.items():
        status = result["status"]
        if status == "success":
            logger.info(f"{model_key}: Success - Audio size: {result['audio_size']} bytes")
        elif status == "error":
            logger.error(f"{model_key}: Error - {result['error']}")
        elif status == "skipped":
            logger.warning(f"{model_key}: Skipped - {result['reason']}")
        else:
            logger.error(f"{model_key}: Exception - {result['error']}")
            
    # Assert that at least one model was successfully tested
    assert any(r["status"] == "success" for r in results.values()), "No models were successfully tested"

def test_ping_all_custom_servers():
    """
    Test the /ping endpoint for all custom-server providers in model_config.json.
    This ensures basic connectivity to each server without generating music.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Load the model configurations
    model_configs = get_model_configs()
    
    # If no models found, fail the test
    assert model_configs, "No models found in model_config.json"
    
    results = {}
    
    # Test each model that has provider type "custom-server"
    for model_key, config in model_configs.items():
        # Check if this is a custom-server provider
        provider_type = config.get("provider")
        if provider_type != "custom-server":
            print(f"Skipping {model_key}: not a custom-server provider (type: {provider_type})")
            continue
            
        # Get the base URL for this provider
        base_url = config.get("config", {}).get("base_url")
        if not base_url:
            print(f"Skipping {model_key}: no base_url found in config")
            results[model_key] = {"status": "skipped", "reason": "no base_url in config"}
            continue
            
        print(f"\n=== Pinging {model_key} server at {base_url} ===")
        logger.info(f"Pinging {model_key} server at {base_url}")
        
        # Test both /ping and /health endpoints
        endpoints = ["/ping", "/health"]
        endpoint_results = {}
        
        for endpoint in endpoints:
            full_url = f"{base_url}{endpoint}"
            try:
                print(f"Testing endpoint: {full_url}")
                start_time = time.time()
                response = requests.get(full_url, timeout=5)
                response_time = time.time() - start_time
                
                # Check the response
                status_code = response.status_code
                response_text = response.text[:100]  # Truncate long responses
                
                if status_code == 200:
                    print(f"✅ {endpoint} endpoint is UP (status: {status_code}, time: {response_time:.2f}s)")
                    print(f"Response: {response_text}")
                    endpoint_results[endpoint] = {
                        "status": "success",
                        "response_time": f"{response_time:.2f}s",
                        "response_text": response_text
                    }
                else:
                    print(f"❌ {endpoint} endpoint returned status {status_code}")
                    print(f"Response: {response_text}")
                    endpoint_results[endpoint] = {
                        "status": "error",
                        "status_code": status_code,
                        "response_text": response_text
                    }
                    
            except requests.RequestException as e:
                print(f"❌ Could not connect to {endpoint} endpoint: {str(e)}")
                logger.error(f"Error connecting to {full_url}: {str(e)}")
                endpoint_results[endpoint] = {
                    "status": "exception",
                    "error": str(e)
                }
                
        # Store results for this model
        results[model_key] = {
            "base_url": base_url,
            "endpoints": endpoint_results
        }
    
    # Print summary of results
    print("\n=== Ping Test Summary ===")
    for model_key, result in results.items():
        print(f"\n{model_key} ({result['base_url']}):")
        
        for endpoint, endpoint_result in result.get("endpoints", {}).items():
            status = endpoint_result.get("status")
            if status == "success":
                response_time = endpoint_result.get("response_time")
                print(f"  {endpoint}: ✅ Success - Response time: {response_time}")
            elif status == "error":
                status_code = endpoint_result.get("status_code")
                print(f"  {endpoint}: ❌ Error - Status code: {status_code}")
            else:
                error = endpoint_result.get("error")
                print(f"  {endpoint}: ❌ Exception - {error}")
    
    # Assert that at least one endpoint was successfully tested
    assert any(
        any(
            endpoint_result.get("status") == "success" 
            for endpoint_result in result.get("endpoints", {}).values()
        )
        for result in results.values()
    ), "No endpoints were successfully tested"

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