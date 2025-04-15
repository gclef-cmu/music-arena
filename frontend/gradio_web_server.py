"""
The gradio demo server for chatting with a single model.

Debugging Ongoing (Yonghyun)

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
)
print(f"Using BACKEND_URL={BACKEND_URL}")

class ArenaType:
    TXT2MUSIC = "txt2music-arena"


# MUSICARENA (Previous version; TODO)
from api_provider import get_music_api_provider

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

def enable_vote_buttons_if_ready(a_listen_time, b_listen_time):
    if a_listen_time >= 5.0 and b_listen_time >= 5.0:
        return [gr.update(interactive=True)] * 4
    return [gr.update(interactive=False)] * 4

def update_vote_status(a_listen_time, b_listen_time):
    if a_listen_time >= 5.0 and b_listen_time >= 5.0:
        return "✅ You can now vote!"
    else:
        return "⚠️ You must listen to at least 5 seconds of each audio before voting is enabled."

def on_play_a(a_start_time):
    return time.time()

def on_play_b(b_start_time):
    return time.time()

def on_pause_a(a_start_time, a_listen_time, b_listen_time):
    if a_start_time:
        a_listen_time += time.time() - a_start_time
        a_start_time = None
    buttons = enable_vote_buttons_if_ready(a_listen_time, b_listen_time)
    message = update_vote_status(a_listen_time, b_listen_time)
    return a_start_time, a_listen_time, buttons[0], buttons[1], buttons[2], buttons[3], message

def on_pause_b(b_start_time, a_listen_time, b_listen_time):
    if b_start_time:
        b_listen_time += time.time() - b_start_time
        b_start_time = None
    buttons = enable_vote_buttons_if_ready(a_listen_time, b_listen_time)
    message = update_vote_status(a_listen_time, b_listen_time)
    return b_start_time, b_listen_time, buttons[0], buttons[1], buttons[2], buttons[3], message

def load_random_mock_pair(json_path="surprise_me/mock_pairs.json"):
    with open(json_path, "r") as f:
        mock_data = json.load(f)

    selected = random.choice(mock_data)
    prompt = selected["prompt"]
    basename = selected["basename"]

    models = ["musicgen-small", "musicgen-large", "sao", "songgen"]
    
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

acknowledgment_md = """
### Terms of Service

Users are required to agree to the following terms before using the service:

The service is a research preview. It only provides limited safety measures and may generate offensive content.
It must not be used for any illegal, harmful, violent, racist, or sexual purposes.
Please do not upload any private information.
The service collects user dialogue data, including both text and images, and reserves the right to distribute it under a Creative Commons Attribution (CC-BY) or a similar license.

#### Please report any bug or issue to our [Discord](https://discord.gg/6GXcFg3TH8)/arena-feedback.

### Acknowledgment
We thank [UC Berkeley SkyLab](https://sky.cs.berkeley.edu/), [a16z](https://a16z.com/announcing-our-latest-open-source-ai-grants/), [Sequoia](https://www.sequoiacap.com/article/building-the-future-meet-the-2024-sequoia-open-source-fellows/), [Fireworks AI](https://fireworks.ai/), [Together AI](https://together.ai/), [RunPod](https://runpod.io), [Anyscale](https://anyscale.com/), [Replicate](https://replicate.com/), [Fal AI](https://fal.ai/), [Hyperbolic](https://hyperbolic.xyz/), [Kaggle](https://www.kaggle.com/), [MBZUAI](https://mbzuai.ac.ae/), [HuggingFace](https://huggingface.co/) for their generous sponsorship.

<div class="sponsor-image-about">
    <a href="https://sky.cs.berkeley.edu/"><img src="https://storage.googleapis.com/public-arena-asset/skylab.png" alt="SkyLab"></a>
    <a href="https://a16z.com/announcing-our-latest-open-source-ai-grants/"><img src="https://storage.googleapis.com/public-arena-asset/a16z.jpeg" alt="a16z"></a>
    <a href="https://www.sequoiacap.com/article/building-the-future-meet-the-2024-sequoia-open-source-fellows/"><img src="https://storage.googleapis.com/public-arena-asset/sequoia.png" alt="Sequoia" style="padding-top:10px; padding-bottom:10px;"></a>
    <a href="https://fireworks.ai/"><img src="https://storage.googleapis.com/public-arena-asset/fireworks.png" alt="Fireworks AI" style="padding-top:10px; padding-bottom:10px;"></a>
    <a href="https://together.ai/"><img src="https://storage.googleapis.com/public-arena-asset/together.png" alt="Together AI"></a>
    <a href="https://runpod.io/"><img src="https://storage.googleapis.com/public-arena-asset/runpod-logo.jpg" alt="RunPod"></a>
    <a href="https://anyscale.com/"><img src="https://storage.googleapis.com/public-arena-asset/anyscale.png" alt="AnyScale"></a>
    <a href="https://replicate.com/"><img src="https://storage.googleapis.com/public-arena-asset/replicate.png" alt="Replicate" style="padding-top:3px; padding-bottom:3px;"></a>
    <a href="https://fal.ai/"><img src="https://storage.googleapis.com/public-arena-asset/fal.png" alt="Fal" style="padding-top:3px; padding-bottom:3px;"></a>
    <a href="https://hyperbolic.xyz/"><img src="https://storage.googleapis.com/public-arena-asset/hyperbolic_logo.png" alt="Hyperbolic"></a>
    <a href="https://www.kaggle.com/"><img src="https://storage.googleapis.com/public-arena-asset/kaggle.png" alt="Kaggle"></a>
    <a href="https://mbzuai.ac.ae/"><img src="https://storage.googleapis.com/public-arena-asset/mbzuai.jpeg" alt="MBZUAI"></a>
    <a href="https://huggingface.co/"><img src="https://storage.googleapis.com/public-arena-asset/huggingface.png" alt="HuggingFace"></a>
</div>
"""

api_endpoint_info = {}

ARENA_TYPE = ArenaType.TXT2MUSIC #ArenaType.TXT2MUSIC # ArenaType.TEXT

# BACKEND (START)
def generate_audio_pair(prompt: str, user_id: str):
    # Referred to server/api/models.py
    payload = {
        "prompt": prompt,
        "userId": user_id, 
        "seed": seed
    }

    response = requests.post(f"{BACKEND_URL}/generate_audio_pair", json=payload)

    if response.status_code == 200:
        return response.json()  # AudioPairResponse Format
    else:
        print("Error:", response.status_code, response.text)
        
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

def decode_base64_audio(audio_base64: str, prompt: str, model: str) -> str:
    audio_bytes = base64.b64decode(audio_base64)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    sanitized_prompt = sanitize_filename(prompt)
    filename = f"{timestamp}_{sanitized_prompt}_{model}.mp3"

    file_path = f"/tmp/{filename}"
    with open(file_path, "wb") as f:
        f.write(audio_bytes)

    return file_path

def call_backend_and_get_music(prompt, user_id="test_user", seed=42):
    payload = {
        "prompt": prompt,
        "userId": user_id,
        "seed": seed
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

        audio_1 = decode_base64_audio(audio_1_base64, prompt, model_a)
        audio_2 = decode_base64_audio(audio_2_base64, prompt, model_b)

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
        print(f"Error calling backend: {e}")
        return None, None, None, "Model A: Error", "Model B: Error", None, None
    
# BACKEND (END)

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
    return ("",) + (disable_btn,) * 4

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
    return ("",) + (disable_btn,) * 4 

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
    return ("",) + (disable_btn,) * 4

# # To be fixed
# def regenerate(state, request: gr.Request):
#     ip = get_ip(request)
#     logger.info(f"regenerate. ip: {ip}")
#     if not state.regen_support:
#         state.skip_next = True
#         return (state, state.to_gradio_chatbot(), "", None) + (no_change_btn,) * 5
#     state.conv.update_last_message(None)
#     return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5
def regenerate(prompt, user_id="test_user", seed=42):
    return call_backend_and_get_music(prompt, user_id=user_id, seed=seed)


# def clear_history(request: gr.Request):
#     ip = get_ip(request)
#     logger.info(f"clear_history. ip: {ip}")
#     state = None
#     return (state, [], "") + (disable_btn,) * 5

def get_random_lyrics_block():
    samples = [
        "Let the rhythm take control",
        "Feel the beat within your soul",
        "Under stars, we lose it all",
        "Walking through the midnight rain",
        "Singing softly through the pain",
        "Hope will find us once again",
        "Colors swirling in the sky",
        "Lift your wings and learn to fly, Every note a lullaby.",
        "Dreams we chase with open eyes",
        "Melodies that never lie, Hearts collide and harmonize.",
    ]
    return random.choice(samples)

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

block_css = """
.prose {
    font-size: 105% !important;
}

#arena_leaderboard_dataframe table {
    font-size: 105%;
}
#full_leaderboard_dataframe table {
    font-size: 105%;
}

.tab-nav button {
    font-size: 18px;
}

.chatbot h1 {
    font-size: 130%;
}
.chatbot h2 {
    font-size: 120%;
}
.chatbot h3 {
    font-size: 110%;
}

#chatbot .prose {
    font-size: 90% !important;
}

.sponsor-image-about img {
    margin: 0 20px;
    margin-top: 20px;
    height: 40px;
    max-height: 100%;
    width: auto;
    float: left;
}

.cursor {
    display: inline-block;
    width: 7px;
    height: 1em;
    background-color: black;
    vertical-align: middle;
    animation: blink 1s infinite;
}

.dark .cursor {
    display: inline-block;
    width: 7px;
    height: 1em;
    background-color: white;
    vertical-align: middle;
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    50.1%, 100% { opacity: 0; }
}

.app {
  max-width: 100% !important;
  padding-left: 5% !important;
  padding-right: 5% !important;
}

a {
    color: #1976D2; /* Your current link color, a shade of blue */
    text-decoration: none; /* Removes underline from links */
}
a:hover {
    color: #63A4FF; /* This can be any color you choose for hover */
    text-decoration: underline; /* Adds underline on hover */
}

.block {
  overflow-y: hidden !important;
}

#custom-repochat-dataset .table {
    text-align: left !important;
}

#custom-repochat-dataset th {
    text-align: left !important;
}

#txt2img-prompt {
    font-size: 115%;
    text-align: center;
}

.grecaptcha-badge {
    visibility: hidden;
}

.explorer {
    overflow: hidden;
    height: 60vw;
    border: 1px solid lightgrey; 
    border-radius: 10px;
}

@media screen and (max-width: 769px) {
    .explorer {
        height: 180vw;
        overflow-y: scroll;
        width: 100%;
        overflow-x: hidden;
    }
}

#_Transparent_Rectangle_ {
    display: none;
}

#input_box textarea {
    padding-top: 6px !important;
    padding-bottom: 6px !important;
    min-height: 36px !important;
    line-height: 1 !important;
}

#custom-input-row {
    align-items: center !important;
    gap: 6px;
}
"""

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
    DISPLAY_NAME_TO_KEY = {
        "MusicGen - Small": "musicgen-small",
        "MusicGen - Large": "musicgen-large",
        "Stable Audio Open": "sao",
        "SongGen": "songgen",
    }

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

def build_about():
    about_markdown = """
# About Us
Chatbot Arena is an open platform for crowdsourced AI benchmarking, hosted by researchers at UC Berkeley [SkyLab](https://sky.cs.berkeley.edu/) and [LMArena](https://blog.lmarena.ai/about/). We open-source the [FastChat](https://github.com/lm-sys/FastChat) project at GitHub and release open datasets. We always welcome contributions from the community. If you're interested in collaboration, we'd love to hear from you!

## Open-source contributors
- Leads: [Wei-Lin Chiang](https://x.com/infwinston), [Anastasios Angelopoulos](https://x.com/ml_angelopoulos)
- Contributors: [Lianmin Zheng](https://lmzheng.net/), [Ying Sheng](https://sites.google.com/view/yingsheng/home), [Lisa Dunlap](https://www.lisabdunlap.com/), [Christopher Chou](https://www.linkedin.com/in/chrisychou), [Tianle Li](https://codingwithtim.github.io/), [Evan Frick](https://efrick2002.github.io/), [Aryan Vichare](https://www.aryanvichare.dev/), [Naman Jain](https://naman-ntc.github.io/), [Manish Shetty](https://manishs.org/), [Dacheng Li](https://dachengli1.github.io/), [Kelly Tang](https://www.linkedin.com/in/kelly-yuguo-tang/), [Siyuan Zhuang](https://www.linkedin.com/in/siyuanzhuang)
- Advisors: [Ion Stoica](http://people.eecs.berkeley.edu/~istoica/), [Joseph E. Gonzalez](https://people.eecs.berkeley.edu/~jegonzal/), [Hao Zhang](https://cseweb.ucsd.edu/~haozhang/), [Trevor Darrell](https://people.eecs.berkeley.edu/~trevor/)

## Learn more
- Chatbot Arena [paper](https://arxiv.org/abs/2403.04132), [launch blog](https://blog.lmarena.ai/), [dataset](https://github.com/lm-sys/FastChat/blob/main/docs/dataset_release.md), [policy](https://blog.lmarena.ai/blog/2024/policy/)
- LMSYS-Chat-1M dataset [paper](https://arxiv.org/abs/2309.11998), LLM Judge [paper](https://arxiv.org/abs/2306.05685)

## Contact Us
- Follow our [X](https://x.com/lmarena_ai), [Discord](https://discord.gg/6GXcFg3TH8), [小红书](https://www.xiaohongshu.com/user/profile/6184a3dd000000001000a8fc) or email us at `lmarena.ai@gmail.com`
- File issues on [GitHub](https://github.com/lm-sys/FastChat)
- Download our datasets and models on [HuggingFace](https://huggingface.co/lmarena-ai)

## Acknowledgment
We thank [SkyPilot](https://github.com/skypilot-org/skypilot) and [Gradio](https://github.com/gradio-app/gradio) team for their system support.
We also thank [UC Berkeley SkyLab](https://sky.cs.berkeley.edu/), [a16z](https://a16z.com/announcing-our-latest-open-source-ai-grants/), [Sequoia](https://www.sequoiacap.com/article/building-the-future-meet-the-2024-sequoia-open-source-fellows/), [Fireworks AI](https://fireworks.ai/), [Together AI](https://together.ai/), [RunPod](https://runpod.io), [Anyscale](https://anyscale.com/), [Replicate](https://replicate.com/), [Fal AI](https://fal.ai/), [Hyperbolic](https://hyperbolic.xyz/), [Kaggle](https://www.kaggle.com/), [MBZUAI](https://mbzuai.ac.ae/), [HuggingFace](https://huggingface.co/) for their generous sponsorship. Contact us to learn more about partnership.

<div class="sponsor-image-about">
    <a href="https://sky.cs.berkeley.edu/"><img src="https://storage.googleapis.com/public-arena-asset/skylab.png" alt="SkyLab"></a>
    <a href="https://a16z.com/announcing-our-latest-open-source-ai-grants/"><img src="https://storage.googleapis.com/public-arena-asset/a16z.jpeg" alt="a16z"></a>
    <a href="https://www.sequoiacap.com/article/building-the-future-meet-the-2024-sequoia-open-source-fellows/"><img src="https://storage.googleapis.com/public-arena-asset/sequoia.png" alt="Sequoia" style="padding-top:10px; padding-bottom:10px;"></a>
    <a href="https://fireworks.ai/"><img src="https://storage.googleapis.com/public-arena-asset/fireworks.png" alt="Fireworks AI" style="padding-top:10px; padding-bottom:10px;"></a>
    <a href="https://together.ai/"><img src="https://storage.googleapis.com/public-arena-asset/together.png" alt="Together AI"></a>
    <a href="https://runpod.io/"><img src="https://storage.googleapis.com/public-arena-asset/runpod-logo.jpg" alt="RunPod"></a>
    <a href="https://anyscale.com/"><img src="https://storage.googleapis.com/public-arena-asset/anyscale.png" alt="AnyScale"></a>
    <a href="https://replicate.com/"><img src="https://storage.googleapis.com/public-arena-asset/replicate.png" alt="Replicate" style="padding-top:3px; padding-bottom:3px;"></a>
    <a href="https://fal.ai/"><img src="https://storage.googleapis.com/public-arena-asset/fal.png" alt="Fal" style="padding-top:3px; padding-bottom:3px;"></a>
    <a href="https://hyperbolic.xyz/"><img src="https://storage.googleapis.com/public-arena-asset/hyperbolic_logo.png" alt="Hyperbolic"></a>
    <a href="https://www.kaggle.com/"><img src="https://storage.googleapis.com/public-arena-asset/kaggle.png" alt="Kaggle"></a>
    <a href="https://mbzuai.ac.ae/"><img src="https://storage.googleapis.com/public-arena-asset/mbzuai.jpeg" alt="MBZUAI"></a>
    <a href="https://huggingface.co/"><img src="https://storage.googleapis.com/public-arena-asset/huggingface.png" alt="HuggingFace"></a>
</div>
</div>
"""
    gr.Markdown(about_markdown, elem_id="about_markdown")

def toggle_lyrics_box(show_lyrics):
    return (
        gr.update(visible=show_lyrics),
        gr.update(visible=show_lyrics),
    )

def build_single_model_ui(models, add_promotion_links=False):
    promotion = (
        f"""
[小红书](https://www.xiaohongshu.com/user/profile/6184a3dd000000001000a8fc) | [Twitter](https://twitter.com/lmarena_ai) | [Discord](https://discord.gg/6GXcFg3TH8) | [Blog](https://blog.lmarena.ai/) | [GitHub](https://github.com/lm-sys/FastChat) | [Paper](https://arxiv.org/abs/2403.04132) | [Dataset](https://github.com/lm-sys/FastChat/blob/main/docs/dataset_release.md) | [Kaggle Competition](https://www.kaggle.com/competitions/wsdm-cup-multilingual-chatbot-arena)

{SURVEY_LINK}

## 👇 Choose any model to chat
"""
        if add_promotion_links
        else ""
    )

    notice_markdown = f"""
# 🎧 Music Arena: Free AI Music Generation to Compare & Test Best Music Generative AIs
{promotion}
"""

    state = gr.State()
    gr.Markdown(notice_markdown, elem_id="notice_markdown")
    audio_id_a_state = gr.State("")
    audio_id_b_state = gr.State("")
    prompt_state = gr.State("")
    a_listen_time_state = gr.State(0.0)
    b_listen_time_state = gr.State(0.0)
    a_start_time_state = gr.State(None)
    b_start_time_state = gr.State(None)
    
    with gr.Group(elem_id="share-region-named"):
        with gr.Row(elem_id="model_selector_row"):
            model_selector = gr.Dropdown(
                choices=models,
                value=models[0] if len(models) > 0 else "",
                interactive=True,
                show_label=False,
                container=False,
                allow_custom_value=True
            )
        with gr.Row():
            model_list = ["MusicGen - Small", "MusicGen - Large", "Stable Audio Open", "SongGen"]
            with gr.Accordion(f"🔍 Expand to see the descriptions of {len(model_list)} models", open=False):
                model_description_md = get_model_description_md_from_json("model/model_descriptions.json", model_list)
                gr.Markdown(model_description_md, elem_id="model_description_markdown")
                
        # Yonghyun (Add Gradio Audio Component for playing music)
        # Custom CSS for hiding default waveform & time info
        custom_css = """
        /* Hide waveform and time info */
        #custom-audio-1 canvas, 
        #custom-audio-1 canvas,
        #custom-audio-2 .waveform, 
        #custom-audio-2 .time-info {
            display: none !important;
        }"""

        def on_play():
            print("Audio started playing.")
        

        with gr.Blocks(css=custom_css) as music_player:
            
            # html_audio = gr.HTML("""
            # <audio id="audio1" src="audio_path.wav"></audio>

            # <script>
            # function playAudio() {
            #     const audio = document.getElementById("audio1");
            #     audio.play();
            # }
            # function pauseAudio() {
            #     const audio = document.getElementById("audio1");
            #     audio.pause();
            # }
            # function stopAudio() {
            #     const audio = document.getElementById("audio1");
            #     audio.pause();
            #     audio.currentTime = 0;
            # }
            # </script>
            # """)
            # with gr.Row():
            #     gr.HTML('<button onclick="playAudio()">▶️ Play</button>')
            #     gr.HTML('<button onclick="pauseAudio()">⏸️ Pause</button>')
            #     gr.HTML('<button onclick="stopAudio()">⏹️ Stop</button>')
                        
            with gr.Row():
                # Left Audio Player w/ Controls
                with gr.Column():
                    # Hidden Default Audio Player (will be controlled via JS)
                    gr.WaveformOptions(show_recording_waveform=False)
                    music_player_1 = gr.Audio(label="Generated Music A", interactive=False, 
                                                elem_id="custom-audio-1", show_download_button=False,
                                                show_share_button=False, visible=True)

                    # music_player_1.pause(on_pause_a)
                    # music_player_1.stop(on_pause_a)
                    # with gr.Row():
                    #     play_btn1 = gr.Button("▶️ Play", elem_id="play_btn_1", interactive=False)
                    #     pause_btn1 = gr.Button("⏸️ Pause", elem_id="pause_btn_1", interactive=False)
                    #     stop_btn1 = gr.Button("⏹️ Stop", elem_id="stop_btn_1", interactive=False)
                    #     forward_btn1 = gr.Button("⏩ +10s", elem_id="forward_btn_1", interactive=False)
                    #     backward_btn1 = gr.Button("⏪ -10s", elem_id="backward_btn_1", interactive=False)

                # Right Audio Player w/ Controls
                with gr.Column():
                    music_player_2 = gr.Audio(label="Generated Music B", interactive=False, 
                                              elem_id="custom-audio-2", show_download_button=False,
                                              show_share_button=False, visible=True)
                    # music_player_2.pause(on_pause_b)
                    # music_player_2.stop(on_pause_b)
                    # with gr.Row():
                    #     play_btn2 = gr.Button("▶️ Play", elem_id="play_btn_2", interactive=False)
                    #     pause_btn2 = gr.Button("⏸️ Pause", elem_id="pause_btn_2", interactive=False)
                    #     stop_btn2 = gr.Button("⏹️ Stop", elem_id="stop_btn_2", interactive=False)
                    #     forward_btn2 = gr.Button("⏩ +10s", elem_id="forward_btn_2", interactive=False)
                    #     backward_btn2 = gr.Button("⏪ -10s", elem_id="backward_btn_2", interactive=False)

            with gr.Row():
                model_a_label = gr.Markdown("**Model A: Unknown**", visible=False)
                model_b_label = gr.Markdown("**Model B: Unknown**", visible=False)

           
    download_file = gr.File(label="🎵 Download your voted music!", visible=False)

    status_text = gr.Markdown("⚠️ You must listen to at least 5 seconds of each audio before voting is enabled.")

    with gr.Row() as button_row:
        # Yonghyun
        a_better_btn = gr.Button(value="👈 A is better", interactive=False)
        b_better_btn = gr.Button(value="👉 B is better", interactive=False)
        tie_btn = gr.Button(value="🤝 Tie", interactive=False)
        both_bad_btn = gr.Button(value="👎 Both are bad", interactive=False)
        
        # music_player_1.play(on_play_a)
        music_player_1.play(
            on_play_a,
            inputs=[a_start_time_state],
            outputs=[a_start_time_state],
        )
        # music_player_1.pause(
        #     on_pause_a,
        #     outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn, status_text]
        # )
        music_player_1.pause(
            on_pause_a,
            inputs=[a_start_time_state, a_listen_time_state, b_listen_time_state],
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
        #music_player_1.pause(lambda: enable_vote_buttons_if_ready(), outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn])
        #music_player_1.stop(lambda: enable_vote_buttons_if_ready(), outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn])
        #music_player_2.play(on_play_b)
        music_player_2.play(
            on_play_b,
            inputs=[b_start_time_state],
            outputs=[b_start_time_state],
        )
        # music_player_2.pause(
        #     on_pause_b,
        #     outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn, status_text]
        # )
        music_player_2.pause(
            on_pause_b,
            inputs=[b_start_time_state, a_listen_time_state, b_listen_time_state],
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
        #music_player_2.pause(lambda: enable_vote_buttons_if_ready(), outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn])
        #music_player_2.stop(lambda: enable_vote_buttons_if_ready(), outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn])
        
    html_code = """
    <div id="audio-container">
        <audio id="audio-player-1" controls></audio>
        <audio id="audio-player-2" controls></audio>
    </div>

    <script>
        function checkAudioLoaded() {
            const audio1 = document.getElementById("audio-player-1");
            const audio2 = document.getElementById("audio-player-2");

            let audio1Loaded = false;
            let audio2Loaded = false;

            audio1.addEventListener("loadeddata", () => {
                audio1Loaded = true;
                enableButtonsIfReady();
            });

            audio2.addEventListener("loadeddata", () => {
                audio2Loaded = true;
                enableButtonsIfReady();
            });

            function enableButtonsIfReady() {
                if (audio1Loaded && audio2Loaded) {
                    console.log("✅ Both audio files loaded successfully!");
                    document.getElementById("play-btn-1").disabled = false;
                    document.getElementById("pause-btn-1").disabled = false;
                    document.getElementById("stop-btn-1").disabled = false;
                    document.getElementById("forward-btn-1").disabled = false;
                    document.getElementById("backward-btn-1").disabled = false;

                    document.getElementById("play-btn-2").disabled = false;
                    document.getElementById("pause-btn-2").disabled = false;
                    document.getElementById("stop-btn-2").disabled = false;
                    document.getElementById("forward-btn-2").disabled = false;
                    document.getElementById("backward-btn-2").disabled = false;
                }
            }
        }

        window.onload = checkAudioLoaded;
    </script>
    """

    def load_audio():
        audio_path_1 = "./mock_data/audio/classical_piece_1.wav"
        audio_path_2 = "./mock_data/audio/classical_piece_2.wav"
        return f"<script>checkAudioLoaded();</script>"

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
        
    lyrics_info_text = gr.Markdown("🔒 Lyrics checkbox is currently disabled. (Coming Soon)")

    with gr.Row(elem_id="custom-input-row"):
        with gr.Column(scale=7, min_width=120):
            textbox = gr.Textbox(
                show_label=False,
                placeholder="👉 Enter your prompt and press ENTER"
            )
        with gr.Column(scale=1, min_width=120):
            checkbox = gr.Checkbox(
                label="Lyrics", 
                interactive=False
            )
        with gr.Column(scale=2, min_width=120):
            send_btn = gr.Button(value="Send", variant="primary")
        

    with gr.Row() as extra_button_row:
        # Yonghyun
        surprise_me_btn = gr.Button(value="🔮 Surprise me", interactive=True)
        new_round_btn = gr.Button(value="🎲 New Round", interactive=False)
        regenerate_btn = gr.Button(value="🔄 Regenerate", interactive=False)
        # share_btn = gr.Button(value="📷 Share", interactive=True)

    if add_promotion_links: None
    
    # Declare model_a_state, model_b_state, pair_id_state at the top of `build_single_model_ui`:
    model_a_state = gr.State("")
    model_b_state = gr.State("")
    pair_id_state = gr.State("")
    audio_1_path_state = gr.State("")
    audio_2_path_state = gr.State("")

    
    gr.HTML("""
    <script>
    
    function getAudioById(id) {
        const wrapper = document.getElementById(id);
        return wrapper ? wrapper.querySelector("audio") : null;
    }

    function playAudio(id) {
        const audio = getAudioById(id);
        if (audio) audio.play();
    }

    function pauseAudio(id) {
        const audio = getAudioById(id);
        if (audio) audio.pause();
    }

    function stopAudio(id) {
        const audio = getAudioById(id);
        if (audio) {
            audio.pause();
            audio.currentTime = 0;
        }
    }

    function forwardAudio(id) {
        const audio = getAudioById(id);
        if (audio) audio.currentTime += 10;
    }

    function backwardAudio(id) {
        const audio = getAudioById(id);
        if (audio) audio.currentTime -= 10;
    }
    </script>
    """)

    # button_js_pairs = [
    #     (play_btn1, "playAudio('custom-audio-1')"),
    #     (pause_btn1, "pauseAudio('custom-audio-1')"),
    #     (stop_btn1, "stopAudio('custom-audio-1')"),
    #     (forward_btn1, "forwardAudio('custom-audio-1')"),
    #     (backward_btn1, "backwardAudio('custom-audio-1')"),
    #     (play_btn2, "playAudio('custom-audio-2')"),
    #     (pause_btn2, "pauseAudio('custom-audio-2')"),
    #     (stop_btn2, "stopAudio('custom-audio-2')"),
    #     (forward_btn2, "forwardAudio('custom-audio-2')"),
    #     (backward_btn2, "backwardAudio('custom-audio-2')")
    # ]

    # for button, js_code in button_js_pairs:
    #     button.click(None, None, [], js=f"() => {js_code}")
        
        
    vote_buttons = [a_better_btn, b_better_btn, tie_btn, both_bad_btn]
    
    a_better_btn.click(
        fn=a_better_last_response,
        inputs=[state, model_selector, model_a_state, model_b_state, 
         pair_id_state, audio_id_a_state, audio_id_b_state, 
         textbox, a_listen_time_state, b_listen_time_state],
        outputs=[textbox] + vote_buttons
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
        outputs=[textbox] + vote_buttons
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
        outputs=[textbox] + vote_buttons
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
        outputs=[textbox] + vote_buttons
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

    
    # lyrics_surprise_me_btn.click(
    #     fn=get_random_lyrics_block,
    #     inputs=None,
    #     outputs=[lyric_textbox],
    # )
    
    # Retrieve from existing text-audio pair
    # surprise_me_btn.click(
    #     fn=lambda: "Classical Piano Music",
    #     inputs=None,
    #     outputs=[textbox],
    # )

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
            music_player_1,         # audio 1
            music_player_2,         # audio 2
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


    # surprise_me_btn.click(
    #     lambda: ("./mock_data/audio/classical_piece_1.wav", "./mock_data/audio/classical_piece_2.wav"),
    #     None,
    #     [music_player_1, music_player_2]
    # )

    # new_round_btn.click(
    #     clear_history,
    #     None,
    #     [state, textbox]
    # )
    new_round_btn.click(
        fn=lambda: (
            None,           # state
            "",             # textbox
            None, None,     # music_player_1, music_player_2
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
            gr.update(interactive=True),   # surprise_me_btn
            gr.update(interactive=False)   # regenerate_btn
        ),
        inputs=None,
        outputs=[
            state,
            textbox,
            music_player_1, music_player_2,
            model_a_label, model_a_label,
            model_b_label, model_b_label,
            a_listen_time_state, b_listen_time_state,
            a_start_time_state, b_start_time_state,
            model_a_state, model_b_state, pair_id_state,
            download_file,
            status_text,
            vote_buttons[0], vote_buttons[1], vote_buttons[2], vote_buttons[3],
            send_btn, surprise_me_btn, regenerate_btn
        ]
    )

    # regenerate_btn.click(
    #     regenerate,
    #     state,
    #     [state, textbox]
    # )
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
            gr.update(interactive=False),  # hide voting buttons
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
        fn=regenerate,
        inputs=[textbox],
        outputs=[
            pair_id_state,
            music_player_1,
            music_player_2,
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


    # share_btn.click(
    #     lambda: "Shared successfully! 📤",
    #     None,
    #     [textbox]
    # )
    
    # play_btn1.click(None, None, [], js="""
    # () => {
    #     setTimeout(() => {
    #         const audio = document.querySelector('#custom-audio-1 audio');
    #         if (audio) audio.play();
    #     }, 200);
    # }
    # """)
    # pause_btn1.click(None, None, [], js="() => { const audio = document.querySelector('#custom-audio-1 audio'); if (audio) audio.pause(); }")
    # stop_btn1.click(None, None, [], js="() => { const audio = document.querySelector('#custom-audio-1 audio'); if (audio) { audio.pause(); audio.currentTime = 0; } }")


    # play_btn1.click(
    #     lambda: """
    #         const audioPlayer = document.getElementById("custom-audio-1");
    #         if (audioPlayer) {
    #             audioPlayer.play();
    #         }
    #     """,
    #     inputs=None,
    #     outputs=None
    # )
    
    # Original
    # send_btn.click(
    #     fn=add_text,
    #     inputs=[state, model_selector, textbox],
    #     outputs=[state, music_player_1, music_player_2, textbox]
    # ).then( # Retrieve the specific music 
    #     fn=lambda: (
    #         "./mock_data/audio/classical_piece_1.mp3",
    #         "./mock_data/audio/classical_piece_2.mp3",
    #     ),
    #     inputs=None,
    #     outputs=[music_player_1, music_player_2]
    # ).then( # This will be fixed (Try to make the users can vote after hearing both songs at least @ sconds)
    #     fn=lambda:[gr.update(interactive=True)] * 10,
    #     inputs=None, 
    #     outputs=[play_btn1, pause_btn1, stop_btn1, forward_btn1, backward_btn1,
    #                 play_btn2, pause_btn2, stop_btn2, forward_btn2, backward_btn2]
    # ).then(
    #     fn=lambda:[gr.update(interactive=True)] * 7,
    #     inputs=None,
    #     outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn,
    #                 new_round_btn, regenerate_btn, share_btn])

    # Apr 3 (BACKEND)
    
    send_btn.click(
        fn=lambda prompt: None,
        inputs=[textbox],
        outputs=[],
        js="""
        () => {
            const textbox = document.querySelector('#custom-input-row textarea');
            if (!textbox || textbox.value.trim() === "") {
                alert("⚠️ Please enter a prompt before pressing Send.");
                throw new Error("Prompt is empty");
            }
            return textbox.value;
        }
    """
    ).then(
        fn=lambda: (
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        ),
        inputs=None,
        outputs=[send_btn, surprise_me_btn, new_round_btn]
    ).then(
        fn=call_backend_and_get_music,
        inputs=[textbox],
        outputs=[
            pair_id_state,
            music_player_1,
            music_player_2,
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
        theme=gr.themes.Default(),
        css=block_css,
    ) as demo:
        url_params = gr.JSON(visible=False)

        state, model_selector = build_single_model_ui(models)

        if args.model_list_mode not in ["once", "reload"]:
            raise ValueError(f"Unknown model list mode: {args.model_list_mode}")

        if args.show_terms_of_use:
            load_js = get_window_url_params_with_tos_js
        else:
            load_js = get_window_url_params_js

        demo.load(
            load_demo,
            [url_params],
            [
                state,
                model_selector,
            ],
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
        "--register-api-endpoint-file",
        type=str,
        help="Register API-based model endpoints from a JSON file",
    )
    parser.add_argument(
        "--gradio-auth-path",
        type=str,
        help='Set the gradio authentication file path. The file should contain one or more user:password pairs in this format: "u1:p1,u2:p2,u3:p3"',
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

    # Set global variables
    set_global_vars(args.moderate, args.use_remote_storage)
    # Controller not used
    print(f"ARENA_TYPE: {ARENA_TYPE}") # txt2music-arena
    print(f"register-api-endpoint-file: {args.register_api_endpoint_file}") # None
    models, all_models = [], []
    # models, all_models = get_model_list(
    #     args.controller_url, args.register_api_endpoint_file, ARENA_TYPE
    # )

    # # Set authorization credentials
    auth = None
    # if args.gradio_auth_path is not None:
    #     auth = parse_gradio_auth_creds(args.gradio_auth_path)
    
    # print(f"auth: {auth}") # None
    # print(f"models: {models}") # []

    # Launch the demo
    demo = build_demo(models)
    demo.queue(
        default_concurrency_limit=args.concurrency_count,
        status_update_rate=10,
        api_open=False,
    ).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        max_threads=200,
        auth=auth,
        root_path=args.gradio_root_path,
    )