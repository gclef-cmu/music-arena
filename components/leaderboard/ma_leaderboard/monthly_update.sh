#!/bin/bash
# Monthly Music Arena update script
# Usage: bash monthly_update.sh
# Optional cron: 0 0 1 * * /path/to/monthly_update.sh >> ~/monthly_update.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MUSIC_ARENA_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=========================================="
echo "Music Arena Monthly Update: $(date)"
echo "=========================================="

cd "$MUSIC_ARENA_ROOT"

# Activate conda environment
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate MusicArena

# Step 1: Download new data from GCP
echo -e "\n[Step 1/6] Downloading new data from GCP..."
ma-leaderboard download

# Step 2: Preprocess
echo -e "\n[Step 2/6] Preprocessing into HuggingFace format..."
ma-leaderboard preprocess

# Step 3: Push to HuggingFace dataset
echo -e "\n[Step 3/6] Pushing to HuggingFace..."
DATASET_DIR="$MUSIC_ARENA_ROOT/components/leaderboard/data/dataset"
HF_REPO_DIR="$HOME/music-arena-dataset"

if [ -d "$HF_REPO_DIR" ]; then
    cd "$HF_REPO_DIR"
    git pull
    cp -r "$DATASET_DIR/battle_data/"* battle_data/ 2>/dev/null || true
    cp -r "$DATASET_DIR/audio_files/"* audio_files/ 2>/dev/null || true
    cp -r "$DATASET_DIR/metadata/"* metadata/ 2>/dev/null || true
    # Auto-update README.md configs from battle_data
    python -m ma_leaderboard.update_hf_readme "$HF_REPO_DIR"
    git add .
    if git diff --staged --quiet; then
        echo "No new data to push."
    else
        # Determine data period from latest battle_data folder name (e.g., 07-2026FEB -> Feb 2026)
        LATEST_FOLDER=$(ls -1 battle_data/ | sort | tail -1)
        DATA_PERIOD=$(echo "$LATEST_FOLDER" | sed 's/^[0-9]*-//' | sed 's/\([0-9]\{4\}\)\(.*\)/\2 \1/')
        git commit -m "Add ${DATA_PERIOD:-new} data"

        # Only ask for auth when we actually need to push
        if ! git push 2>/dev/null; then
            echo "HuggingFace authentication required."
            read -p "Enter your HF username: " HF_USER
            read -s -p "Enter your HF token: " HF_TOKEN
            echo ""
            REMOTE_URL=$(git remote get-url origin)
            REPO_PATH=$(echo "$REMOTE_URL" | sed 's|https://huggingface.co/||')
            git remote set-url origin "https://${HF_USER}:${HF_TOKEN}@huggingface.co/${REPO_PATH}"
            git push
            git remote set-url origin "https://huggingface.co/${REPO_PATH}"
        fi
        echo "Pushed to HuggingFace."
    fi

    cd "$MUSIC_ARENA_ROOT"
else
    echo "WARNING: HF dataset repo not found at $HF_REPO_DIR. Skipping push."
fi

# Step 4: Sanity check
echo -e "\n[Step 4/6] Sanity check..."
ma-leaderboard sanity-check

# Step 5: Generate leaderboard (clean results first to avoid stale files)
echo -e "\n[Step 5/6] Generating leaderboard..."
rm -rf results
ma-leaderboard leaderboard

# Step 6: Update frontend
echo -e "\n[Step 6/6] Updating frontend..."
ma-leaderboard update-frontend

echo -e "\n=========================================="
echo "Done! $(date)"
echo ""
echo "Remaining manual steps:"
echo "  cd $MUSIC_ARENA_ROOT"
echo "  git add components/frontend/ma_frontend/leaderboard/"
echo "  git commit -m 'Update leaderboard (data through $(ls components/frontend/ma_frontend/leaderboard/ | sort | tail -1))'"
echo "  git push"
echo "=========================================="
