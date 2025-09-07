# Music Arena Leaderboard & Analysis Toolkit

This repository contains the Python scripts for downloading, analyzing, and generating leaderboards from the Music Arena platform's battle data.

## Features

  * **Data Downloader**: Fetch battle logs directly from a GCS bucket, with options to download only new files or files from a specific date range.
  * **Log Parser**: Process raw, nested JSON logs into a structured format for analysis.
  * **Data Analyzer**: Generate summary statistics, including:
      * Counts of voted, unvoted, and health-check battles.
      * Detailed listening time statistics (average, median, std. dev., etc.).
      * Daily and hourly user activity trends.
  * **Leaderboard Generator**: Calculate Arena Scores using the Bradley-Terry model and generate separate leaderboards for instrumental and vocal models.
  * **Visualizer**: Create and save plots for quality-speed tradeoffs, usage trends, and data distributions.

## Repository Structure

```
leaderboard/
├── main.py                 # Main executable script
├── config.py               # All configurations (GCP info, model metadata, etc.)
├── data_loader.py          # Data loading and parsing functions
├── download_data.py        # Downloading filtered audio and battle data subsets (For Data Release)
├── analysis.py             # Statistical analysis functions
├── scoring.py              # Arena Score and RTF calculation logic
├── leaderboard.py          # Leaderboard table generation
├── visualizer.py           # Plotting and visualization functions
├── battle_logs/            # Directory for downloaded raw battle data via main.py
├── audio_files/            # Directory for downloaded filtered audio files via download_data.py
|── battle_data/            # Directory for downloaded filtered battle data via download_data.py
└── outputs/                # Directory for generated leaderboards and plots
    ├── leaderboards/
    └── plots/
```

## Setup

1.  **Google Cloud Authentication:**
    To download data from GCS, you need to authenticate. Run this command once in your terminal:

    ```bash
    gcloud auth application-default login
    ```

2.  **Configure the Project:**
    Open `config.py` and ensure the `GCP_PROJECT_ID`, `METADATA_BUCKET_NAME`, and `AUDIO_BUCKET_NAME` variables are set correctly.

## Usage

All operations are run via `main.py` using the `--action` argument. You can also specify a date range for most actions.

### 1\. Download Battle Logs

  * **Download only new files (skips existing):**
    ```bash
    python main.py --action download
    ```
  * **Download only new files from a specific date range:**
    ```bash
    python main.py --action download --start_date YYYY-MM-DD --end_date YYYY-MM-DD
    ```

### 2\. Perform Data Analysis

  * **Analyze all local logs and print summary statistics:**
    ```bash
    python main.py --action analyze
    ```
  * **Analyze local logs from a specific date range:**
    ```bash
    python main.py --action analyze --start_date YYYY-MM-DD --end_date YYYY-MM-DD
    ```

### 3\. Generate Leaderboards

  * **Generate leaderboards and plots from all local logs:**
    ```bash
    python main.py --action leaderboard
    ```
  * **Generate leaderboards and plots for a specific date range:**
    ```bash
    python main.py --action leaderboard --start_date YYYY-MM-DD --end_date YYYY-MM-DD
    ```