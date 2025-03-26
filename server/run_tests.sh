#!/bin/bash

# Make the script exit on error
set -e

# Create output directory for test results
mkdir -p test_output

# Function to print section headers
print_header() {
    echo ""
    echo "============================================"
    echo "$1"
    echo "============================================"
    echo ""
}

# Install test dependencies if needed
print_header "Installing test dependencies"
pip install pytest pytest-cov pytest-xdist requests fastapi httpx

# Run unit tests with coverage
print_header "Running unit tests with coverage"
pytest -v tests/unit/ --cov=src --cov-report=term --cov-report=html:test_output/coverage

# Ask if integration tests should be run
print_header "Integration tests"
read -p "Do you want to run integration tests? These may take longer and require external services. (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Ask if real clients should be used
    read -p "Do you want to use real Firebase and GCP clients? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        export USE_MOCK_CLIENTS=false
        print_header "Running integration tests with real clients"
    else
        export USE_MOCK_CLIENTS=true
        print_header "Running integration tests with mock clients"
    fi
    
    pytest -v tests/integration/ -m integration
    
    print_header "Integration test results"
    if [ -d "test_output" ] && [ "$(ls -A test_output)" ]; then
        echo "Generated audio files are available in the test_output directory:"
        ls -la test_output
    else
        echo "No audio files were generated during testing."
    fi
fi

print_header "All tests completed"
echo "Coverage report is available in test_output/coverage/index.html"