# Music Arena - Consolidated Repository

This repository consolidates the previously separate `music-arena` and `audio-arena` repositories into a unified structure.

## Repository Structure

- **`api-gateway/`** - Contains the original `music-arena` codebase (API gateway and backend services)
- **`frontend/`** - Contains the frontend web application (promoted from `api-gateway/frontend/`)
- **`ow-backend/`** - Contains the `audio-arena` codebase as a git submodule (backend processing)

## Migration Notes

- The original `music-arena` repository content has been moved to the `api-gateway/` directory
- The `audio-arena` repository has been added as a git submodule in the `ow-backend/` directory
- This consolidation allows for unified development while maintaining separate histories for each component

## Development

To work with this repository:

1. Clone the repository: `git clone git@github.com:gclef-cmu/music-arena.git`
2. Initialize submodules: `git submodule update --init --recursive`

Each component (`api-gateway` and `ow-backend`) maintains its own dependencies and can be developed independently while being part of the unified repository structure.

## Component Details

### API Gateway (`api-gateway/`)
Contains the main music arena application including:
- Server backend
- API endpoints
- Authentication and secrets management
- Mock data and testing utilities

### Frontend (`frontend/`)
Contains the frontend web application including:
- Gradio-based web interface (`gradio_web_server.py`)
- Conversation logs and user interaction data
- Frontend-specific dependencies and Docker configuration
- Styling and UI components

### OW Backend (`ow-backend/`)
Contains the audio processing backend from the `audio-arena` repository as a git submodule pointing to `git@github.com:gclef-cmu/audio-arena.git`. 