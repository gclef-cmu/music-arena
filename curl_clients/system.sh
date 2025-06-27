#!/bin/bash

# curl_client.sh - A curl client for music-arena sys-serve.py
# Usage: ./curl_client.sh [-p port] [-h hostname] <system_key> <json_file_path>
#    or: ./curl_client.sh -p <port> [-h hostname] <json_file_path>
# Where system_key is in format: system_tag:variant_tag

set -e

# Default values
HOSTNAME="localhost"
PORT=""
SYSTEM_KEY=""
JSON_FILE=""

# Parse command line options
while getopts "p:h:" opt; do
    case $opt in
        p)
            PORT="$OPTARG"
            ;;
        h)
            HOSTNAME="$OPTARG"
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            echo "Usage: $0 [-p port] [-h hostname] <system_key> <json_file_path>"
            echo "   or: $0 -p <port> [-h hostname] <json_file_path>"
            echo "Where system_key is in format: system_tag:variant_tag"
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            exit 1
            ;;
    esac
done

# Shift past the options
shift $((OPTIND-1))

# Check arguments based on whether port was specified
if [ -n "$PORT" ]; then
    # Port specified, only need JSON file
    if [ $# -ne 1 ]; then
        echo "Usage when port is specified: $0 -p <port> [-h hostname] <json_file_path>"
        echo "Example: $0 -p 8080 -h myserver.com prompt.json"
        exit 1
    fi
    JSON_FILE="$1"
    echo "Using specified port $PORT and hostname $HOSTNAME"
else
    # Port not specified, need system_key and json_file
    if [ $# -ne 2 ]; then
        echo "Usage when port is not specified: $0 [-h hostname] <system_key> <json_file_path>"
        echo "Where system_key is in format: system_tag:variant_tag"
        echo "Example: $0 -h myserver.com musicgen:small prompt.json"
        exit 1
    fi
    SYSTEM_KEY="$1"
    JSON_FILE="$2"
    
    # Calculate port using the Python command with SystemKey.from_string
    PORT=$(python3 -c "from music_arena.docker import system_port; from music_arena.dataclass.system_metadata import SystemKey; print(system_port(SystemKey.from_string('$SYSTEM_KEY')))")
    
    if [ -z "$PORT" ]; then
        echo "Error: Failed to calculate port for system key '$SYSTEM_KEY'"
        exit 1
    fi
    
    echo "Connecting to system key '$SYSTEM_KEY' on port $PORT (hostname: $HOSTNAME)"
fi

# Check if JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON file '$JSON_FILE' not found"
    exit 1
fi

# Validate JSON file
if ! python3 -m json.tool "$JSON_FILE" > /dev/null 2>&1; then
    echo "Error: '$JSON_FILE' is not valid JSON"
    exit 1
fi

# Health check first
echo "Checking server health..."
HEALTH_URL="http://$HOSTNAME:$PORT/health"
if ! curl -s -f "$HEALTH_URL" > /dev/null; then
    echo "Error: Server health check failed. Is the server running on $HOSTNAME:$PORT?"
    if [ -n "$SYSTEM_KEY" ]; then
        echo "You can start the server with:"
        echo "  python -m music_arena.cli.system $SYSTEM_KEY serve"
    fi
    exit 1
fi

echo "Server is healthy"

# Send the generate request
echo "Sending generate request..."
GENERATE_URL="http://$HOSTNAME:$PORT/generate"

# Read JSON content and send POST request
JSON_CONTENT=$(cat "$JSON_FILE")

# Send curl request with proper headers and capture response
echo "Generating audio..."
RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$JSON_CONTENT" \
    "$GENERATE_URL")

# Check if request was successful
if [ $? -ne 0 ]; then
    echo "Error: Request failed"
    exit 1
fi

# Extract audio_b64 from JSON response and decode to MP3 file
if [ -n "$SYSTEM_KEY" ]; then
    OUTPUT_FILE="${SYSTEM_KEY//:/_}_output.mp3"
else
    OUTPUT_FILE="output_port_${PORT}.mp3"
fi
echo "Extracting audio data and saving to $OUTPUT_FILE..."

# Use jq to extract audio_b64 and base64 to decode
AUDIO_B64=$(echo "$RESPONSE" | jq -r '.audio_b64')

if [ "$AUDIO_B64" = "null" ] || [ -z "$AUDIO_B64" ]; then
    echo "Error: No audio_b64 field found in response"
    echo "Response: $RESPONSE"
    exit 1
fi

# Decode base64 audio data to WAV file
echo "$AUDIO_B64" | base64 -d > "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo "Audio saved successfully to $OUTPUT_FILE"
else
    echo "Error: Failed to decode audio data"
    exit 1
fi

# Extract and print lyrics if present
LYRICS=$(echo "$RESPONSE" | jq -r '.lyrics')
if [ "$LYRICS" != "null" ] && [ -n "$LYRICS" ]; then
    echo ""
    echo "Lyrics:"
    echo "$LYRICS"
fi

echo "Request completed" 
