import os
import json
import random
import time
import uuid
import base64
import logging
import traceback
from typing import Dict, Any, Optional, List
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import real clients
from src.firebase.firebase_client import FirebaseClient
from src.gcp.gcp_client import GCPClient

# Import mock clients for testing
from src.firebase.mock_firebase_client import MockFirebaseClient
from src.gcp.mock_gcp_client import MockGCPClient

from src.api.models import AudioPairRequest, AudioPairResponse, AudioMetadata, AudioItem, VoteRequest, VoteResponse
from src.api.utils import (
    get_settings,
    generate_unique_id,
    get_timestamp,
    create_audio_metadata,
    create_vote_metadata,
)
from src.api.music_api import get_music_api_provider, MusicResponseOutput

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FastAPIApp:
    def __init__(self):
        self.settings = get_settings()
        self.app = FastAPI(
            title="Music Arena API",
            version=self.settings.get("version_backend", "0.1.0"),
        )

        # Set up CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize clients
        self.firebase_client = FirebaseClient()
        self.gcp_client = GCPClient()
        
        # Load model configurations
        self.model_configs = self._load_model_configs()
        logger.info(f"Loaded {len(self.model_configs)} model configurations")

        # Set up routes
        self.setup_routes()
        logger.info("API is starting up")
        
    def _load_model_configs(self):
        """Load model configurations from the config file."""
        config_path = os.path.join("config", "model_config.json")
        try:
            with open(config_path, "r") as f:
                model_configs = json.load(f)
            return model_configs
        except Exception as e:
            logger.warning(f"Error loading model config: {str(e)}. Using default empty config")
            return {}
            
    def sample_random_models(self, count=2):
        """Sample random models from the loaded configurations.
        
        Args:
            count (int): Number of models to sample
            
        Returns:
            list: List of sampled model keys
        """
        if not self.model_configs or len(self.model_configs) < count:
            # Fallback models if not enough are configured
            logger.warning(f"Not enough models in config, using default models")
            default_models = ["musicgen-small", "audioldm2", "noise"]
            return random.sample(default_models[:count], min(count, len(default_models)))
        
        # Select random models from available models
        model_keys = list(self.model_configs.keys())
        return random.sample(model_keys, count)

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "version": self.settings.get("version_backend", "0.1.0"),
            }
            
        @self.app.post("/record_vote")
        async def record_vote(request: VoteRequest):
            """
            Record a user's vote on an audio pair.
            
            The vote data is stored in Firebase.
            """
            try:
                # Create a unique vote ID
                vote_id = generate_unique_id()
                
                logger.info(f"Recording vote for pair {request.pair_id}, winner: {request.winning_model}")
                
                # Create vote metadata directly from the request
                vote_metadata = create_vote_metadata(
                    vote_id=vote_id,
                    request_data=request.dict(by_alias=True)
                )
                
                # Upload vote to Firebase
                votes_collection = self.settings["firebase_collections"]["audio_outcomes"]
                doc_id = self.firebase_client.upload_data(votes_collection, vote_metadata)
                
                logger.info(f"Recorded vote with ID {vote_id}, document ID: {doc_id}")
                
                # Return success response
                return VoteResponse(
                    voteId=vote_id,
                    timestamp=get_timestamp(),
                    status="success"
                )
                
            except Exception as e:
                error_msg = f"Error recording vote: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/generate_audio_pair")
        async def generate_audio_pair(
            request: AudioPairRequest, background_tasks: BackgroundTasks
        ):
            """
            Generate a pair of audio samples from a text prompt.

            The audio files are stored in Google Cloud Storage, and metadata is stored in Firebase.
            """
            start_time = time.time()

            try:
                # Create a unique pair ID
                pair_id = str(uuid.uuid4())
                
                # Sample two random models
                selected_model_keys = self.sample_random_models(2)
                
                # Get music API providers for both models
                music_api_1 = get_music_api_provider(model_key=selected_model_keys[0])
                music_api_2 = get_music_api_provider(model_key=selected_model_keys[1])
                
                logger.info(
                    f"Using music models: {music_api_1.model_name} and {music_api_2.model_name}"
                )

                # Generate first audio
                audio_id_1 = generate_unique_id()
                generation_start_1 = time.time()
                response_1 = music_api_1.generate_music(
                    prompt=request.prompt, seed=request.seed
                )
                generation_time_1 = time.time() - generation_start_1

                # Generate second audio 
                audio_id_2 = generate_unique_id()
                generation_start_2 = time.time()
                response_2 = music_api_2.generate_music(
                    prompt=request.prompt, seed=request.seed
                )
                generation_time_2 = time.time() - generation_start_2

                # Check for errors
                if response_1.error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error generating first audio: {response_1.error}",
                    )
                if response_2.error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error generating second audio: {response_2.error}",
                    )

                # Upload audio files to GCS
                bucket_name = self.settings["gcs_buckets"]["audio_files"]
                gcs_path_1 = f"audio/{audio_id_1}.mp3"
                gcs_path_2 = f"audio/{audio_id_2}.mp3"

                logger.info(f"Uploading audio files to GCS bucket: {bucket_name}")
                url_1 = self.gcp_client.upload_file(
                    bucket_name, response_1.audio_data, gcs_path_1
                )
                url_2 = self.gcp_client.upload_file(
                    bucket_name, response_2.audio_data, gcs_path_2
                )
                logger.info(
                    f"Audio files uploaded successfully. URLs: {url_1}, {url_2}"
                )

                # Create metadata
                metadata_1 = create_audio_metadata(
                    audio_id=audio_id_1,
                    user_id=request.user_id,
                    prompt=request.prompt,
                    model=music_api_1.model_name,
                    latency=generation_time_1,
                    seed=request.seed,
                    pair_audio_id=audio_id_2,
                    pair_index=0,
                )

                metadata_2 = create_audio_metadata(
                    audio_id=audio_id_2,
                    user_id=request.user_id,
                    prompt=request.prompt,
                    model=music_api_2.model_name,
                    latency=generation_time_2,
                    seed=request.seed,
                    pair_audio_id=audio_id_1,
                    pair_index=1,
                )

                # Add URLs to metadata
                metadata_1["audioUrl"] = url_1
                metadata_2["audioUrl"] = url_2

                # Upload metadata to Firebase synchronously
                collection = self.settings["firebase_collections"]["audio_metadata"]
                logger.info(f"Uploading metadata to Firebase collection: {collection}")
                doc_id_1 = self.firebase_client.upload_data(collection, metadata_1)
                doc_id_2 = self.firebase_client.upload_data(collection, metadata_2)
                logger.info(
                    f"Metadata uploaded successfully. Document IDs: {doc_id_1}, {doc_id_2}"
                )

                # Prepare response with Base64 encoded audio data
                audio_item_1 = AudioItem(
                    **metadata_1,
                    audioDataBase64=base64.b64encode(response_1.audio_data).decode('utf-8')
                )
                
                audio_item_2 = AudioItem(
                    **metadata_2,
                    audioDataBase64=base64.b64encode(response_2.audio_data).decode('utf-8')
                )
                
                response = AudioPairResponse(pairId=pair_id, audioItems=[audio_item_1, audio_item_2])

                total_time = time.time() - start_time
                logger.info(
                    f"Generated audio pair in {total_time:.2f}s. Pair ID: {pair_id}"
                )

                return response

            except Exception as e:
                error_msg = (
                    f"Error generating audio pair: {str(e)}\n{traceback.format_exc()}"
                )
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=str(e))


# Create the FastAPI application
fastapi_app = FastAPIApp()
app = fastapi_app.app
