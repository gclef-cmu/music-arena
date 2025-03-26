# Music Arena Server Tests

This directory contains tests for the Music Arena server.

## Test Structure

- `unit/`: Unit tests for individual components
- `integration/`: Integration tests that interact with external services

## Running Tests

### Unit Tests

Run all unit tests:

```bash
cd /workspace/music-arena/server
python -m pytest
```

### Integration Tests

Run all integration tests:

```bash
cd /workspace/music-arena/server
python -m pytest -m integration
```

### Running Specific Tests

Run tests for a specific file:

```bash
python -m pytest tests/unit/test_music_api.py
```

Run a specific test:

```bash
python -m pytest tests/unit/test_music_api.py::test_custom_server_music_api_provider_validate_config
```

## Test Configuration

Integration tests require real Firebase and GCP clients. To use real clients, set the environment variable:

```bash
export USE_MOCK_CLIENTS=false
```

## Test Output

Integration tests that generate audio will save the files to the `test_output/` directory for manual inspection.