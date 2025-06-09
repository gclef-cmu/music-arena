# Use an official Python runtime as a parent image
FROM python:3.12-slim-bullseye
COPY --from=ghcr.io/astral-sh/uv:0.3.0 /uv /bin/uv

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN uv pip install --system -r requirements.txt

# Make port 12000 available to the world outside this container
EXPOSE 12000

# Define environment variables
ENV USE_MOCK_CLIENTS=false
ENV PORT=12000
ENV GCP_PROJECT_ID=music-arena
ENV GCS_AUDIO_BUCKET=music-arena-audio

# Run the application when the container launches
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "12000", "--workers", "2"]