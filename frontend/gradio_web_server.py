"""
The gradio demo server for chatting with a single model.
```
cd frontend
python -m frontend.gradio_web_server --share
```
"""

import argparse
from collections import defaultdict
import datetime
import hashlib
import io
import json
import os
import random
import time
import uuid
import pandas as pd
from typing import List, Dict

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import gradio as gr
import requests

import re

import base64
from io import BytesIO

from functools import partial

# Import constants
from constants import (
    LOGDIR,
    WORKER_API_TIMEOUT,
    ErrorCode,
    MODERATION_MSG,
    CONVERSATION_LIMIT_MSG,
    RATE_LIMIT_MSG,
    SERVER_ERROR_MSG,
    INPUT_CHAR_LEN_LIMIT,
    CONVERSATION_TURN_LIMIT,
    SESSION_EXPIRATION_TIME,
    SURVEY_LINK,
    BACKEND_URL,
    KEY_TO_DISPLAY_NAME,
    DISPLAY_NAME_TO_KEY
)
print(f"Using BACKEND_URL={BACKEND_URL}")

class ArenaType:
    TXT2MUSIC = "txt2music-arena"

# # MUSICARENA (Previous version; TODO)
# from api_provider import get_music_api_provider

from remote_logger import (
    get_remote_logger,
    get_repochat_remote_logger,
)
from utils import (
    build_logger,
    get_window_url_params_js,
    get_window_url_params_with_tos_js,
    moderation_filter,
    parse_gradio_auth_creds,
    save_music_files,
    get_music_directory_name_and_remote_storage_flag,
)

def enable_vote_buttons_if_ready(a_listen_time, b_listen_time, vote_cast):
    if vote_cast:
        return [gr.update(interactive=False)] * 4
    if a_listen_time >= 5.0 and b_listen_time >= 5.0:
        return [gr.update(interactive=True)] * 4
    return [gr.update(interactive=False)] * 4

def update_vote_status(a_listen_time, b_listen_time, vote_cast):
    if vote_cast: # 이미 투표했다면
        return "🫶 Thank you for voting!"
    else:
        if a_listen_time >= 5.0 and b_listen_time >= 5.0:
            return "✅ You can now vote!"
        else:
            return "⚠️ You must listen to at least 5 seconds of each audio before voting is enabled."

def on_play_a(a_start_time):
    return time.time()

def on_play_b(b_start_time):
    return time.time()

def on_pause_a(a_start_time, a_listen_time, b_listen_time, current_vote_cast):
    if a_start_time:
        a_listen_time += time.time() - a_start_time
        a_start_time = None
    buttons = enable_vote_buttons_if_ready(a_listen_time, b_listen_time, current_vote_cast)
    message = update_vote_status(a_listen_time, b_listen_time, current_vote_cast)
    return a_start_time, a_listen_time, buttons[0], buttons[1], buttons[2], buttons[3], message

def on_pause_b(b_start_time, a_listen_time, b_listen_time, current_vote_cast):
    if b_start_time:
        b_listen_time += time.time() - b_start_time
        b_start_time = None
    buttons = enable_vote_buttons_if_ready(a_listen_time, b_listen_time, current_vote_cast)
    message = update_vote_status(a_listen_time, b_listen_time, current_vote_cast)
    return b_start_time, b_listen_time, buttons[0], buttons[1], buttons[2], buttons[3], message

def load_random_mock_pair(json_path="surprise_me/mock_pairs.json"):
    with open(json_path, "r") as f:
        mock_data = json.load(f)

    selected = random.choice(mock_data)
    prompt = selected["prompt"]
    basename = selected["basename"]

    models = ["musicgen-small", "musicgen-large", "sao", "songgen", "acestep"]
    
    model_a, model_b = random.sample(models, 2)

    audio_dir = "surprise_me/audio"
    audio_1_path = os.path.join(audio_dir, f"{basename}_{model_a}.mp3")
    audio_2_path = os.path.join(audio_dir, f"{basename}_{model_b}.mp3")

    pair_id = f"mock_{uuid.uuid4().hex[:8]}"

    return (
        pair_id,
        audio_1_path,
        audio_2_path,
        f"**Model A: {model_a}**",
        f"**Model B: {model_b}**",
        audio_1_path,
        audio_2_path,
        pair_id,
        model_a,
        model_b,
        prompt
    )


logger = build_logger("gradio_web_server", "gradio_web_server.log")

headers = {"User-Agent": "Music Arena Client"}

no_change_btn = gr.Button()
enable_btn = gr.Button(interactive=True, visible=True)
disable_btn = gr.Button(interactive=False)
invisible_btn = gr.Button(interactive=False, visible=False)

enable_moderation = False
use_remote_storage = False

# --- START: LEADERBOARD RELATED FUNCTIONS ---
LEADERBOARD_DATA_URL = f"{BACKEND_URL}/get_leaderboard_data"
# Path to your model descriptions JSON file
MODEL_DESCRIPTIONS_PATH = "model/model_descriptions.json"

def load_model_descriptions(path):
    """Loads model descriptions from a JSON file."""
    try:
        # Ensure the path is correct, especially if running from a different directory
        base_dir = os.path.dirname(os.path.abspath(__file__)) # Gets the directory of the current script
        full_path = os.path.join(base_dir, path)
        
        # If the above doesn't work (e.g. __file__ is not defined in interactive environments),
        # you might need a more robust way to set the base path or use an absolute path.
        # For simplicity, if __file__ is not defined, try relative path directly.
        if not os.path.exists(full_path) and not os.path.isabs(path):
             # Try relative path if the script dir approach failed or __file__ not defined
            full_path = path # Fallback to using the path as is (e.g. if it's already absolute or correctly relative)


        if not os.path.exists(full_path):
            print(f"Warning: Model descriptions file not found at {full_path}. Using empty metadata.")
            return {}
            
        with open(full_path, 'r', encoding='utf-8') as f:
            descriptions = json.load(f)
        return descriptions
    except FileNotFoundError:
        print(f"Error: The file {MODEL_DESCRIPTIONS_PATH} was not found. Full path attempted: {full_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {MODEL_DESCRIPTIONS_PATH}. Check for syntax errors.")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while loading {MODEL_DESCRIPTIONS_PATH}: {e}")
        return {}

# Load model descriptions once when the script/module is loaded
music_ai_models_metadata = load_model_descriptions(MODEL_DESCRIPTIONS_PATH)

def get_model_meta(model_key, field, default="N/A"):
    """Helper to safely get metadata for a model."""
    return music_ai_models_metadata.get(model_key, {}).get(field, default)

def infer_organization_license(model_key, description):
    """Infers organization and license based on description or model key."""
    # Basic inference, can be expanded
    organization = "N/A"
    license_type = "N/A"

    if "Meta" in description:
        organization = "Meta"
        license_type = "Research/Proprietary" # Meta's licenses vary
    elif "Stability AI" in description:
        organization = "Stability AI"
        license_type = "Open Source (Non-Commercial)"
    elif "SongGen" in model_key or "songgen.ai" in get_model_meta(model_key, "link", ""):
        organization = "SongGen AI"
        license_type = "Proprietary"
    elif "ACE-Step" in model_key or "ace-step.github.io" in get_model_meta(model_key, "link", ""):
        organization = "ACE-Step Team"
        license_type = "Open Source"
    
    # Fallback for models from JSON that don't match above
    if model_key in music_ai_models_metadata:
        # You could add 'organization' and 'license' fields directly to your JSON
        # For now, we use the inferred ones or defaults.
        if organization == "N/A" and "organization" in music_ai_models_metadata[model_key]:
             organization = music_ai_models_metadata[model_key]["organization"]
        if license_type == "N/A" and "license" in music_ai_models_metadata[model_key]:
             license_type = music_ai_models_metadata[model_key]["license"]


    return organization, license_type


def fetch_and_format_leaderboard_data_global():
    """
    Fetches and formats leaderboard data, using Music AI model metadata loaded from JSON.
    Returns a dictionary containing the DataFrame for the table and summary stats.
    """
    display_headers = [
        "Rank (UB)", "Rank (StyleCtrl)", "Model", "Arena Score",
        "95% CI", "Votes", "Organization", "License",
    ]
    summary_stats = {
        "total_models": "N/A", "total_votes_str": "N/A", "last_updated": "N/A",
    }

    try:
        # ... (real data fetching logic would go here) ...

        # Mock data generation using loaded metadata
        logger.warning("Using MOCK leaderboard data with JSON metadata. Implement backend endpoint for real data.")
        
        music_leaderboard_entries = []
        # Define some base scores and vote counts for mock data generation
        base_scores = {
            "musicgen-large": 1520, "sao": 1485, "musicgen-small": 1450,
            "acestep": 1410, "songgen": 1375
        }
        base_votes = {
            "musicgen-large": 6200, "sao": 5500, "musicgen-small": 4800,
            "acestep": 3900, "songgen": 3200
        }
        # Sort models by a predefined score for ranking, or use keys from JSON
        sorted_model_keys = sorted(base_scores.keys(), key=lambda k: base_scores[k], reverse=True)

        for rank, model_key in enumerate(sorted_model_keys):
            if model_key not in music_ai_models_metadata:
                print(f"Warning: Metadata for model key '{model_key}' not found in loaded JSON data. Skipping.")
                continue

            meta = music_ai_models_metadata[model_key]
            description = meta.get("description", "No description available.")
            org, lic = infer_organization_license(model_key, description)
            
            elo = base_scores.get(model_key, 1200)
            votes = base_votes.get(model_key, 100)
            ci_delta_lower = votes % 15 + 5 # Just some pseudo-random CI
            ci_delta_upper = votes % 18 + 5 # Just some pseudo-random CI

            music_leaderboard_entries.append({
                "rank_ub": rank + 1,
                "rank_stylectrl": rank + 1, # Assuming same rank for mock
                "model_name": meta.get("model_display_name", KEY_TO_DISPLAY_NAME.get(model_key, model_key.replace('-', ' ').title())),
                "link": meta.get("link", ""),
                "elo_rating": elo,
                "elo_rating_q025": elo - ci_delta_lower,
                "elo_rating_q975": elo + ci_delta_upper,
                "num_battles": votes,
                "organization": org,
                "license": lic
            })
        
        mock_backend_response = {
            "leaderboard": music_leaderboard_entries,
            "summary": {
                "total_models": len(music_leaderboard_entries) if music_leaderboard_entries else "N/A",
                "total_votes_str": f"{sum(entry['num_battles'] for entry in music_leaderboard_entries):,}" if music_leaderboard_entries else "N/A",
                "last_updated": "2025-05-22", # Example date
            }
        }
        data_from_backend = mock_backend_response.get("leaderboard", [])
        summary_stats.update(mock_backend_response.get("summary", {}))

        if not data_from_backend:
            return pd.DataFrame(columns=display_headers), summary_stats

        df = pd.DataFrame(data_from_backend)
        
        # Column processing (same as before)
        df["rank_ub"] = df.get("rank_ub", pd.Series(0, index=df.index, dtype=int))
        df["rank_stylectrl"] = df.get("rank_stylectrl", pd.Series("N/A", index=df.index, dtype=str))
        df["model_name"] = df.get("model_name", pd.Series("N/A", index=df.index, dtype=str))
        df["link"] = df.get("link", pd.Series(None, index=df.index, dtype=object))
        df["elo_rating"] = df.get("elo_rating", pd.Series(0.0, index=df.index, dtype=float))
        df["elo_rating_q025"] = df.get("elo_rating_q025", df["elo_rating"])
        df["elo_rating_q975"] = df.get("elo_rating_q975", df["elo_rating"])
        df["num_battles"] = df.get("num_battles", pd.Series(0, index=df.index, dtype=int))
        df["organization"] = df.get("organization", pd.Series("N/A", index=df.index, dtype=str))
        df["license"] = df.get("license", pd.Series("N/A", index=df.index, dtype=str))

        df_display = pd.DataFrame()
        df_display["Rank (UB)"] = df["rank_ub"]
        df_display["Rank (StyleCtrl)"] = df["rank_stylectrl"]
        df_display["Model"] = df.apply(
            lambda row: f"[{row['model_name']}]({row['link']})" if pd.notna(row['link']) and row['link'] else row['model_name'],
            axis=1
        )
        df_display["Arena Score"] = df["elo_rating"].round(0).astype(int)
        df_display["95% CI"] = df.apply(
            lambda row: f"+{max(0, round(row['elo_rating_q975'] - row['elo_rating'])):.0f}/-{max(0, round(row['elo_rating'] - row['elo_rating_q025'])):.0f}"
            if pd.notna(row['elo_rating_q025']) and pd.notna(row['elo_rating_q975']) and pd.notna(row['elo_rating'])
            else "N/A",
            axis=1
        )
        df_display["Votes"] = df["num_battles"]
        df_display["Organization"] = df["organization"]
        df_display["License"] = df["license"]
        df_display = df_display[display_headers]

        return df_display, summary_stats

    except Exception as e: # Broader exception for mock data generation issues as well
        # logger.error(f"Error in fetch_and_format_leaderboard_data_global: {e}", exc_info=True)
        print(f"Error in fetch_and_format_leaderboard_data_global: {e}") # Print error for visibility
        error_row = ["Error processing data"] + ["-"] * (len(display_headers) - 1)
        return pd.DataFrame([error_row], columns=display_headers), summary_stats


def build_leaderboard_ui():
    with gr.Column():
        gr.Markdown("## 📊 Model Leaderboard")
        
    with gr.Column():
        summary_md = gr.Markdown()
        with gr.Row():
            # Using category options from your previous image for consistency
            category_dropdown = gr.Dropdown(label="Category", choices=["Overall", "User Prompts Only", "Pre-generated Prompts (Surprise Me) Only"], value="Overall", interactive=True)
            with gr.Column(scale=1):
                style_control_checkbox = gr.Checkbox(label="Style Control", info="Apply style control adjustments", interactive=True)
                deprecated_checkbox = gr.Checkbox(label="Show Deprecated", interactive=True)

        leaderboard_display_headers = ["Rank (UB)", "Rank (StyleCtrl)", "Model", "Arena Score", "95% CI", "Votes", "Organization", "License"]
        datatypes = ["number", "str", "markdown", "number", "str", "number", "str", "str"]
        leaderboard_df_display = gr.DataFrame(
            headers=leaderboard_display_headers, datatype=datatypes, interactive=False,
            row_count=(15, "dynamic"), col_count=(len(leaderboard_display_headers), "fixed"), wrap=True,
        )
        refresh_button = gr.Button("🔄 Refresh Leaderboard")
        with gr.Accordion("View Column Explanations", open=False):
            gr.Markdown( # ... (explanations markdown, same as before) ...
                """
                - **Rank (UB):** Model's ranking (upper-bound). Defined as 1 + (number of models statistically better than this one). Model A is statistically better than model B if A's lower-bound score (from 95% CI) is greater than B's upper-bound score (from 95% CI).
                - **Rank (StyleCtrl):** Model's ranking when style control is applied. This adjusts for factors like response length and use of markdown to try and decouple raw model capability from these stylistic choices. *(This may not be available for all categories or models).*
                - **Model:** The name of the generative Music AI model. Clickable if a link to more information is available.
                - **Arena Score:** The Elo rating of the model based on head-to-head battles. Higher scores indicate better performance.
                - **95% CI:** The 95% confidence interval for the Arena Score, shown as `+Upper Error / -Lower Error` relative to the score. This indicates the range within which the true score likely lies.
                - **Votes:** The total number of votes (or battles) this model has participated in to calculate its current score.
                - **Organization:** The primary organization or research group behind the model.
                - **License:** The usage license associated with the model.
                """
            )
        
        # This combined function will handle updates from button, dropdown, checkboxes
        def handle_leaderboard_update(category_val, style_control_val, show_deprecated_val):
            # logger.info(f"Updating leaderboard. Category: {category_val}, StyleControl: {style_control_val}, Deprecated: {show_deprecated_val}")
            # NOTE: The fetch_and_format_leaderboard_data_global function currently doesn't use
            # style_control_val or show_deprecated_val. You'd need to pass these to the backend
            # or modify the function to filter/process based on them if handled client-side (less likely for complex logic).
            
            # For now, only category is used in fetch_and_format_leaderboard_data_global mock.
            # df_data, summary_data = fetch_and_format_leaderboard_data_global(category=category_val) # If you adapt fetch function
            df_data, summary_data = fetch_and_format_leaderboard_data_global() # Current mock doesn't filter by category yet.

            total_models_val = summary_data.get('total_models', 'N/A')
            total_votes_val = summary_data.get('total_votes_str', 'N/A')
            last_updated_val = summary_data.get('last_updated', 'N/A')
            summary_text = (
                f"Category: **{category_val}** (Style Control: {style_control_val}, Show Deprecated: {show_deprecated_val})\n\n" # Reflecting filter states
                f"Total #models: **{total_models_val}**. Total #votes: **{total_votes_val}**. Last updated: **{last_updated_val}**.\n\n"
                "Code to recreate leaderboard tables and plots in [our analysis notebook](YOUR_MUSIC_ARENA_NOTEBOOK_LINK). " 
            )
            return summary_text, df_data

        # Inputs for the handler function
        update_inputs = [category_dropdown, style_control_checkbox, deprecated_checkbox]
        
        refresh_button.click(handle_leaderboard_update, inputs=update_inputs, outputs=[summary_md, leaderboard_df_display])
        category_dropdown.change(handle_leaderboard_update, inputs=update_inputs, outputs=[summary_md, leaderboard_df_display])
        style_control_checkbox.change(handle_leaderboard_update, inputs=update_inputs, outputs=[summary_md, leaderboard_df_display])
        deprecated_checkbox.change(handle_leaderboard_update, inputs=update_inputs, outputs=[summary_md, leaderboard_df_display])
        
    # Return components that might be needed by a .load() event if this is part of a larger Blocks app
    # and also the input components if they need to be referenced for initial load.
    return summary_md, leaderboard_df_display, category_dropdown, style_control_checkbox, deprecated_checkbox

# --- END: LEADERBOARD RELATED FUNCTIONS ---


about_md = """
## About Us
Welcome to the Music Arena Leaderboard! This platform ranks Text-to-Music AI models 
based on crowdsourced human preferences. Models are evaluated in head-to-head battles, 
and their Elo ratings are updated dynamically. Explore the top models, their performance 
metrics, and learn more about their capabilities.
Powered by insights from CMU [Generative Creativity Lab (G-CLef)](https://chrisdonahue.com/#group), 
Georgia Tech [Music Informatics Group](https://musicinformatics.gatech.edu/), 
and [LM Arena](https://blog.lmarena.ai/about/).
"""
open_source_md = """
## Open-source contributors
Leads: [Wayne Chi](https://www.waynechi.com/), [Chris Donahue](https://chrisdonahue.com/), [Yonghyun Kim](https://yonghyunk1m.com)
"""

terms_of_service_md = """
## Terms of Service

Users are required to agree to the following terms before using the Music AI Arena service:

1.  **Research Preview:** This service is a research preview intended for evaluating and comparing AI music generation models. It is provided "as is" without warranties of any kind.
2.  **Prohibited Uses:** The service must not be used for any illegal, harmful, defamatory, or infringing purposes. Do not use prompts intended to generate such content.
3.  **Privacy:** Please do not submit any private or sensitive personal information in your text prompts.
4.  **Data Collection and Use:** The service collects data including your text prompts, your preferences (votes) regarding generated audio, and anonymized interaction data. This data is crucial for research to advance music generation technology and to improve this platform.
5.  **Data Distribution:** We reserve the right to publicly release collected text prompts and voting data (but not the generated audio itself, which is subject to the terms of the individual AI models) under a Creative Commons Attribution (CC-BY) license or a similar open license.
6.  **Feedback:** Your feedback is valuable. Please report any bugs, issues, or surprising outputs.

#### Please report any bugs or issues to our [Discord](https://discord.gg/6GXcFg3TH8)/arena-feedback channel.
"""

acknowledgment_md = """
## Acknowledgment
We are incredibly grateful for the support from the following organizations, which makes this research and platform possible:
[LM Arena](https://blog.lmarena.ai/about/).

<div class="sponsor-image-about">
    <a href="https://blog.lmarena.ai"><img src="https://media.licdn.com/dms/image/v2/D560BAQFN6nC2aa-L6Q/company-logo_200_200/B56Zbuv79gGoAI-/0/1747762266220/lmarena_logo?e=1753315200&amp;v=beta&amp;t=Ee-WCpcVCrhhXqY2MGXQ_laqU8WFiwOBSjbeO_T6hzE" loading="lazy" alt="LMArena logo" style="height:50px;"></a>
</div>
"""
ARENA_TYPE = ArenaType.TXT2MUSIC
        
def send_vote(pair_id: str, user_id: str, winning_model: str, losing_model: str,
              winning_audio_id: str, losing_audio_id: str, winning_index: int, prompt: str):
    payload = {
        "pairId": pair_id,
        "userId": user_id,
        "winningModel": winning_model,
        "losingModel": losing_model,
        "winningAudioId": winning_audio_id,
        "losingAudioId": losing_audio_id,
        "winningIndex": winning_index,
        "prompt": prompt
    }

    response = requests.post(f"{BACKEND_URL}/record_vote", json=payload)
    if response.ok:
        print("✅ Vote recorded!")
    else:
        print("❌ Failed to record vote:", response.status_code, response.text)


def sanitize_filename(text):
    words = re.findall(r'\w+', text)
    return "_".join(words[:3])

def decode_base64_audio(audio_base64: str, prompt: str, model: str, audio_type: str) -> str:
    audio_bytes = base64.b64decode(audio_base64)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sanitized_prompt = sanitize_filename(prompt)
    filename = f"{timestamp}_{sanitized_prompt}_Model {audio_type}_{model}.mp3"

    file_path = f"/tmp/{filename}"
    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    return file_path

def call_backend_and_get_music(prompt, lyrics="", user_id="test_user", seed=42, show_lyrics=False):

    full_prompt = prompt + (f"\nLyrics: {lyrics}" if lyrics.strip() else "")
    print(f"DEBUG: full_prompt: {full_prompt}")

    if lyrics.strip(): selected_models = ["songgen", "acestep"]
    else: selected_models = ["musicgen-small", "musicgen-large", "sao", "songgen", "acestep"]
    print(f"DEBUG: selected_models: {selected_models}")

    # model_a, model_b = random.sample(selected_models, 2) # Commented; Random Selection will be happened in the API-level

    '''
    # Same format with AudioPairRequest in API
    prompt: str
    user_id: str = Field(..., alias="userId")
    seed: Optional[int] = None
    lyrics: bool = False
    lyricsText: Optional[str] = None
    '''
    payload = {
        "prompt": prompt,
        "userId": user_id,
        "seed": seed,
        "lyrics": show_lyrics,
        "lyricsText": lyrics.strip() if lyrics.strip() else None
    }
    try:
        res = requests.post(f"{BACKEND_URL}/generate_audio_pair", json=payload)
        res.raise_for_status()
        response_json = res.json()

        audio_1_base64 = response_json["audioItems"][0]["audioDataBase64"]
        audio_2_base64 = response_json["audioItems"][1]["audioDataBase64"]
        model_a = response_json["audioItems"][0]["model"]
        model_b = response_json["audioItems"][1]["model"]
        pair_id = response_json["pairId"]

        audio_1 = decode_base64_audio(audio_1_base64, prompt, model_a, "A")
        audio_2 = decode_base64_audio(audio_2_base64, prompt, model_b, "B")

        return (
            pair_id,
            audio_1,
            audio_2,
            f"**Model A: {model_a}**",
            f"**Model B: {model_b}**",
            audio_1,
            audio_2
        )

    except Exception as e:
        if "[Errno 111]" in str(e) or "Connection refused" in str(e).lower():
            raise gr.Error("🛠️ The AI model service is temporarily unavailable, possibly for maintenance. Please try again in a little while. We apologize for any inconvenience.", duration=10)
        print(f"Error calling backend: {e}")
        return None, None, None, "Model A: Error", "Model B: Error", None, None

def prepare_download_file(winning_index, audio_1_path, audio_2_path):
    if winning_index == 0:
        return gr.update(value=audio_1_path, visible=True)
    elif winning_index == 1:
        return gr.update(value=audio_2_path, visible=True)
    else:
        return gr.update(visible=False)

def set_global_vars(
    enable_moderation_,
    use_remote_storage_,
):
    global enable_moderation, use_remote_storage
    enable_moderation = enable_moderation_
    use_remote_storage = use_remote_storage_

def get_conv_log_filename(arena_type=ARENA_TYPE, has_csam_image=False):
    t = datetime.datetime.now()
    conv_log_filename = f"{t.year}-{t.month:02d}-{t.day:02d}-conv.json"
    name = os.path.join(LOGDIR, f"txt2music-{conv_log_filename}")
    
    return name

def load_demo(url_params, request: gr.Request):
    global models

    print(f"load_demo executed: {load_demo}")
    ip = get_ip(request)
    logger.info(f"load_demo. ip: {ip}. params: {url_params}") # ip: 143.215.16.196. params: {}

    logger.info(f"args.model_list_mode: {args.model_list_mode}") # 'once'

    return None, None

def vote_last_response(
    vote_type,
    model_selector,
    request: gr.Request,
    model_a='musicgen',
    model_b='riffusionv1',
    pair_id=None,
    audio_id_a=None,
    audio_id_b=None,
    prompt=None,
    a_listen_time=0.0,
    b_listen_time=0.0,
):

    ip = get_ip(request)
    filename = get_conv_log_filename()

    # Determine winning and losing models & audio IDs
    if vote_type == "a_better":
        winning_model = model_a
        losing_model = model_b
        winning_audio_id = audio_id_a
        losing_audio_id = audio_id_b
        winning_index = 0
    elif vote_type == "b_better":
        winning_model = model_b
        losing_model = model_a
        winning_audio_id = audio_id_b
        losing_audio_id = audio_id_a
        winning_index = 1
    elif vote_type == "tie":
        winning_model = "tie"
        losing_model = "tie"
        winning_audio_id = "tie"
        losing_audio_id = "tie"
        winning_index = -1
    elif vote_type == "both_bad":
        winning_model = "both_bad"
        losing_model = "both_bad"
        winning_audio_id = "both_bad"
        losing_audio_id = "both_bad"
        winning_index = -1
    else:
        winning_model = None
        losing_model = None
        winning_audio_id = None
        losing_audio_id = None
        winning_index = -1

    # Send to backend only if we have the required info
    if pair_id and winning_model and winning_audio_id and prompt is not None:
        send_vote(
            pair_id,
            ip,
            winning_model,
            losing_model,
            winning_audio_id,
            losing_audio_id,
            winning_index,
            prompt,
        )

    # Local logging
    data = {
        "tstamp": round(time.time(), 4),
        "type": vote_type,
        "model": model_selector,
        "model_a": model_a,
        "model_b": model_b,
        "a_listen_time": round(a_listen_time, 2),
        "b_listen_time": round(b_listen_time, 2),
        "ip": ip,
        "prompt": prompt,
        "pair_id": pair_id,
        "winning_model": winning_model,
        "losing_model": losing_model,
        "winning_audio_id": winning_audio_id,
        "losing_audio_id": losing_audio_id,
        "winning_index": winning_index,
    }

    with open(filename, "a") as fout:
        fout.write(json.dumps(data) + "\n")

    get_remote_logger().log(data)

    
def a_better_last_response(state, model_selector, request: gr.Request, model_a, model_b, pair_id, audio_id_a, audio_id_b, current_prompt, a_listen_time, b_listen_time):
    ip = get_ip(request)
    logger.info(f"a is better. ip: {ip}")
    print(f"DEBUG: a_better_last_response")
    vote_last_response(
        "a_better", model_selector, request,
        model_a=model_a,
        model_b=model_b,
        pair_id=pair_id,
        audio_id_a=audio_id_a,
        audio_id_b=audio_id_b,
        prompt=current_prompt,
        a_listen_time=a_listen_time,
        b_listen_time=b_listen_time,
    )
    return (
        "",
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False), 
        gr.update(interactive=False),
        True # vote_cast_state
    )

def b_better_last_response(state, model_selector, request: gr.Request, model_a, model_b, pair_id, audio_id_a, audio_id_b, current_prompt, a_listen_time, b_listen_time):
    ip = get_ip(request)
    logger.info(f"b is better. ip: {ip}")
    print(f"DEBUG: b_better_last_response")
    vote_last_response(
        "b_better", model_selector, request,
        model_a=model_a,
        model_b=model_b,
        pair_id=pair_id,
        audio_id_a=audio_id_a,
        audio_id_b=audio_id_b,
        prompt=current_prompt,
        a_listen_time=a_listen_time,
        b_listen_time=b_listen_time,
    )
    return ("",) + (disable_btn,) * 4 + (True,)

def tie_last_response(state, model_selector, request: gr.Request, model_a, model_b, pair_id, audio_id_a, audio_id_b, current_prompt, a_listen_time, b_listen_time):
    ip = get_ip(request)
    logger.info(f"tie. ip: {ip}")
    print(f"DEBUG: tie_last_response")
    vote_last_response(
        "tie", model_selector, request,
        model_a=model_a,
        model_b=model_b,
        pair_id=pair_id,
        audio_id_a=audio_id_a,
        audio_id_b=audio_id_b,
        prompt=current_prompt,
        a_listen_time=a_listen_time,
        b_listen_time=b_listen_time,
    )
    return ("",) + (disable_btn,) * 4 + (True,)

def both_bad_last_response(state, model_selector, request: gr.Request, model_a, model_b, pair_id, audio_id_a, audio_id_b, current_prompt, a_listen_time, b_listen_time):
    ip = get_ip(request)
    logger.info(f"both are bad ip: {ip}")
    print(f"DEBUG: both_bad_last_response")
    vote_last_response(
        "both_bad", model_selector, request,
        model_a=model_a,
        model_b=model_b,
        pair_id=pair_id,
        audio_id_a=audio_id_a,
        audio_id_b=audio_id_b,
        prompt=current_prompt,
        a_listen_time=a_listen_time,
        b_listen_time=b_listen_time,
    )
    return ("",) + (disable_btn,) * 4 + (True,)


def get_ip(request: gr.Request):
    if "cf-connecting-ip" in request.headers:
        ip = request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        ip = request.headers["x-forwarded-for"]
        if "," in ip:
            ip = ip.split(",")[0]
    else:
        ip = request.client.host
    return ip

def model_worker_stream_iter(
    conv,
    model_name,
    worker_addr,
    prompt,
    temperature,
    repetition_penalty,
    top_p,
    max_new_tokens,
    images,
):
    # Make requests
    gen_params = {
        "model": model_name,
        "prompt": prompt,
        "temperature": temperature,
        "repetition_penalty": repetition_penalty,
        "top_p": top_p,
        "max_new_tokens": max_new_tokens,
        "stop": conv.stop_str,
        "stop_token_ids": conv.stop_token_ids,
        "echo": False,
    }

    logger.info(f"==== request ====\n{gen_params}")

    if len(images) > 0:
        gen_params["images"] = images

    # Stream output
    response = requests.post(
        worker_addr + "/worker_generate_stream",
        headers=headers,
        json=gen_params,
        stream=True,
        timeout=WORKER_API_TIMEOUT,
    )
    for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            data = json.loads(chunk.decode())
            yield data


def is_limit_reached(model_name, ip):
    monitor_url = "http://localhost:9090"
    try:
        ret = requests.get(
            f"{monitor_url}/is_limit_reached?model={model_name}&user_id={ip}", timeout=1
        )
        obj = ret.json()
        return obj
    except Exception as e:
        logger.info(f"monitor error: {e}")
        return None

def get_model_description_md(models):
    model_description_md = """
| | | |
| ---- | ---- | ---- |
"""
    ct = 0
    visited = set()
    for i, name in enumerate(models):
        minfo = get_model_info(name)
        if minfo.simple_name in visited:
            continue
        visited.add(minfo.simple_name)
        one_model_md = f"[{minfo.simple_name}]({minfo.link}): {minfo.description}"

        if ct % 3 == 0:
            model_description_md += "|"
        model_description_md += f" {one_model_md} |"
        if ct % 3 == 2:
            model_description_md += "\n"
        ct += 1
    return model_description_md

def get_model_description_md_from_json(json_path, display_model_list):
    with open(json_path, "r") as f:
        model_info = json.load(f)

    md = "| | | |\n|---|---|---|\n"
    row = []

    for i, display_name in enumerate(display_model_list):
        model_key = DISPLAY_NAME_TO_KEY[display_name]
        model = model_info[model_key]
        one = f"[{display_name}]({model['link']}): {model['description']}"
        row.append(one)
        if len(row) == 3:
            md += "| " + " | ".join(row) + " |\n"
            row = []

    if row:  # fill the last row
        while len(row) < 3:
            row.append("")
        md += "| " + " | ".join(row) + " |\n"

    return md

def toggle_lyrics_box(show_lyrics):
    return (
        gr.update(visible=show_lyrics),
        gr.update(visible=show_lyrics),
    )

def build_single_model_ui(models, add_promotion_links=False):
    #notice_markdown = f"""# 🎧 Music Arena: Free AI Music Generation to Compare & Test Best Music Generative AIs"""

    state = gr.State()
    #gr.Markdown(notice_markdown, elem_id="notice_markdown")
    prompt_state = gr.State("")
    audio_id_a_state, audio_id_b_state = gr.State(""), gr.State("")
    a_listen_time_state, b_listen_time_state = gr.State(0.0), gr.State(0.0)
    a_start_time_state, b_start_time_state = gr.State(None), gr.State(None)
    vote_cast_state = gr.State(False)
    
    with gr.Group(elem_id="share-region-named"):
        with gr.Row(elem_id="model_selector_row"):
            model_selector = gr.Dropdown(
                choices=models,
                value=models[0] if len(models) > 0 else "",
                interactive=True,
                show_label=False,
                container=False,
                allow_custom_value=True,
                visible=False
            )
        with gr.Row():
            model_list = ["MusicGen - Small", "MusicGen - Large", "Stable Audio Open", "SongGen", "ACE-Step"]
            with gr.Accordion(f"🔍 Expand to see the descriptions of {len(model_list)} models", open=False):
                model_description_md = get_model_description_md_from_json("model/model_descriptions.json", model_list)
                gr.Markdown(model_description_md, elem_id="model_description_markdown")

        with gr.Blocks() as music_player:
            with gr.Row():
                with gr.Column():
                    music_player_A = gr.Audio(label="Generated Music A", interactive=False,
                                                elem_id="music-A", show_download_button=False,
                                                show_share_button=False, visible=True)
                with gr.Column():
                    music_player_B = gr.Audio(label="Generated Music B", interactive=False, 
                                              elem_id="music-B", show_download_button=False,
                                              show_share_button=False, visible=True)
                
            with gr.Row():
                model_a_label = gr.Markdown("**Model A: Unknown**", visible=False)
                model_b_label = gr.Markdown("**Model B: Unknown**", visible=False)
           
    download_file = gr.File(label="🎵 Download your voted music!", visible=False)
    status_text = gr.Markdown("⚠️ You must listen to at least 5 seconds of each audio before voting is enabled.")

    with gr.Row() as button_row:
        a_better_btn = gr.Button(value="👈 A is better", interactive=False, scale=1)
        b_better_btn = gr.Button(value="👉 B is better", interactive=False, scale=1)
        tie_btn = gr.Button(value="🤝 Tie", interactive=False, scale=1)
        both_bad_btn = gr.Button(value="👎 Both are bad", interactive=False, scale=1, visible=False) # Temporarily hidden (visible=False)

    gr.HTML('''
        <style>
        #lyrics_row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
        }
        </style>'''
    )
        
    with gr.Row(elem_id="custom-input-row"):
        with gr.Column(scale=7, min_width=120):
            textbox = gr.Textbox(
                show_label=False,
                placeholder="👉 Enter your prompt and press ENTER"
            )
        with gr.Column(scale=1, min_width=120):
            checkbox = gr.Checkbox(
                label="Lyrics", 
                interactive=True
            )
        with gr.Column(scale=2, min_width=120):
            send_btn = gr.Button(value="Send", variant="primary")

    lyrics_box = gr.Textbox(
        label="Lyrics Input",
        visible=False,
        interactive=True,
        lines=3,
        placeholder="🖋️ Enter lyrics here, or leave blank to automatically generate lyrics",
        elem_id="lyrics_input"
    )

    checkbox.change(
        fn=lambda show: gr.update(visible=show),
        inputs=checkbox,
        outputs=lyrics_box
    )
    
    lyrics_info_text = gr.Markdown("🔒 🔮 Surprise me is currently disabled — Coming Soon!")

    with gr.Row() as extra_button_row:
        surprise_me_btn = gr.Button(value="🔮 Surprise me", interactive=False)
        new_round_btn = gr.Button(value="🎲 New Round", interactive=False)
        regenerate_btn = gr.Button(value="🔄 Regenerate", interactive=False)

    if add_promotion_links: None

    """Music Player"""
    music_player_A.play(
        on_play_a,
        inputs=[a_start_time_state],
        outputs=[a_start_time_state],
    )
    music_player_A.pause(
        on_pause_a,
        inputs=[a_start_time_state, a_listen_time_state, b_listen_time_state, vote_cast_state],
        outputs=[
            a_start_time_state,
            a_listen_time_state,
            a_better_btn,
            b_better_btn,
            tie_btn,
            both_bad_btn,
            status_text
        ],
    )

    music_player_B.play(
        on_play_b,
        inputs=[b_start_time_state],
        outputs=[b_start_time_state],
    )

    music_player_B.pause(
        on_pause_b,
        inputs=[b_start_time_state, a_listen_time_state, b_listen_time_state, vote_cast_state],
        outputs=[
            b_start_time_state,
            b_listen_time_state,
            a_better_btn,
            b_better_btn,
            tie_btn,
            both_bad_btn,
            status_text
        ],
    )
    # Declare model_a_state, model_b_state, pair_id_state at the top of `build_single_model_ui`:
    model_a_state = gr.State("")
    model_b_state = gr.State("")
    pair_id_state = gr.State("")
    audio_1_path_state = gr.State("")
    audio_2_path_state = gr.State("")
    
    vote_buttons = [a_better_btn, b_better_btn, tie_btn, both_bad_btn]
    
    a_better_btn.click(
        fn=a_better_last_response,
        inputs=[state, model_selector, model_a_state, model_b_state, 
         pair_id_state, audio_id_a_state, audio_id_b_state, 
         textbox, a_listen_time_state, b_listen_time_state],
        outputs=[textbox] + vote_buttons + [vote_cast_state]
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda m_a, m_b: (
            gr.update(value=f"**Model A: {m_a}**", visible=True), 
            gr.update(value=f"**Model B: {m_b}**", visible=True)
        ),
        [model_a_state, model_b_state],
        [model_a_label, model_b_label]
    ).then(
    fn=prepare_download_file,
    inputs=[gr.State(0), audio_1_path_state, audio_2_path_state],
    outputs=[download_file]
    ).then(
    fn=lambda: gr.update(interactive=False),
    inputs=None,
    outputs=[regenerate_btn]
    )

    b_better_btn.click(
        fn=b_better_last_response,
        inputs=[state, model_selector, model_a_state, model_b_state, 
         pair_id_state, audio_id_a_state, audio_id_b_state, 
         textbox, a_listen_time_state, b_listen_time_state],
        outputs=[textbox] + vote_buttons + [vote_cast_state]
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda m_a, m_b: (
            gr.update(value=f"**Model A: {m_a}**", visible=True), 
            gr.update(value=f"**Model B: {m_b}**", visible=True)
        ),
        [model_a_state, model_b_state],
        [model_a_label, model_b_label]
    ).then(
    fn=prepare_download_file,
    inputs=[gr.State(1), audio_1_path_state, audio_2_path_state],
    outputs=[download_file]
    ).then(
    fn=lambda: gr.update(interactive=False),
    inputs=None,
    outputs=[regenerate_btn]
    )

    tie_btn.click(
        fn=tie_last_response,
        inputs=[state, model_selector, model_a_state, model_b_state, 
         pair_id_state, audio_id_a_state, audio_id_b_state, 
         textbox, a_listen_time_state, b_listen_time_state],
        outputs=[textbox] + vote_buttons + [vote_cast_state]
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda m_a, m_b: (
            gr.update(value=f"**Model A: {m_a}**", visible=True), 
            gr.update(value=f"**Model B: {m_b}**", visible=True)
        ),
        [model_a_state, model_b_state],
        [model_a_label, model_b_label]
    ).then(
    fn=prepare_download_file,
    inputs=[gr.State(-1), audio_1_path_state, audio_2_path_state],
    outputs=[download_file]
    ).then(
    fn=lambda: gr.update(interactive=False),
    inputs=None,
    outputs=[regenerate_btn]
    )

    both_bad_btn.click(
        fn=both_bad_last_response,
        inputs=[state, model_selector, model_a_state, model_b_state, 
         pair_id_state, audio_id_a_state, audio_id_b_state, 
         textbox, a_listen_time_state, b_listen_time_state],
        outputs=[textbox] + vote_buttons + [vote_cast_state]
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda m_a, m_b: (
            gr.update(value=f"**Model A: {m_a}**", visible=True), 
            gr.update(value=f"**Model B: {m_b}**", visible=True)
        ),
        [model_a_state, model_b_state],
        [model_a_label, model_b_label]
    ).then(
    fn=prepare_download_file,
    inputs=[gr.State(-1), audio_1_path_state, audio_2_path_state],
    outputs=[download_file]
    ).then(
    fn=lambda: gr.update(interactive=False),
    inputs=None,
    outputs=[regenerate_btn]
    )

    surprise_me_btn.click(
        fn=lambda: [gr.update(interactive=False)] * 4,
        inputs=None,
        outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn]
    ).then(
        fn=lambda: [gr.update(interactive=False)]*2+[gr.update(interactive=True)]+[gr.update(interactive=False)],
        inputs=None,
        outputs=[send_btn, surprise_me_btn, new_round_btn, regenerate_btn]
    ).then(
        fn=lambda: (
            0.0,  # reset a_listen_time
            0.0,  # reset b_listen_time
            None, # reset a_start_time
            None  # reset b_start_time
        ),
        inputs=None,
        outputs=[
            a_listen_time_state,
            b_listen_time_state,
            a_start_time_state,
            b_start_time_state
        ]
    ).then(
        fn=lambda: (
            gr.update(visible=False),  # hide download file
            "⚠️ You must listen to at least 5 seconds of each audio before voting is enabled."
        ),
        inputs=None,
        outputs=[download_file, status_text]
    ).then(
        fn=lambda: (
            gr.update(value="**Model A: Unknown**", visible=False),
            gr.update(value="**Model B: Unknown**", visible=False)
        ),
        inputs=None,
        outputs=[model_a_label, model_b_label]
    ).then(
        fn=load_random_mock_pair,
        inputs=None,
        outputs=[
            pair_id_state,          # pair_id
            music_player_A,         # audio 1
            music_player_B,         # audio 2
            model_a_label,          # Model A Markdown
            model_b_label,          # Model B Markdown
            audio_1_path_state,     # audio 1 path (for download)
            audio_2_path_state,     # audio 2 path (for download)
            pair_id_state,          # (again, redundant but safe)
            model_a_state,          # Model A name
            model_b_state,          # Model B name
            textbox                 # prompt
        ]
    )

    new_round_btn.click(
        fn=lambda: (
            None,           # state
            "",             # textbox
            None, None,     # music_player_A, music_player_B
            gr.update(value="**Model A: Unknown**", visible=False),  # model_a_label
            gr.update(value="**Model A: Unknown**", visible=False),  # model_a_label (duplicate in output list)
            gr.update(value="**Model B: Unknown**", visible=False),  # model_b_label
            gr.update(value="**Model B: Unknown**", visible=False),  # model_b_label (duplicate)
            0.0, 0.0,       # a_listen_time_state, b_listen_time_state
            None, None,     # a_start_time_state, b_start_time_state
            "", "", "",     # model_a_state, model_b_state, pair_id_state
            gr.update(visible=False),      # download_file
            "⚠️ You must listen to at least 5 seconds of each audio before voting is enabled.",  # status_text
            gr.update(interactive=False),  # a_better_btn
            gr.update(interactive=False),  # b_better_btn
            gr.update(interactive=False),  # tie_btn
            gr.update(interactive=False),  # both_bad_btn
            gr.update(interactive=True),  # send_btn
            gr.update(interactive=False),   # surprise_me_btn
            gr.update(interactive=False),   # regenerate_btn
            False # vote_cast_state
        ),
        inputs=None,
        outputs=[
            state,
            textbox,
            music_player_A, music_player_B,
            model_a_label, model_a_label,
            model_b_label, model_b_label,
            a_listen_time_state, b_listen_time_state,
            a_start_time_state, b_start_time_state,
            model_a_state, model_b_state, pair_id_state,
            download_file,
            status_text,
            vote_buttons[0], vote_buttons[1], vote_buttons[2], vote_buttons[3],
            send_btn, surprise_me_btn, regenerate_btn, vote_cast_state
        ]
    )

    regenerate_btn.click(
        fn=lambda: (
            0.0,  # reset a_listen_time
            0.0,  # reset b_listen_time
            None, # reset a_start_time
            None  # reset b_start_time
        ),
        inputs=None,
        outputs=[
            a_listen_time_state,
            b_listen_time_state,
            a_start_time_state,
            b_start_time_state
        ]
    ).then(
        fn=lambda: (
            gr.update(interactive=False), # hide voting buttons
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        ),
        inputs=None,
        outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn]
    ).then(
        fn=lambda: (
            gr.update(visible=False),  # hide download file
            "⚠️ You must listen to at least 5 seconds of each audio before voting is enabled."
        ),
        inputs=None,
        outputs=[download_file, status_text]
    ).then(
        fn=lambda: (
            gr.update(value="**Model A: Unknown**", visible=False),
            gr.update(value="**Model B: Unknown**", visible=False)
        ),
        inputs=None,
        outputs=[model_a_label, model_b_label]
    ).then(
        fn=lambda prompt, lyrics, show_lyrics: call_backend_and_get_music(
            prompt=prompt,
            lyrics=lyrics,
            show_lyrics=show_lyrics
        ),
        inputs=[textbox, lyrics_box, checkbox],
        outputs=[
            pair_id_state,
            music_player_A,
            music_player_B,
            model_a_label,
            model_b_label,
            audio_1_path_state,
            audio_2_path_state
        ]
    ).then(
        fn=lambda pair_id, model_a_label, model_b_label: (
            pair_id,
            model_a_label.replace("**Model A: ", "").replace("**", ""),
            model_b_label.replace("**Model B: ", "").replace("**", "")
        ),
        inputs=[pair_id_state, model_a_label, model_b_label],
        outputs=[pair_id_state, model_a_state, model_b_state]
    )
    
    send_btn.click(
        fn=lambda prompt, lyrics, show_lyrics: None,
        inputs=[textbox, lyrics_box, checkbox],
        outputs=[],
        js="""
        () => {
            const textbox = document.querySelector('#custom-input-row textarea');
            const lyricsbox = document.querySelector('textarea#lyrics_input');
            const checkbox = document.querySelector('#custom-input-row input[type="checkbox"]');
            if (!textbox || textbox.value.trim() === "") {
                alert("⚠️ Please enter a prompt before pressing Send.");
                throw new Error("Prompt is empty");
            }
            return [textbox.value, lyricsbox ? lyricsbox.value : "", checkbox?.checked];
        }"""
    ).then(
        fn=lambda: (
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        ),
        inputs=None,
        outputs=[send_btn, surprise_me_btn, new_round_btn]
    ).then(
        fn=lambda prompt, lyrics, show_lyrics: call_backend_and_get_music(
            prompt, lyrics=lyrics, show_lyrics=show_lyrics
        ),
        inputs=[textbox, lyrics_box, checkbox],
        outputs=[
            pair_id_state,
            music_player_A,
            music_player_B,
            model_a_label,
            model_b_label,
            audio_1_path_state,
            audio_2_path_state
        ]
    ).then(
        fn=lambda pair_id, model_a_label, model_b_label: (
            pair_id,
            model_a_label.replace("**Model A: ", "").replace("**", ""),
            model_b_label.replace("**Model B: ", "").replace("**", "")
        ),
        inputs=[pair_id_state, model_a_label, model_b_label],
        outputs=[pair_id_state, model_a_state, model_b_state]
    ).then(
        fn=lambda: [gr.update(interactive=False)] * 4,
        inputs=None,
        outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn]
    ).then(
        fn=lambda: [gr.update(interactive=True)] * 2,
        inputs=None,
        outputs=[new_round_btn, regenerate_btn]
    )

    return [state, model_selector]


def build_demo(models):
    with gr.Blocks(
        title="Music Arena: Free Music AI Generation to Compare & Test Best Music Generative AIs",
        css="style.css",
    ) as demo:
        url_params = gr.JSON(visible=False)
        notice_markdown = f"""# 🎧 Music Arena: Free AI Music Generation to Compare & Test Best Music Generative AIs"""
        gr.Markdown(notice_markdown, elem_id="notice_markdown")
        #state, model_selector = build_single_model_ui(models)
        
        with gr.Tabs(elem_id="main_tabs"):
            with gr.TabItem("⚔️ Arena", elem_id="arena_tab"):
                state, model_selector = build_single_model_ui(models)
                state_component_from_arena = state
                model_selector_component_from_arena = model_selector
            with gr.TabItem("📊 Leaderboard", elem_id="leaderboard_tab"):
                leaderboard_display_component = build_leaderboard_ui()
            with gr.TabItem("📜 About & Terms", elem_id="about_tab"):
                gr.Markdown(about_md, elem_id="about_markdown")
                gr.Markdown(open_source_md, elem_id="open_source_markdown")
                gr.Markdown(terms_of_service_md, elem_id="terms_of_service_markdown")
                gr.Markdown(acknowledgment_md, elem_id="acknowledgment_markdown")

        if args.model_list_mode not in ["once", "reload"]:
            raise ValueError(f"Unknown model list mode: {args.model_list_mode}")

        if args.show_terms_of_use: load_js = get_window_url_params_with_tos_js
        else: load_js = get_window_url_params_js

        demo.load(
            load_demo,
            [url_params],
            [state,model_selector],
            js=load_js,
        )
    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--share",
        action="store_true",
        help="Whether to generate a public, shareable link",
    )
    parser.add_argument(
        "--controller-url",
        type=str,
        default="http://localhost:21001",
        help="The address of the controller",
    )
    parser.add_argument(
        "--concurrency-count",
        type=int,
        default=10,
        help="The concurrency count of the gradio queue",
    )
    parser.add_argument(
        "--model-list-mode",
        type=str,
        default="once",
        choices=["once", "reload"],
        help="Whether to load the model list once or reload the model list every time",
    )
    parser.add_argument(
        "--moderate",
        action="store_true",
        help="Enable content moderation to block unsafe inputs",
    )
    parser.add_argument(
        "--show-terms-of-use",
        action="store_true",
        help="Shows term of use before loading the demo",
    )
    parser.add_argument(
        "--gradio-root-path",
        type=str,
        help="Sets the gradio root path, eg /abc/def. Useful when running behind a reverse-proxy or at a custom URL path prefix",
    )
    parser.add_argument(
        "--use-remote-storage",
        action="store_true",
        default=False,
        help="Uploads image files to google cloud storage if set to true",
    )
    args = parser.parse_args()
    logger.info(f"args: {args}")

    set_global_vars(args.moderate, args.use_remote_storage)
    models, all_models = [], []

    # Launch the demo
    demo = build_demo(models)
    demo.queue(
        default_concurrency_limit=args.concurrency_count,
        status_update_rate=10,
        api_open=False
    ).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=200,
        auth=None,
        root_path=args.gradio_root_path,
    )