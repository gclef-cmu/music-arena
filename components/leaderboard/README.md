# Music Arena Leaderboard

The leaderboard is computed transparently from the public [Music Arena Dataset](https://huggingface.co/datasets/music-arena/music-arena-dataset) on HuggingFace.

## Scoring Methodology

- **Arena Score**: [Bradley-Terry model](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model) via L2-regularized logistic regression. Ties are split as half-win / half-loss for each side. Votes with `BOTH_BAD` preference are excluded.
- **95% CI**: Bootstrap resampling (1,000 iterations)
- **Generation Speed (RTF)**: Median Real-Time Factor (audio duration / generation time), normalized to A6000 GPU for open-weights models.
- **Threshold**: Only models with 30+ votes are shown.

For the full scoring implementation, see [`ma_leaderboard/scoring.py`](ma_leaderboard/scoring.py).

## Setup

```bash
# Install the leaderboard component
pip install -e components/leaderboard/

# For GCP data download (maintainers only):
pip install -e "components/leaderboard/[gcp]"
```

## Reproduce the Leaderboard (Anyone)

No credentials required — uses only public HuggingFace data:

```bash
# Generate leaderboard from public HuggingFace dataset
ma-leaderboard leaderboard --output-dir results

# View the generated files
ls results/leaderboards/   # TSV tables
ls results/plots/           # PNG scatter plots
```

## Monthly Data Pipeline (Maintainers)

The full pipeline can be run with a single command:

```bash
bash components/leaderboard/ma_leaderboard/monthly_update.sh
```

This will download new data, preprocess, push to HuggingFace, generate the leaderboard, and update the frontend.

Alternatively, each step can be run individually:

### Step 1: Download new battle data from GCP

```bash
# 1. Authenticate with GCP (one-time setup, no key files needed)
gcloud auth application-default login

# 2. Set bucket configuration (ask maintainers for values, never commit these)
export MUSIC_ARENA_GCP_PROJECT_ID="<project-id>"
export MUSIC_ARENA_METADATA_BUCKET="<metadata-bucket>"
export MUSIC_ARENA_AUDIO_BUCKET="<audio-bucket>"

# 3. Download new data (dates are auto-detected)
ma-leaderboard download
```

> **Security**: GCP authentication uses `gcloud` CLI login — no key files are stored in the repo. The bucket names are passed via environment variables only. All credential-related patterns (`*credentials*`, `*service_account*`, `.env*`) are in `.gitignore`.

- **Start date**: Auto-detected from existing data. If no data exists, defaults to 2025-07-28 (launch date).
- **End date**: Auto-detected as end of previous month. Override with `--start` / `--end` if needed.
- Only battles with valid models (in `MODELS_METADATA`) are downloaded. Test/unknown models are skipped.
- Already downloaded files are automatically skipped (incremental).

Downloaded files are stored in:
```
components/leaderboard/data/
  logs/       # Raw JSON battle logs
  audio/      # MP3 audio files
```

This directory is git-ignored and will not be committed.

### Step 2: Preprocess into HuggingFace dataset format

```bash
ma-leaderboard preprocess
```

Output is written to `components/leaderboard/data/dataset/`:
```
components/leaderboard/data/dataset/
  battle_data/{month}/    # Simplified JSON per battle
  audio_files/{month}/    # MP3 files (non-public models excluded)
  metadata/{month}.md     # Period summary
```

### Step 3: Push to HuggingFace dataset

```bash
cd <your-local-clone-of-music-arena-dataset>

# Copy the new month's data into the dataset repo
cp -r <music-arena>/components/leaderboard/data/dataset/battle_data/* battle_data/
cp -r <music-arena>/components/leaderboard/data/dataset/audio_files/* audio_files/
cp -r <music-arena>/components/leaderboard/data/dataset/metadata/* metadata/

# Commit and push (audio files tracked via Git LFS)
git add .
git commit -m "Add February 2026 data"
git push
```

### Step 3.5: Sanity check (optional but recommended)

```bash
ma-leaderboard sanity-check
```

Compares local log count vs HuggingFace dataset count to verify the push was complete.

### Step 4: Generate updated leaderboard

```bash
# After HuggingFace processes the new data:
ma-leaderboard leaderboard
```

Results are written to `results/`:
```
results/
  leaderboards/    # TSV tables (instrumental + vocal)
  plots/           # PNG scatter plots
```

### Step 5: Update the website

```bash
ma-leaderboard update-frontend
# Creates components/frontend/ma_frontend/leaderboard/{YYYYMMDD}/
# Commit and open a PR
```

### Optional: Cron job

The monthly update script can be scheduled as a cron job (not enabled by default):

```bash
crontab -e
0 0 1 * * /path/to/music-arena/components/leaderboard/ma_leaderboard/monthly_update.sh >> ~/monthly_update.log 2>&1
```
