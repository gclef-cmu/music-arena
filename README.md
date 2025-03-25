# Music Arena

A web application for generating and comparing music from different AI models.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up Firebase credentials:
   - Create a Firebase project
   - Generate a service account key
   - Save the key as `firebase-credentials.json` in the project root

3. Set up Google Cloud Storage:
   - Create a GCS bucket
   - Set the `GCP_BUCKET_NAME` environment variable to your bucket name
   - Ensure your service account has access to the bucket

## Running the Application

```
python run.py
```

The application will be available at http://localhost:12000

## API Endpoints

### Generate Audio Pair

`POST /api/generate_audio_pair`

Generate a pair of audio files using two different models.

Request body:
```json
{
    "model1": "noise",
    "model2": "musicgen-small",
    "prompt1": "Create a noisy background",
    "prompt2": "Create an upbeat electronic dance track",
    "seed1": 42,
    "seed2": 123
}
```

Response:
```json
{
    "pair_id": "uuid",
    "audio1_url": "https://storage.googleapis.com/...",
    "audio2_url": "https://storage.googleapis.com/...",
    "metadata": {
        "pair_id": "uuid",
        "created_at": "2023-04-01T12:00:00Z",
        "model1": "noise",
        "model2": "musicgen-small",
        "prompt1": "Create a noisy background",
        "prompt2": "Create an upbeat electronic dance track",
        "seed1": 42,
        "seed2": 123,
        "audio1_url": "https://storage.googleapis.com/...",
        "audio2_url": "https://storage.googleapis.com/...",
        "votes": {
            "audio1": 0,
            "audio2": 0
        }
    }
}