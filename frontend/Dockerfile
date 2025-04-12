FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . /app/

# Install required packages
RUN pip install --no-cache-dir -r /app/requirements-frontend.txt

# Make port 8080 available
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV LOGDIR=/app/logs

# Ensure log directory exists
RUN mkdir -p /app/logs

# Run the application
CMD ["python", "gradio_web_server.py", "--port", "8080", "--host", "0.0.0.0", "--share"]