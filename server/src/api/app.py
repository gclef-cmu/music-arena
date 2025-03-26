import os
import time
import uuid
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

from src.api.models import AudioPairRequest, AudioPairResponse, AudioMetadata
from src.api.utils import (
    get_settings,
    generate_unique_id,
    get_timestamp,
    create_audio_metadata,
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

        # Set up routes
        self.setup_routes()
        logger.info("API is starting up")

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "version": self.settings.get("version_backend", "0.1.0"),
            }

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

                # Get model key from request or use default
                model_key = (
                    request.model_key
                    if hasattr(request, "model_key") and request.model_key
                    else "musicgen-small"
                )

                # Get music API provider using the model configuration
                music_api = get_music_api_provider(model_key=model_key)

                logger.info(
                    f"Using music model: {music_api.model_name} with base_url: {music_api.config.get('base_url')}"
                )

                # Generate first audio
                audio_id_1 = generate_unique_id()
                generation_start_1 = time.time()
                response_1 = music_api.generate_music(
                    prompt=request.prompt, seed=request.seed
                )
                generation_time_1 = time.time() - generation_start_1

                # Generate second audio with different seed
                audio_id_2 = generate_unique_id()
                seed_2 = (request.seed + 1) if request.seed is not None else None
                generation_start_2 = time.time()
                response_2 = music_api.generate_music(
                    prompt=request.prompt, seed=seed_2
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
                    model=music_api.model_name,
                    latency=generation_time_1,
                    seed=request.seed,
                    pair_audio_id=audio_id_2,
                    pair_index=0,
                )

                metadata_2 = create_audio_metadata(
                    audio_id=audio_id_2,
                    user_id=request.user_id,
                    prompt=request.prompt,
                    model=music_api.model_name,
                    latency=generation_time_2,
                    seed=seed_2,
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

                # Prepare response
                audio_items = [
                    {**metadata_1, "audioData": response_1.audio_data.decode("latin1")},
                    {**metadata_2, "audioData": response_2.audio_data.decode("latin1")},
                ]

                response = AudioPairResponse(pairId=pair_id, audioItems=audio_items)

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
