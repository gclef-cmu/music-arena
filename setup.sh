#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ENABLE_MOCKING=true
export GCP_BUCKET_NAME=music-arena-audio

# Run the application
python run.py