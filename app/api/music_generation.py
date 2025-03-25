import json
import logging
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional, Tuple

from app.utils.music_api_provider import get_music_api_provider
from app.utils.firebase_utils import upload_to_firebase
from app.utils.gcp_storage_utils import upload_to_gcp_storage
from app.utils.mock_utils import mock_firebase_upload, mock_gcp_upload, mock_generate_audio, ENABLE_MOCKING

logger = logging.getLogger(__name__)

# Create a Blueprint for the music generation API
music_generation_bp = Blueprint('music_generation', __name__)

# Load model configuration
with open(os.path.join(os.path.dirname(__file__), '../config/model_config.json'), 'r') as f:
    MODEL_CONFIG = json.load(f)

# GCP Storage bucket name
GCP_BUCKET_NAME = os.environ.get('GCP_BUCKET_NAME', 'music-arena-audio')

# Firebase collection name
FIREBASE_COLLECTION = 'audio_pairs'

@music_generation_bp.route('/generate_audio_pair', methods=['POST'])
def generate_audio_pair():
    """
    Generate an audio pair using the specified models and prompts.
    
    Request JSON format:
    {
        "model1": "noise",
        "model2": "musicgen-small",
        "prompt1": "Create a noisy background",
        "prompt2": "Create an upbeat electronic dance track",
        "seed1": 42,  # Optional
        "seed2": 123  # Optional
    }
    
    Returns:
        JSON response with the generated audio URLs and metadata
    """
    try:
        # Parse request data
        data = request.json
        
        # Validate required fields
        required_fields = ['model1', 'model2', 'prompt1', 'prompt2']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Extract request parameters
        model1 = data['model1']
        model2 = data['model2']
        prompt1 = data['prompt1']
        prompt2 = data['prompt2']
        seed1 = data.get('seed1')
        seed2 = data.get('seed2')
        
        # Validate models
        if model1 not in MODEL_CONFIG:
            return jsonify({'error': f'Invalid model1: {model1}'}), 400
        if model2 not in MODEL_CONFIG:
            return jsonify({'error': f'Invalid model2: {model2}'}), 400
        
        # Generate unique ID for this audio pair
        pair_id = str(uuid.uuid4())
        
        # Generate audio from model1
        audio1_data, audio1_error = generate_audio(model1, prompt1, seed1)
        if audio1_error:
            return jsonify({'error': f'Error generating audio1: {audio1_error}'}), 500
        
        # Generate audio from model2
        audio2_data, audio2_error = generate_audio(model2, prompt2, seed2)
        if audio2_error:
            return jsonify({'error': f'Error generating audio2: {audio2_error}'}), 500
        
        # Upload audio files to GCP Storage
        audio1_filename = f"{pair_id}_audio1.mp3"
        audio2_filename = f"{pair_id}_audio2.mp3"
        
        # Use mock or real implementation based on configuration
        if ENABLE_MOCKING:
            audio1_url = mock_gcp_upload(GCP_BUCKET_NAME, audio1_data, audio1_filename)
            audio2_url = mock_gcp_upload(GCP_BUCKET_NAME, audio2_data, audio2_filename)
        else:
            audio1_url = upload_to_gcp_storage(GCP_BUCKET_NAME, audio1_data, audio1_filename)
            audio2_url = upload_to_gcp_storage(GCP_BUCKET_NAME, audio2_data, audio2_filename)
            
        if not audio1_url:
            return jsonify({'error': 'Failed to upload audio1 to GCP Storage'}), 500
        
        if not audio2_url:
            return jsonify({'error': 'Failed to upload audio2 to GCP Storage'}), 500
        
        # Prepare metadata for Firebase
        metadata = {
            'pair_id': pair_id,
            'created_at': datetime.utcnow().isoformat(),
            'model1': model1,
            'model2': model2,
            'prompt1': prompt1,
            'prompt2': prompt2,
            'seed1': seed1,
            'seed2': seed2,
            'audio1_url': audio1_url,
            'audio2_url': audio2_url,
            'votes': {
                'audio1': 0,
                'audio2': 0
            }
        }
        
        # Upload metadata to Firebase (use mock or real implementation)
        if ENABLE_MOCKING:
            success = mock_firebase_upload(FIREBASE_COLLECTION, pair_id, metadata)
        else:
            success = upload_to_firebase(FIREBASE_COLLECTION, pair_id, metadata)
        if not success:
            return jsonify({'error': 'Failed to upload metadata to Firebase'}), 500
        
        # Return success response
        return jsonify({
            'pair_id': pair_id,
            'audio1_url': audio1_url,
            'audio2_url': audio2_url,
            'metadata': metadata
        }), 200
        
    except Exception as e:
        logger.error(f"Error in generate_audio_pair: {e}")
        return jsonify({'error': str(e)}), 500

def generate_audio(model_key: str, prompt: str, seed: Optional[int] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Generate audio using the specified model and prompt.
    
    Args:
        model_key (str): The model key from the configuration
        prompt (str): The text prompt
        seed (Optional[int]): Optional seed for reproducible generation
        
    Returns:
        Tuple[Optional[bytes], Optional[str]]: The audio data and error message (if any)
    """
    try:
        # Use mock implementation for testing if enabled
        if ENABLE_MOCKING:
            audio_data = mock_generate_audio(model_key, prompt, seed)
            return audio_data, None
            
        # Get model configuration
        model_config = MODEL_CONFIG[model_key]['config']
        
        # Create provider instance
        provider = get_music_api_provider(model_key, **model_config)
        
        # Generate music
        response = provider.generate_music(prompt=prompt, seed=seed)
        
        if response.error:
            return None, response.error
        
        return response.audio_data, None
        
    except Exception as e:
        logger.error(f"Error generating audio with {model_key}: {e}")
        return None, str(e)