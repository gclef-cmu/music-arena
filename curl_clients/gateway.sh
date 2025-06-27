#!/bin/bash

set -e
set -o pipefail

# Default values
HOSTNAME="localhost"
PORT="8080"
SERVER_URL=""

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
            echo "Usage: $0 [-p port] [-h hostname] [full_server_url]"
            echo "   or: $0 [full_server_url]"
            echo "Examples:"
            echo "  $0                                    # Use default localhost:8080"
            echo "  $0 -p 9090                          # Use localhost:9090"
            echo "  $0 -h myserver.com                  # Use myserver.com:8080"
            echo "  $0 -p 9090 -h myserver.com          # Use myserver.com:9090"
            echo "  $0 http://custom-server:8080         # Use full custom URL"
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

# Determine SERVER_URL based on arguments
if [ $# -eq 1 ]; then
    # Backward compatibility: single argument overrides everything
    SERVER_URL="$1"
    echo "Using provided server URL: $SERVER_URL"
elif [ $# -eq 0 ]; then
    # No URL argument, construct from hostname and port
    SERVER_URL="http://$HOSTNAME:$PORT"
    echo "Using constructed server URL: $SERVER_URL (hostname: $HOSTNAME, port: $PORT)"
else
    echo "Error: Too many arguments"
    echo "Usage: $0 [-p port] [-h hostname] [full_server_url]"
    exit 1
fi

echo "Testing gateway at: $SERVER_URL"
echo

# Function to check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed. Please install jq."
        exit 1
    fi
}

# Function to handle API errors
handle_api_error() {
    local response="$1"
    local endpoint="$2"
    
    if echo "$response" | jq -e '.detail' > /dev/null 2>&1; then
        echo "Error from $endpoint: $(echo "$response" | jq -r '.detail')"
        return 1
    fi
    return 0
}

check_jq

# 1. Call /systems to get available systems
echo "1. Getting available systems..."
SYSTEMS_RESPONSE=$(curl -s -w "%{http_code}" "$SERVER_URL/systems" || { echo "Error: curl command failed for /systems"; exit 1; })
HTTP_CODE="${SYSTEMS_RESPONSE: -3}"
SYSTEMS_BODY="${SYSTEMS_RESPONSE%???}"

if [ "$HTTP_CODE" != "200" ]; then
    echo "Error: Failed to get systems (HTTP $HTTP_CODE)"
    echo "Response: $SYSTEMS_BODY"
    exit 1
fi

if ! handle_api_error "$SYSTEMS_BODY" "/systems"; then
    echo "Error: API error detected in /systems response"
    exit 1
fi

echo "Systems available: $(echo "$SYSTEMS_BODY" | jq 'length')"
echo "System pairs:"
echo "$SYSTEMS_BODY" | jq -r '.[] | "  - System: \(.[0]), Variant: \(.[1])"'
echo

# 2. Call /prebaked to get prebaked prompts
echo "2. Getting prebaked prompts..."
PREBAKED_RESPONSE=$(curl -s -w "%{http_code}" "$SERVER_URL/prebaked" || { echo "Error: curl command failed for /prebaked"; exit 1; })
HTTP_CODE="${PREBAKED_RESPONSE: -3}"
PREBAKED_BODY="${PREBAKED_RESPONSE%???}"

if [ "$HTTP_CODE" != "200" ]; then
    echo "Error: Failed to get prebaked prompts (HTTP $HTTP_CODE)"
    echo "Response: $PREBAKED_BODY"
    exit 1
fi

if ! handle_api_error "$PREBAKED_BODY" "/prebaked"; then
    echo "Error: API error detected in /prebaked response"
    exit 1
fi

echo "Prebaked prompts count: $(echo "$PREBAKED_BODY" | jq 'keys | length')"
echo

# Generate mock UUIDs and timestamps for session and user
SESSION_UUID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
SESSION_CREATE_TIME=$(python3 -c "import time; print(time.time())")
USER_IP_HASH=$(python3 -c "import hashlib; print(hashlib.md5('127.0.0.1test'.encode()).hexdigest())")
USER_FP_HASH=$(python3 -c "import hashlib; print(hashlib.md5('test-fingerprint'.encode()).hexdigest())")

echo "Session UUID: $SESSION_UUID"
echo "Session Create Time: $SESSION_CREATE_TIME"
echo "User IP Hash: $USER_IP_HASH"
echo "User Fingerprint Hash: $USER_FP_HASH"
echo

# 3. Call /generate_battle with a simple prompt
echo "3. Generating battle with simple prompt..."
PROMPT_TEXT="Generate a relaxing ambient soundscape with soft piano"
BATTLE_REQUEST=$(cat << EOF
{
  "session": {
    "uuid": "$SESSION_UUID",
    "create_time": $SESSION_CREATE_TIME,
    "frontend_git_hash": "$(git rev-parse HEAD)",
    "ack_tos": true
  },
  "user": {
    "salted_ip": "$USER_IP_HASH",
    "salted_fingerprint": "$USER_FP_HASH"
  },
  "prompt": {
    "prompt": "$PROMPT_TEXT"
  }
}
EOF
)

BATTLE_RESPONSE=$(curl -s -w "%{http_code}" -X POST "$SERVER_URL/generate_battle" \
    -H "Content-Type: application/json" \
    -d "$BATTLE_REQUEST" || { echo "Error: curl command failed for /generate_battle"; exit 1; })

HTTP_CODE="${BATTLE_RESPONSE: -3}"
BATTLE_BODY="${BATTLE_RESPONSE%???}"

if [ "$HTTP_CODE" != "200" ]; then
    echo "Error: Failed to generate battle (HTTP $HTTP_CODE)"
    echo "Response: $BATTLE_BODY"
    
    # Handle flaky errors by retrying once
    if echo "$BATTLE_BODY" | grep -q "Flaky error"; then
        echo "Retrying due to flaky error..."
        sleep 1
        BATTLE_RESPONSE=$(curl -s -w "%{http_code}" -X POST "$SERVER_URL/generate_battle" \
            -H "Content-Type: application/json" \
            -d "$BATTLE_REQUEST" || { echo "Error: curl retry command failed for /generate_battle"; exit 1; })
        HTTP_CODE="${BATTLE_RESPONSE: -3}"
        BATTLE_BODY="${BATTLE_RESPONSE%???}"
        
        if [ "$HTTP_CODE" != "200" ]; then
            echo "Error: Retry also failed (HTTP $HTTP_CODE)"
            echo "Response: $BATTLE_BODY"
            exit 1
        fi
    else
        exit 1
    fi
fi

if ! handle_api_error "$BATTLE_BODY" "/generate_battle"; then
    echo "Error: API error detected in /generate_battle response"
    exit 1
fi

# Extract battle UUID from response
BATTLE_UUID=$(echo "$BATTLE_BODY" | jq -r '.uuid')
if [ "$BATTLE_UUID" = "null" ] || [ -z "$BATTLE_UUID" ]; then
    echo "Error: Failed to get battle UUID from response"
    echo "Response: $BATTLE_BODY"
    exit 1
fi
echo "Battle UUID: $BATTLE_UUID"

# Save battle data to JSON file
echo "Saving battle data to ${BATTLE_UUID}.json..."
echo "$BATTLE_BODY" | jq '.' > "${BATTLE_UUID}.json"
echo "Battle data saved to ${BATTLE_UUID}.json"

# Extract audio URLs
AUDIO_A_URL=$(echo "$BATTLE_BODY" | jq -r '.a_audio_url')
AUDIO_B_URL=$(echo "$BATTLE_BODY" | jq -r '.b_audio_url')
echo "Audio A URL: $AUDIO_A_URL"
echo "Audio B URL: $AUDIO_B_URL"

# Check if we have system metadata (should be anonymized)
A_SYSTEM=$(echo "$BATTLE_BODY" | jq -r '.a_metadata.system_tag // "anonymized"')
B_SYSTEM=$(echo "$BATTLE_BODY" | jq -r '.b_metadata.system_tag // "anonymized"')
echo "System A: $A_SYSTEM"
echo "System B: $B_SYSTEM"

# Download audio files and verify they're valid
echo "Downloading ${BATTLE_UUID}-a.mp3..."
if ! curl -s "$AUDIO_A_URL" -o "${BATTLE_UUID}-a.mp3"; then
    echo "Error: Failed to download audio A from $AUDIO_A_URL"
    exit 1
fi
AUDIO_A_SIZE=$(stat -f%z "${BATTLE_UUID}-a.mp3" 2>/dev/null || stat -c%s "${BATTLE_UUID}-a.mp3" 2>/dev/null || echo "unknown")
echo "Downloaded audio A (${AUDIO_A_SIZE} bytes)"

echo "Downloading ${BATTLE_UUID}-b.mp3..."
if ! curl -s "$AUDIO_B_URL" -o "${BATTLE_UUID}-b.mp3"; then
    echo "Error: Failed to download audio B from $AUDIO_B_URL"
    exit 1
fi
AUDIO_B_SIZE=$(stat -f%z "${BATTLE_UUID}-b.mp3" 2>/dev/null || stat -c%s "${BATTLE_UUID}-b.mp3" 2>/dev/null || echo "unknown")
echo "Downloaded audio B (${AUDIO_B_SIZE} bytes)"
echo

# 4. Call /record_vote with a random vote
echo "4. Recording vote..."
PREFERENCES=("A" "B" "TIE" "BOTH_BAD")
RANDOM_PREFERENCE=${PREFERENCES[$RANDOM % ${#PREFERENCES[@]}]}
CURRENT_TIME=$(python3 -c "import time; print(time.time())")

# Add some mock listen data
LISTEN_TIME_A=$(python3 -c "import time; print(time.time() - 10)")
LISTEN_TIME_B=$(python3 -c "import time; print(time.time() - 5)")

VOTE_REQUEST=$(cat << EOF
{
  "session": {
    "uuid": "$SESSION_UUID",
    "create_time": $SESSION_CREATE_TIME,
    "frontend_git_hash": "test-git-hash",
    "ack_tos": true
  },
  "user": {
    "salted_ip": "$USER_IP_HASH",
    "salted_fingerprint": "$USER_FP_HASH"
  },
  "battle_uuid": "$BATTLE_UUID",
  "vote": {
    "preference": "$RANDOM_PREFERENCE",
    "preference_time": $CURRENT_TIME,
    "a_listen_data": [["PLAY", $LISTEN_TIME_A], ["PAUSE", $(python3 -c "import time; print(time.time() - 8)")]],
    "b_listen_data": [["PLAY", $LISTEN_TIME_B], ["PAUSE", $(python3 -c "import time; print(time.time() - 3)")]],
    "a_feedback": "Sounds good",
    "b_feedback": "Also nice"
  }
}
EOF
)

VOTE_RESPONSE=$(curl -s -w "%{http_code}" -X POST "$SERVER_URL/record_vote" \
    -H "Content-Type: application/json" \
    -d "$VOTE_REQUEST" || { echo "Error: curl command failed for /record_vote"; exit 1; })

HTTP_CODE="${VOTE_RESPONSE: -3}"
VOTE_BODY="${VOTE_RESPONSE%???}"

if [ "$HTTP_CODE" != "200" ]; then
    echo "Error: Failed to record vote (HTTP $HTTP_CODE)"
    echo "Response: $VOTE_BODY"
    exit 1
fi

if ! handle_api_error "$VOTE_BODY" "/record_vote"; then
    echo "Error: API error detected in /record_vote response"
    exit 1
fi

echo "Vote preference: $RANDOM_PREFERENCE"
echo "Vote response:"
echo "$VOTE_BODY" | jq '.'
echo

echo "✅ All API calls completed successfully!"
echo "Generated files: ${BATTLE_UUID}.json, ${BATTLE_UUID}-a.mp3, ${BATTLE_UUID}-b.mp3" 