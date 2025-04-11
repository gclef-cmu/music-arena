# Music Arena API

A FastAPI server that handles JSON uploads to Firebase and audio file uploads to Google Cloud Storage.

## Front-End
Before diving into the back-end setup, here’s a quick guide on how to launch the front end.

The main front-end component is implemented in `frontend/gradio_web_server.py`.

To make the front end publicly accessible, run the following command:
```
cd frontend
pip install -r requirements-frontend.txt
python -m gradio_web_server --share
```

## Setup

### Using Docker (Recommended)

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/music-arena.git
   cd music-arena
   ```

2. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```

3. Edit the `.env` file with your credentials:
   - Set `FIREBASE_ACCOUNT_KEY` to your base64-encoded Firebase service account key
   - Set `GCP_PROJECT_ID` to your Google Cloud project ID
   - Set `GCS_AUDIO_BUCKET` to your Google Cloud Storage bucket name
   - Set `MUSIC_API_URL` to your music generation API URL

4. Build and start the containers:
   ```
   cd server
   docker-compose up -d
   ```

5. The API will be available at:
   - API: http://localhost:12000
   - Nginx proxy: http://localhost:8080

### Manual Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up Firebase and Google Cloud Storage credentials:
   - Create a `config/firebase_config.json` file with your Firebase service account credentials
   - Or set the `FIREBASE_ACCOUNT_KEY` environment variable with a base64-encoded version of your credentials

3. Configure environment variables in `.env` file:
   ```
   GCP_PROJECT_ID=your-project-id
   GCS_AUDIO_BUCKET=your-bucket-name
   MUSIC_API_URL=http://your-music-api-url
   ```

4. Run the server:
   ```
   python main.py
   ```

The server will start on port 12000 by default. You can change this by setting the `PORT` environment variable.

## API Endpoints

### Health Check
```
GET /health
```

### Generate Audio Pair
```
POST /generate_audio_pair
```
Request body:
```json
{
  "prompt": "Create an upbeat electronic dance track",
  "userId": "user123",
  "seed": 42
}
```

### Upload JSON
```
POST /upload_json
```
Request body:
```json
{
  "userId": "user123",
  "metadata": {
    "key1": "value1",
    "key2": "value2"
  },
  "audioData": "base64_encoded_audio_data"
}
```

### Upload Audio File
```
POST /upload_audio
```
Form data:
- `file`: Audio file
- `user_id`: User ID
- `metadata`: Optional JSON metadata string
