# Music Arena Server Tests

This directory contains pytest tests for the Music Arena server.

## Test Structure

- `unit/`: Unit tests for individual components
- `integration/`: Integration tests that interact with external services

## Test Categories

Tests are categorized using pytest markers:

- `unit`: Unit tests that don't require external services
- `integration`: Tests that interact with external services
- `api`: Tests for API endpoints
- `music`: Tests for music generation functionality
- `firebase`: Tests for Firebase functionality
- `gcp`: Tests for Google Cloud Platform functionality
- `slow`: Tests that take more than 1 second to run

## Running Tests

### Using the Test Script

The easiest way to run tests is using the provided script:

```bash
cd /workspace/music-arena/server
./run_tests.sh
```

### Running Tests Manually

#### Unit Tests

Run all unit tests:

```bash
cd /workspace/music-arena/server
pytest -m unit
```

Run unit tests with coverage:

```bash
pytest -m unit --cov=src --cov-report=term --cov-report=html:test_output/coverage
```

#### Integration Tests

Run all integration tests:

```bash
cd /workspace/music-arena/server
pytest -m integration
```

#### Running Tests by Category

Run all API tests:

```bash
pytest -m api
```

Run all music generation tests:

```bash
pytest -m music
```

Run all slow tests:

```bash
pytest -m slow
```

#### Running Specific Tests

Run tests for a specific file:

```bash
pytest tests/unit/test_music_api.py
```

Run a specific test:

```bash
pytest tests/unit/test_music_api.py::test_custom_server_music_api_provider_validate_config
```

#### Running Tests in Parallel

For faster execution, you can run tests in parallel:

```bash
pytest -m unit -n auto
```

## Test Configuration

Integration tests require real Firebase and GCP clients. To use real clients, set the environment variable:

```bash
export USE_MOCK_CLIENTS=false
```

## Test Output

- Coverage reports are saved to `test_output/coverage/`
- Integration tests that generate audio will save the files to the `test_output/` directory for manual inspection

## Adding New Tests

When adding new tests:

1. Use appropriate pytest markers to categorize your tests
2. Follow the naming convention: `test_*.py` for test files and `test_*` for test functions
3. Use fixtures from the conftest.py files when possible
4. Add docstrings to explain what each test is checking