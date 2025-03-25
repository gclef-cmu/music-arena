import requests
import json
import sys

def test_generate_audio_pair():
    """Test the generate_audio_pair endpoint."""
    url = "http://localhost:12000/api/generate_audio_pair"
    
    payload = {
        "model1": "noise",
        "model2": "musicgen-small",
        "prompt1": "Create a noisy background",
        "prompt2": "Create an upbeat electronic dance track",
        "seed1": 42,
        "seed2": 123
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = test_generate_audio_pair()
    sys.exit(0 if success else 1)