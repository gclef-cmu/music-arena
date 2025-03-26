# Music Arena Server

This directory contains the server-side code for the Music Arena application.

## Setup

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gclef-cmu/music-arena.git
   cd music-arena/server
   ```

2. Install dependencies:
   ```bash
   # For production
   pip install -r requirements.txt
   
   # For development
   pip install -r requirements-dev.txt
   
   # For testing only
   pip install -r requirements-test.txt
   ```

### Configuration

1. Create a `config/firebase_config.json` file with your Firebase credentials.
2. Update `config/settings.json` with your specific settings.
3. The `config/model_config.json` file contains configuration for the music generation models.

## Running the Server

```bash
python main.py
```

The server will start on port 12000 by default. You can change this by setting the `PORT` environment variable.

## API Endpoints

- `GET /health`: Health check endpoint
- `POST /generate_audio_pair`: Generate a pair of audio samples from a text prompt
- `POST /upload_json`: Upload a JSON document to Firebase
- `POST /upload_audio`: Upload an audio file to Google Cloud Storage

## Testing

Run the tests using the provided script:

```bash
./run_tests.sh
```

For more information about testing, see the [tests/README.md](tests/README.md) file.

## Directory Structure

- `config/`: Configuration files
- `src/`: Source code
  - `api/`: API endpoints and utilities
  - `firebase/`: Firebase client
  - `gcp/`: Google Cloud Platform client
- `tests/`: Tests
  - `unit/`: Unit tests
  - `integration/`: Integration tests

## Requirements Files

- `requirements.txt`: Core dependencies for production
- `requirements-dev.txt`: Additional dependencies for development
- `requirements-test.txt`: Dependencies for running tests