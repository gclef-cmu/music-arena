"""
The gradio demo server for chatting with a single model.

Debugging Ongoing (Yonghyun)

python -m frontend.gradio_web_server --controller-url http://0.0.0.0:21001 --share
"""

"""
TODO
- Debug the code (Bug after pressing SEND button)
- Connect with the Wayne's backend
- Implement the support for lyrics conditioning on the frontend? The UI components should look like:
    Prompt: text box
    Instrumental-only: check box, checked by default
    Lyrics: text box, prepopulated w/ ghost text that says "Surprise me!", indicating that the system will come up with lyrics when unspecified
   (Professor will incorporate YuE (a recent open weights model w/ lyrics conditioning) into the backend so have something to test it out with.)
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

import gradio as gr
import requests

from functools import partial

from frontend.constants import (
    LOGDIR, # The output dir of log files LOGDIR = os.getenv("LOGDIR", ".")
    WORKER_API_TIMEOUT, # int(os.getenv("FASTCHAT_WORKER_API_TIMEOUT", 100))
    ErrorCode,
    MODERATION_MSG,
    CONVERSATION_LIMIT_MSG,
    RATE_LIMIT_MSG,
    SERVER_ERROR_MSG,
    INPUT_CHAR_LEN_LIMIT,
    CONVERSATION_TURN_LIMIT,
    SESSION_EXPIRATION_TIME,
    SURVEY_LINK,
)

from model.model_adapter import get_conversation_template
from model.model_registry import get_model_info, model_info

#MUSICARENA (Previous version; TODO) 
from frontend.gradio_global_state import (
    Context, # music_models
    ArenaType, # TEXT2MUSIC
    RepoChatContext,
)

'''
#Yonghyun
[gradio_global_state]

1. Context (Dataclass)
- A structure that manages various categories of Large Language Models (LLMs).
- Defined using the `dataclass` decorator with the following attributes:

| **Attribute**         | **Description**                                    |
|-----------------------|----------------------------------------------------|
| `music_models`        | List of selected music generation models           |
| `all_music_models`    | List of all available music generation models      |
| `models`              | List of selected models (all categories combined)  |
| `all_models`          | List of all available models                       |
| `arena_type`          | Currently selected arena type (default: `TEXT`)    |

2. ArenaType (Constant Class)
This class defines constants for various **arena types**.

| **Constant**         | **Description**                            |
|----------------------|--------------------------------------------|
| TXT2MUSIC            | Text-to-music generation model arena       |

'''

# MUSICARENA (Previous version; TODO)
from frontend.api_provider import get_music_api_provider
'''
#Yonghyun
[fastchat.serve.txt2music.music_api_provider]

1. MusicResponseOutput (Dataclass)
- A simple data container to store the API's response.
- Fields:
    - `audio_data`: Contains the generated audio data as `bytes`.
    - `error`: Describes any error encountered during the process (default: `None`).
    
2. BaseMusicAPIProvider (Abstract Base Class)
- Serves as a blueprint for building custom API providers.
- Key methods:
    - `validate_config()`: Abstract method that ensures essential configuration keys are present.
    - `log_gen_params()`: Logs request parameters for debugging.

3. CustomServerMusicAPIProvider (Concrete Provider Class)
- Implements music generation logic using an external HTTP-based Flask server.
- Key methods:
    - `validate_config()`: Ensures required config keys (`base_url`, `check_interval`, `max_wait_time`) are provided.
    - `generated_music()`: Core method that:
        1. Submits a music generation request.
        2. Continuously polls the server to check the job status.
        3. If successful, fetches and returns the generated audio data.

4. get_music_api_provider() (Factory Function)
- Dynamically creates a 3. `CustomServerMusicAPIProvider` instance.
- Combines default values (like `base_url`) with user-provided configurations.

**Default Configuration:**
- `base_url`: `"http://localhost:5000"`  
- `check_interval`: `1.0` second  
- `max_wait_time`: `60.0` seconds  
'''

from frontend.remote_logger import (
    get_remote_logger,
    get_repochat_remote_logger,
)
from frontend.utils import (
    build_logger,
    get_window_url_params_js,
    get_window_url_params_with_tos_js,
    moderation_filter,
    parse_gradio_auth_creds,
    save_music_files,
    get_music_directory_name_and_remote_storage_flag,
)

# Yonghyun - Tracking the audio listening time
a_start_time = None
b_start_time = None
a_listen_time = 0
b_listen_time = 0

def on_play_a():
    global a_start_time
    a_start_time = time.time()
    print(f"a_start_time: {a_start_time}")

def on_play_b():
    global b_start_time
    b_start_time = time.time()
    print(f"b_start_time: {b_start_time}")


def on_pause_a():
    global a_start_time, a_listen_time
    if a_start_time:
        a_listen_time += time.time() - a_start_time
        print(f"a_listen_time: {a_listen_time}")
        a_start_time = None

def on_pause_b():
    global b_start_time, b_listen_time
    if b_start_time:
        b_listen_time += time.time() - b_start_time
        print(f"b_listen_time: {a_listen_time}")
        b_start_time = None 

logger = build_logger("gradio_web_server", "gradio_web_server.log")

headers = {"User-Agent": "Music Arena Client"}

no_change_btn = gr.Button()
enable_btn = gr.Button(interactive=True, visible=True)
disable_btn = gr.Button(interactive=False)
invisible_btn = gr.Button(interactive=False, visible=False)

controller_url = None
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

# JSON file format of API-based models:
# {
#   "gpt-3.5-turbo": {
#     "model_name": "gpt-3.5-turbo",
#     "api_type": "openai",
#     "api_base": "https://api.openai.com/v1",
#     "api_key": "sk-******",
#     "anony_only": false
#   }
# }
#
#  - "api_type" can be one of the following: openai, anthropic, gemini, or mistral. For custom APIs, add a new type and implement it accordingly.
#  - "anony_only" indicates whether to display this model in anonymous mode only.

api_endpoint_info = {}

ARENA_TYPE = ArenaType.TXT2MUSIC #ArenaType.TXT2MUSIC # ArenaType.TEXT

# (Yonghyun) Class for managing chatting session
class State:
    def __init__(self, model_name, arena_type=ARENA_TYPE, metadata=None):
        self.conv = get_conversation_template(model_name) # 현재 체팅 세션의 대화 기록 저장
        self.conv_id = uuid.uuid4().hex
        self.skip_next = False
        self.model_name = model_name
        self.oai_thread_id = None
        self.arena_type = arena_type
        self.repochat_context = RepoChatContext()
        self.ans_models = []
        self.router_outputs = []
        # NOTE(chris): This could be sort of a hack since it assumes the user only uploads one image. If they can upload multiple, we should store a list of image hashes.
        self.has_csam_image = False

        self.regen_support = True
        if "browsing" in model_name:
            self.regen_support = False
        #self.init_system_prompt(self.conv)

    def update_ans_models(self, ans: str) -> None:
        self.ans_models.append(ans)

    def update_router_outputs(self, outputs: Dict[str, float]) -> None:
        self.router_outputs.append(outputs)

    # def init_system_prompt(self, conv):
    #     system_prompt = conv.get_system_message(is_vision=self.is_vision)
    #     if len(system_prompt) == 0:
    #         return
    #     current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    #     system_prompt = system_prompt.replace("{{currentDateTime}}", current_date)

    #     current_date_v2 = datetime.datetime.now().strftime("%d %b %Y")
    #     system_prompt = system_prompt.replace("{{currentDateTimev2}}", current_date_v2)

    #     current_date_v3 = datetime.datetime.now().strftime("%B %Y")
    #     system_prompt = system_prompt.replace("{{currentDateTimev3}}", current_date_v3)
    #     conv.set_system_message(system_prompt)

    # def to_gradio_chatbot(self):
    #     return self.conv.to_gradio_chatbot()

    # def dict(self):
    #     base = self.conv.dict()
    #     base.update(
    #         {
    #             "conv_id": self.conv_id,
    #             "model_name": self.model_name,
    #         }
    #     )

    #     if self.ans_models:
    #         base.update(
    #             {
    #                 "ans_models": self.ans_models,
    #             }
    #         )

    #     if self.router_outputs:
    #         base.update(
    #             {
    #                 "router_outputs": self.router_outputs,
    #             }
    #         )

    #     return base

# BACKEND
def generate_audio_pair(prompt: str, user_id: str):
    payload = {
        "prompt": prompt,
        "user_id": user_id,
        "seed": 42
    }

    response = requests.post("http://localhost:12000/generate_audio_pair", json=payload)

    if response.status_code == 200:
        return response.json()  # AudioPairResponse Format
    else:
        print("Error:", response.status_code, response.text)
        
def send_vote(pair_id: str, user_id: str, winning_model: str):
    payload = {
        "pair_id": pair_id,
        "user_id": user_id,
        "winning_model": winning_model
    }

    response = requests.post("http://localhost:12000/record_vote", json=payload)

    if response.ok:
        print("Vote recorded!")
    else:
        print("Failed to record vote:", response.status_code, response.text)

def call_backend_and_get_music(prompt, user_id="test_user", seed=42):
    payload = {
        "prompt": prompt,
        "user_id": user_id,
        "seed": seed
    }

    try:
        res = requests.post("http://localhost:12000/generate_audio_pair", json=payload)
        res.raise_for_status()
        response_json = res.json()

        audio_1_base64 = response_json["audioItems"][0]["audioDataBase64"]
        audio_2_base64 = response_json["audioItems"][1]["audioDataBase64"]
        model_a = response_json["audioItems"][0]["model"]
        model_b = response_json["audioItems"][1]["model"]
        pair_id = response_json["pairId"]

        return (
            pair_id,
            audio_1_base64,
            audio_2_base64,
            f"**Model A: {model_a}**",
            f"**Model B: {model_b}**"
        )

    except Exception as e:
        print(f"Error calling backend: {e}")
        return None, None, None, "Model A: Error", "Model B: Error"


def set_global_vars(
    controller_url_,
    enable_moderation_,
    use_remote_storage_,
):
    global controller_url, enable_moderation, use_remote_storage
    controller_url = controller_url_
    enable_moderation = enable_moderation_
    use_remote_storage = use_remote_storage_


def get_conv_log_filename(arena_type=ARENA_TYPE, has_csam_image=False):
    t = datetime.datetime.now()
    conv_log_filename = f"{t.year}-{t.month:02d}-{t.day:02d}-conv.json"
    name = os.path.join(LOGDIR, f"txt2music-{conv_log_filename}")
    
    return name


def get_model_list(controller_url, register_api_endpoint_file, arena_type):
    global api_endpoint_info

    # Add models from the controller
    if controller_url:
        print(f"controller_url: {controller_url}") # https://localhost:21001
        ret = requests.post(controller_url + "/refresh_all_workers")
        print(f"ret (1): {ret}") # <Response [200]>
        assert ret.status_code == 200

        ret = requests.post(controller_url + "/list_multimodal_models")
        models = ret.json()["models"]
        print(f"ret (2): {ret}") # <Response [200]>
        print(f"models: {models}") # []            

    else:
        models = []

    # Add models from the API providers
    if register_api_endpoint_file:
        api_endpoint_info = json.load(open(register_api_endpoint_file))
        for mdl, mdl_dict in api_endpoint_info.items():
            mdl_vision = mdl_dict.get("vision-arena", False)
            mdl_text = mdl_dict.get("text-arena", True)
            mdl_txt2img = mdl_dict.get("txt2img-arena", False)
            mdl_txt2music = mdl_dict.get("txt2music-arena", False) # Yonghyun
            if arena_type == ArenaType.VISION and mdl_vision:
                models.append(mdl)
            if arena_type == ArenaType.TEXT and mdl_text:
                models.append(mdl)
            if arena_type == ArenaType.TXT2IMG and mdl_txt2img:
                models.append(mdl)
            if arena_type == ArenaType.TXT2MUSIC and mdl_txt2music:
                models.append(mdl)

    # Remove anonymous models
    models = list(set(models))
    visible_models = models.copy()
    for mdl in models:
        if mdl not in api_endpoint_info:
            continue
        mdl_dict = api_endpoint_info[mdl]
        if mdl_dict["anony_only"]:
            visible_models.remove(mdl)

    # Sort models and add descriptions
    priority = {k: f"___{i:03d}" for i, k in enumerate(model_info)}
    models.sort(key=lambda x: priority.get(x, x))
    visible_models.sort(key=lambda x: priority.get(x, x))
    logger.info(f"(get_model_list) All models: {models}")
    logger.info(f"(get_model_list) Visible models: {visible_models}")
    return visible_models, models


def load_demo_single(context: Context, query_params):
    # default to text models
    # logger.info(f"context: {context}")
    if isinstance(context, list):
        logger.warning("[gradio_web_server.py] ⚠️ Context 객체가 아니라 리스트로 전달됨. 기본 Context 사용")
        context = Context()
        
    models = context.music_models # gradio_global_state

    selected_model = models[0] if len(models) > 0 else ""
    if "model" in query_params:
        model = query_params["model"]
        if model in models:
            selected_model = model

    all_models = context.models

    if selected_model not in all_models:
        selected_model = all_models[0] if all_models else ""
    
    dropdown_update = gr.Dropdown(
        choices=all_models, value=selected_model, visible=True
    )
    state = None
    return [state, dropdown_update]


def load_demo(url_params, request: gr.Request):
    global models

    print(f"load_demo executed: {load_demo}")
    ip = get_ip(request)
    logger.info(f"load_demo. ip: {ip}. params: {url_params}") # ip: 143.215.16.196. params: {}

    logger.info(f"args.model_list_mode: {args.model_list_mode}") # 'once'
    if args.model_list_mode == "reload":
        models, all_models = get_model_list(
            controller_url, args.register_api_endpoint_file, ARENA_TYPE
        )

    return load_demo_single(models, url_params)

"""
(Revised vote_last_response)
Records votes on the generated model's response.
This function is called when a user clicks a button in the Gradio web interface.
It logs the user's feedback and saves it in the log file.

get_conv_log_filename() → Generates a filename for saving the chat conversation log.

'tstamp': Current timestamp
'type': Vote type ('a_better', 'b_better', 'tie', 'both_bad')
'model': Selected model name
'model_a': Name of model A
'model_b': Name of model B
'a_listen_time': Total time the user listened to Model A's output
'b_listen_time': Total time the user listened to Model B's output
'state': Current state object converted to a dictionary (state.dict())
'ip': User's IP address
"""

def vote_last_response(state, vote_type, model_selector, request: gr.Request, model_a='musicgen', model_b='riffusionv1'):
    
    global a_listen_time, b_listen_time
    
    ip = get_ip(request)
    
    filename = get_conv_log_filename()
    #print(f"[gradio_web_server.py vote_last_response()] filename: {filename}") #  ./txt2music-2025-03-12-conv.json
    
    if "llava" in model_selector:
        filename = filename.replace("2024", "vision-tmp-2024")

    with open(filename, "a") as fout: 
        # Append mode - Adds content to the existing file
        # Converts vote data to JSON format and appends it to the file
        data = {
            "tstamp": round(time.time(), 4),
            "type": vote_type,
            "model": model_selector,
            'model_a': model_a,
            'model_b': model_b,
            'a_listen_time': round(a_listen_time, 2),
            'b_listen_time': round(b_listen_time, 2),
            "state": state.dict(),
            "ip": ip,
        }
        fout.write(json.dumps(data) + "\n") 
    get_remote_logger().log(data) # # Sends the log data remotely for additional monitoring

    
def a_better_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"a is better. ip: {ip}")
    print(f"DEBUG: a_better_last_response")
    vote_last_response(state, "a_better", model_selector, request)

    return (
        "",
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False), 
        gr.update(interactive=False),
    )

def b_better_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"b is better. ip: {ip}")
    print(f"DEBUG: b_better_last_response")
    vote_last_response(state, "b_better", model_selector, request)
    return ("",) + (disable_btn,) * 4

def tie_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"tie. ip: {ip}")
    print(f"DEBUG: tie_last_response")
    vote_last_response(state, "tie", model_selector, request)
    return ("",) + (disable_btn,) * 4 

def both_bad_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"both are bad ip: {ip}")
    print(f"DEBUG: both_bad_last_response")
    vote_last_response(state, "both_bad", model_selector, request)
    return ("",) + (disable_btn,) * 4


def upvote_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"upvote. ip: {ip}")
    vote_last_response(state, "upvote", model_selector, request)
    return ("",) + (disable_btn,) * 3


def downvote_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"downvote. ip: {ip}")
    vote_last_response(state, "downvote", model_selector, request)
    return ("",) + (disable_btn,) * 3


def flag_last_response(state, model_selector, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"flag. ip: {ip}")
    vote_last_response(state, "flag", model_selector, request)
    return ("",) + (disable_btn,) * 3


def regenerate(state, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"regenerate. ip: {ip}")
    if not state.regen_support:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "", None) + (no_change_btn,) * 5
    state.conv.update_last_message(None)
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


def clear_history(request: gr.Request):
    ip = get_ip(request)
    logger.info(f"clear_history. ip: {ip}")
    state = None
    return (state, [], "") + (disable_btn,) * 5


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


# Convey the user's text input to the AI Model
def add_text(state, model_selector, text, request: gr.Request):
    ip = get_ip(request)
    logger.info(f"add_text. ip: {ip}. len: {len(text)}")

    if state is None:
        state = State(model_selector)

    if len(text) <= 0:
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), "", None) + (no_change_btn,) * 5

    all_conv_text = state.conv.get_prompt()
    all_conv_text = all_conv_text[-2000:] + "\nuser: " + text
    flagged = moderation_filter(all_conv_text, [state.model_name])
    # flagged = moderation_filter(text, [state.model_name])
    if flagged:
        logger.info(f"violate moderation. ip: {ip}. text: {text}")
        # overwrite the original text
        text = MODERATION_MSG

    if (len(state.conv.messages) - state.conv.offset) // 2 >= CONVERSATION_TURN_LIMIT:
        logger.info(f"conversation turn limit. ip: {ip}. text: {text}")
        state.skip_next = True
        return (state, state.to_gradio_chatbot(), CONVERSATION_LIMIT_MSG, None) + (
            no_change_btn,
        ) * 5

    text = text[:INPUT_CHAR_LEN_LIMIT]  # Hard cut-off
    state.conv.append_message(state.conv.roles[0], text)
    state.conv.append_message(state.conv.roles[1], None)
    return (state, state.to_gradio_chatbot(), "") + (disable_btn,) * 5


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


# MUSIC_DB_PATH = "music-arena/mock_data/audio/"
# MUSIC_MAP_FILE = "music-arena/mock_data/audio/music_db.json"

# def load_music_db():
#     '''Load a predefiend music database from a JSON file.'''
#     if os.path.exists(MUSIC_MAP_FILE):
#         with open(MUSIC_MAP_FILE, "r") as f:
#             return json.load(f)
#     return {}


# def find_music_file(user_text):
#     '''Match user input with a music file in the database.'''
#     MUSIC_DB = load_music_db()
#     for keyword, filename in MUSIC_DB.items():
#         if keyword.lower() in user_text.lower():
#             file_path = os.path.join(MUSIC_DB_PATH, filename)
#             if os.path.exists(file_path):
#                 return file_path
#             else:
#                 logger.warning(f"⚠️ Music file '{file_path}' doens't exist.")
#     return None


def bot_response(
    state: State,
    temperature,
    top_p,
    max_new_tokens,
    request: gr.Request,
    apply_rate_limit=True,
    use_recommended_config=False,
):
    ip = get_ip(request)
    logger.info(f"bot_response. ip: {ip}")
    start_tstamp = time.time()
    temperature = float(temperature)
    top_p = float(top_p)
    max_new_tokens = int(max_new_tokens)

    if state.skip_next:
        # This generate call is skipped due to invalid inputs
        state.skip_next = False
        yield (state, state.to_gradio_chatbot(), None) + (no_change_btn,) * 5
        return

    if apply_rate_limit:
        ret = is_limit_reached(state.model_name, ip)
        if ret is not None and ret["is_limit_reached"]:
            error_msg = RATE_LIMIT_MSG + "\n\n" + ret["reason"]
            logger.info(f"rate limit reached. ip: {ip}. error_msg: {ret['reason']}")
            state.conv.update_last_message(error_msg)
            yield (state, state.to_gradio_chatbot(), None) + (no_change_btn,) * 5
            return

    conv, model_name = state.conv, state.model_name
    model_api_dict = (
        api_endpoint_info[model_name] if model_name in api_endpoint_info else None
    )

    # TODO Wayne Need to figure out --register-api-endpoint-file argument and add music models
    api_provider = get_music_api_provider(
        model_key=model_api_dict["model_name"],
    )

    # TODO(CHRIS): make seed tunable.
    seed = random.randint(0, 2**31 - 1)

    start_tstamp = time.time()
    try:
        music_response = api_provider.generate_music(state.prompt, seed=seed)
        state.generated_music = music_response.audio_data
    except requests.exceptions.RequestException as e:
        state.generated_music = None
        yield [state, state.to_gradio_chatbot(), None] + [
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        ]
        return

    api_provider = get_api_provider(
        model_key=model_api_dict["model_name"],
        api_key=model_api_dict["api_key"],
    )

    # TODO(CHRIS): make seed tunable.
    seed = random.randint(0, 2**31 - 1)

    start_tstamp = time.time()
    try:
        image_response = api_provider.generate_image(state.prompt)
        image_response.image = crop_image(image_response.image, ratio=(16, 9))
        state.generated_image = image_response.image
        state.has_nsfw_image = image_response.moderation_flagged
    except requests.exceptions.RequestException as e:
        state.generated_image = None
        yield [state, state.to_gradio_chatbot(), None] + [
            disable_btn,
            disable_btn,
            disable_btn,
            enable_btn,
            enable_btn,
        ]
        return

    finish_tstamp = time.time()

    print(F"state.arena_type: {state.arena_type}")
    print(F"ArenaType.TXT2MUSIC: {ArenaType.TXT2MUSIC}")
    
    if state.generated_music is not None:
        music_to_save = [state.generated_music]
    else:
        music_to_save = []

    if len(music_to_save) > 0:
        (
            music_directory_name,
            remote_storage_flag,
        ) = get_music_directory_name_and_remote_storage_flag(
            use_remote_storage, state.arena_type
        )
        filenames = save_music_files(
            music_to_save, music_directory_name, remote_storage_flag
        )
        if state.arena_type == ArenaType.TXT2MUSIC:
            state.music_filenames = filenames

    filename = get_conv_log_filename(state.arena_type, state.has_csam_image)

    data = {
        "tstamp": round(finish_tstamp, 4),
        "type": "chat",
        "model": model_name,
        "start": round(start_tstamp, 4),
        "finish": round(finish_tstamp, 4),
        "state": state.dict(),
        "ip": get_ip(request),
    }

    # Note: upstream expects a generator element so we must yield here instead of returning
    returned_music = state.generated_music
    yield [state, state.to_gradio_chatbot(), returned_music] + [
        disable_btn,
        disable_btn,
        disable_btn,
        enable_btn,
        enable_btn,
    ]
    return


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
            with gr.Accordion(
                f"🔍 Expand to see the descriptions of 2 models", # f"🔍 Expand to see the descriptions of {len(models)} models"
                open=False,
            ):
                model_description_md = get_model_description_md(models)
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
                    music_player_1 = gr.Audio(label="Generated Music 1", interactive=False, 
                                                elem_id="custom-audio-1", show_download_button=False,
                                                show_share_button=False, visible=True)
                    # music_player_1.play(on_play_a)
                    # music_player_1.pause(on_pause_a)
                    # music_player_1.stop(on_pause_a)
                    with gr.Row():
                        play_btn1 = gr.Button("▶️ Play", elem_id="play_btn_1", interactive=False)
                        pause_btn1 = gr.Button("⏸️ Pause", elem_id="pause_btn_1", interactive=False)
                        stop_btn1 = gr.Button("⏹️ Stop", elem_id="stop_btn_1", interactive=False)
                        forward_btn1 = gr.Button("⏩ +10s", elem_id="forward_btn_1", interactive=False)
                        backward_btn1 = gr.Button("⏪ -10s", elem_id="backward_btn_1", interactive=False)

                # Right Audio Player w/ Controls
                with gr.Column():
                    music_player_2 = gr.Audio(label="Generated Music 2", interactive=False, 
                                              elem_id="custom-audio-2", show_download_button=False,
                                              show_share_button=False, visible=True)
                    music_player_2.play(on_play_b)
                    music_player_2.pause(on_pause_b)
                    music_player_2.stop(on_pause_b)
                    with gr.Row():
                        play_btn2 = gr.Button("▶️ Play", elem_id="play_btn_2", interactive=False)
                        pause_btn2 = gr.Button("⏸️ Pause", elem_id="pause_btn_2", interactive=False)
                        stop_btn2 = gr.Button("⏹️ Stop", elem_id="stop_btn_2", interactive=False)
                        forward_btn2 = gr.Button("⏩ +10s", elem_id="forward_btn_2", interactive=False)
                        backward_btn2 = gr.Button("⏪ -10s", elem_id="backward_btn_2", interactive=False)

            with gr.Row():
                model_a_label = gr.Markdown("**Model A: Unknown**", visible=False)
                model_b_label = gr.Markdown("**Model B: Unknown**", visible=False)

                gr.HTML("""
                <style>
                #lyrics_row {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-bottom: 8px;
                }
                </style>
                <script>
                document.getElementById("play_btn_1").onclick = () => {
                    const audio = document.querySelector("#custom-audio-1 audio");
                    if (audio) audio.play();
                };
                document.getElementById("pause_btn_1").onclick = () => {
                    const audio = document.querySelector("#custom-audio-1 audio");
                    if (audio) audio.pause();
                };
                document.getElementById("stop_btn_1").onclick = () => {
                    const audio = document.querySelector("#custom-audio-1 audio");
                    if (audio) {
                        audio.pause();
                        audio.currentTime = 0;
                    }
                };
                </script>
                """)
          
        # Ongoing
        gr.HTML("""
        <script>
        setTimeout(() => {
            const audio1 = document.querySelector('#custom-audio-1 audio');
            console.log("Audio 1 exists?", !!audio1);
        }, 500);
        </script>
        """)   
           
    with gr.Row() as button_row:
        # Yonghyun
        a_better_btn = gr.Button(value="👈 A is better", interactive=False)
        b_better_btn = gr.Button(value="👉 B is better", interactive=False)
        tie_btn = gr.Button(value="🤝 Tie", interactive=False)
        both_bad_btn = gr.Button(value="👎 Both are bad", interactive=False)
        # upvote_btn = gr.Button(value="👍  Upvote", interactive=False)
        # downvote_btn = gr.Button(value="👎  Downvote", interactive=False)
        # flag_btn = gr.Button(value="⚠️  Flag", interactive=False)
        # regenerate_btn = gr.Button(value="🔄  Regenerate", interactive=False)
        # clear_btn = gr.Button(value="🗑️  Clear history", interactive=False)
        
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

    with gr.Row(elem_id="lyrics_row"):
        with gr.Column(scale=1, min_width=120):
            checkbox = gr.Checkbox(label="Lyric Music?")
        with gr.Column(scale=2, min_width=150):
            lyrics_surprise_me_btn = gr.Button(
                value="🔮 Surprise me", 
                visible=False,
                interactive=True
            )
        with gr.Column(scale=6, min_width=300):
            textbox = gr.Textbox(
                show_label=False,
                placeholder="🎤 Write your own lyrics!",
                elem_id="input_box",
                visible=False,
                interactive=True
            )

        checkbox.change(
            fn=toggle_lyrics_box,
            inputs=checkbox,
            outputs=[textbox, lyrics_surprise_me_btn],
        )
    
    with gr.Row():
        textbox = gr.Textbox(
            show_label=False,
            placeholder="👉 Enter your prompt and press ENTER",
            elem_id="input_box",
        )
        send_btn = gr.Button(value="Send", variant="primary", scale=0)
        

    with gr.Row() as extra_button_row:
        # Yonghyun
        surprise_me_btn = gr.Button(value="🔮 Surprise me", interactive=True)
        new_round_btn = gr.Button(value="🎲 New Round", interactive=False)
        regenerate_btn = gr.Button(value="🔄 Regenerate", interactive=False)
        share_btn = gr.Button(value="📷 Share", interactive=True)

    # Accordion is a layout element which can be toggled to show/hide the contained content. (https://www.gradio.app/docs/gradio/accordion)
    with gr.Accordion("Parameters", open=False) as parameter_row:
        temperature = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.7,
            step=0.1,
            interactive=True,
            label="Temperature",
        )
        top_p = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=1.0,
            step=0.1,
            interactive=True,
            label="Top P",
        )
        max_output_tokens = gr.Slider(
            minimum=16,
            maximum=4096,
            value=2048,
            step=64,
            interactive=True,
            label="Max output tokens",
        )

    if add_promotion_links: None
    
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

    button_js_pairs = [
        (play_btn1, "playAudio('custom-audio-1')"),
        (pause_btn1, "pauseAudio('custom-audio-1')"),
        (stop_btn1, "stopAudio('custom-audio-1')"),
        (forward_btn1, "forwardAudio('custom-audio-1')"),
        (backward_btn1, "backwardAudio('custom-audio-1')"),
        (play_btn2, "playAudio('custom-audio-2')"),
        (pause_btn2, "pauseAudio('custom-audio-2')"),
        (stop_btn2, "stopAudio('custom-audio-2')"),
        (forward_btn2, "forwardAudio('custom-audio-2')"),
        (backward_btn2, "backwardAudio('custom-audio-2')")
    ]

    for button, js_code in button_js_pairs:
        button.click(None, None, [], js=f"() => {js_code}")
        
        
        
    vote_buttons = [a_better_btn, b_better_btn, tie_btn, both_bad_btn]

    a_better_btn.click(
        a_better_last_response,
        [state, model_selector],
        [textbox] + vote_buttons
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda: (
            gr.update(value="**Model A: MusicGen medium**", visible=True), 
            gr.update(value="**Model B: Riffusion v1**", visible=True)
        ),
        None,
        [model_a_label, model_b_label]
    )

    b_better_btn.click(
        b_better_last_response,
        [state, model_selector],
        [textbox] + vote_buttons
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda: (
            gr.update(value="**Model A: MusicGen**", visible=True), 
            gr.update(value="**Model B: Riffusion**", visible=True)
        ),
        None,
        [model_a_label, model_b_label]
    )

    tie_btn.click(
        tie_last_response,
        [state, model_selector],
        [textbox] + vote_buttons
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda: (
            gr.update(value="**Model A: MusicGen medium**", visible=True), 
            gr.update(value="**Model B: Riffusion v1**", visible=True)
        ),
        None,
        [model_a_label, model_b_label]
    )

    both_bad_btn.click(
        both_bad_last_response,
        [state, model_selector],
        [textbox] + vote_buttons
    ).then(
        lambda: "Press \"🎲 New Round\" to start over👇 (Note: Your vote shapes the leaderboard, please vote RESPONSIBLY!)",
        None,
        [textbox]
    ).then(
        lambda: [gr.update(interactive=False)] * 4,
        None,
        vote_buttons
    ).then( 
        lambda: (
            gr.update(value="**Model A: MusicGen medium**", visible=True), 
            gr.update(value="**Model B: Riffusion v1**", visible=True)
        ),
        None,
        [model_a_label, model_b_label]
    )

    surprise_me_btn.click(
        lambda: ("./mock_data/audio/classical_piece_1.wav", "./mock_data/audio/classical_piece_2.wav"),
        None,
        [music_player_1, music_player_2]
    )

    new_round_btn.click(
        clear_history,
        None,
        [state, textbox]
    )

    regenerate_btn.click(
        regenerate,
        state,
        [state, textbox]
    ).then(
        bot_response,
        [state, temperature, top_p, max_output_tokens],
        [state]
    )

    share_btn.click(
        lambda: "Shared successfully! 📤",
        None,
        [textbox]
    )
    
    play_btn1.click(None, None, [], js="""
    () => {
        setTimeout(() => {
            const audio = document.querySelector('#custom-audio-1 audio');
            if (audio) audio.play();
        }, 200);
    }
    """)
    pause_btn1.click(None, None, [], js="() => { const audio = document.querySelector('#custom-audio-1 audio'); if (audio) audio.pause(); }")
    stop_btn1.click(None, None, [], js="() => { const audio = document.querySelector('#custom-audio-1 audio'); if (audio) { audio.pause(); audio.currentTime = 0; } }")


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
    send_btn.click(
        fn=add_text,
        inputs=[state, model_selector, textbox],
        outputs=[state, music_player_1, music_player_2, textbox]
    ).then( # Retrieve the specific music 
        fn=lambda: (
            "./mock_data/audio/classical_piece_1.mp3",
            "./mock_data/audio/classical_piece_2.mp3",
        ),
        inputs=None,
        outputs=[music_player_1, music_player_2]
    ).then( # This will be fixed (Try to make the users can vote after hearing both songs at least @ sconds)
        fn=lambda:[gr.update(interactive=True)] * 10,
        inputs=None, 
        outputs=[play_btn1, pause_btn1, stop_btn1, forward_btn1, backward_btn1,
                    play_btn2, pause_btn2, stop_btn2, forward_btn2, backward_btn2]
    ).then(
        fn=lambda:[gr.update(interactive=True)] * 7,
        inputs=None,
        outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn,
                    new_round_btn, regenerate_btn, share_btn])

    # # BACKEND
    # send_btn.click(
    #     fn=lambda prompt: call_backend_and_get_music(prompt),
    #     inputs=[textbox],
    #     outputs=[
    #         gr.State(),         # pair_id
    #         music_player_1,     # audioDataBase64 -> decoded
    #         music_player_2,
    #         model_a_label,
    #         model_b_label
    #     ]
    # )

    
    # send_btn.click(
    #     fn=add_text,
    #     inputs=[state, model_selector, textbox],
    #     outputs=[state, textbox, textbox, textbox]
    # ).then(
    #     fn=lambda prompt: call_backend_and_get_music(prompt),
    #     inputs=[textbox],
    #     outputs=[
    #         gr.State(),
    #         music_player_1,
    #         music_player_2,
    #         model_a_label,
    #         model_b_label
    #     ]
    # ).then(
    #     fn=lambda: [gr.update(interactive=True)] * 10,
    #     inputs=None,
    #     outputs=[play_btn1, pause_btn1, stop_btn1, forward_btn1, backward_btn1,
    #             play_btn2, pause_btn2, stop_btn2, forward_btn2, backward_btn2]
    # ).then(
    #     fn=lambda: [gr.update(interactive=True)] * 7,
    #     inputs=None,
    #     outputs=[a_better_btn, b_better_btn, tie_btn, both_bad_btn,
    #             new_round_btn, regenerate_btn, share_btn]
    # )


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
    set_global_vars(args.controller_url, args.moderate, args.use_remote_storage)
    print(f"args.controller_url: {args.controller_url}") # http://localhost:21001
    print(f"ARENA_TYPE: {ARENA_TYPE}") # txt2music-arena
    print(f"register-api-endpoint-file: {args.register_api_endpoint_file}") # None
    models, all_models = get_model_list(
        args.controller_url, args.register_api_endpoint_file, ARENA_TYPE
    )

    # Set authorization credentials
    auth = None
    if args.gradio_auth_path is not None:
        auth = parse_gradio_auth_creds(args.gradio_auth_path)
    
    print(f"auth: {auth}") # None
    print(f"models: {models}") # []

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