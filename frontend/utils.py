"""
Common utilities. [Source] https://github.com/lmarena/FastChat-dev/blob/yonghyun/txt2music-dev/fastchat/utils.py
"""

from asyncio import AbstractEventLoop
from io import BytesIO
import base64
import json
import logging
import logging.handlers
import os
import platform
import sys
import time
from typing import AsyncGenerator, Generator
import warnings

import requests

from constants import LOGDIR
from gradio_global_state import ArenaType

handler = None
visited_loggers = set()

vote_convert_js = """
function (a, b, c, d) {
    const isTxt2Img = window.activeTab === 'txt2img';
    const eventName = isTxt2Img ? 'conversion_event_txt2img_vote' : 'conversion_event_default';
    return getRecaptchaToken('submit').then((token) => {
        if (typeof gtag === 'function') {
            gtag('event', eventName, {
                'event_timeout': 2000,
            });
        }
        return [a, b, c, d, token];
    });
}
"""

# set a variable globally
set_tab_chat_js = """
function (a){
    window.activeTab = "chat";
    return [a]
}
"""
set_tab_repochat_js = """
    function (a){
    window.activeTab = "repochat";
    return [a]
    }
"""
set_tab_txt2img_js = """
    function (a){
    window.activeTab = "txt2img";
    return [a]
    }
"""


def build_logger(logger_name, logger_filename):
    global handler

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the format of root handlers
    if not logging.getLogger().handlers:
        if sys.version_info[1] >= 9:
            # This is for windows
            logging.basicConfig(level=logging.INFO, encoding="utf-8")
        else:
            if platform.system() == "Windows":
                warnings.warn(
                    "If you are running on Windows, "
                    "we recommend you use Python >= 3.9 for UTF-8 encoding."
                )
            logging.basicConfig(level=logging.INFO)
    logging.getLogger().handlers[0].setFormatter(formatter)

    # Redirect stdout and stderr to loggers
    stdout_logger = logging.getLogger("stdout")
    stdout_logger.setLevel(logging.INFO)
    sl = StreamToLogger(stdout_logger, logging.INFO)
    sys.stdout = sl

    stderr_logger = logging.getLogger("stderr")
    stderr_logger.setLevel(logging.ERROR)
    sl = StreamToLogger(stderr_logger, logging.ERROR)
    sys.stderr = sl

    # Get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Avoid httpx flooding POST logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # if LOGDIR is empty, then don't try output log to local file
    if LOGDIR != "":
        os.makedirs(LOGDIR, exist_ok=True)
        filename = os.path.join(LOGDIR, logger_filename)
        handler = logging.handlers.TimedRotatingFileHandler(
            filename, when="D", utc=True, encoding="utf-8"
        )
        handler.setFormatter(formatter)

        for l in [stdout_logger, stderr_logger, logger]:
            if l in visited_loggers:
                continue
            visited_loggers.add(l)
            l.addHandler(handler)

    return logger


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.terminal = sys.stdout
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def __getattr__(self, attr):
        return getattr(self.terminal, attr)

    def write(self, buf):
        temp_linebuf = self.linebuf + buf
        self.linebuf = ""
        for line in temp_linebuf.splitlines(True):
            # From the io.TextIOWrapper docs:
            #   On output, if newline is None, any '\n' characters written
            #   are translated to the system default line separator.
            # By default sys.stdout.write() expects '\n' newlines and then
            # translates them so this is still cross platform.
            if line[-1] == "\n":
                encoded_message = line.encode("utf-8", "ignore").decode("utf-8")
                self.logger.log(self.log_level, encoded_message.rstrip())
            else:
                self.linebuf += line

    def flush(self):
        if self.linebuf != "":
            encoded_message = self.linebuf.encode("utf-8", "ignore").decode("utf-8")
            self.logger.log(self.log_level, encoded_message.rstrip())
        self.linebuf = ""


def disable_torch_init():
    """
    Disable the redundant torch default initialization to accelerate model creation.
    """
    import torch

    setattr(torch.nn.Linear, "reset_parameters", lambda self: None)
    setattr(torch.nn.LayerNorm, "reset_parameters", lambda self: None)


def get_gpu_memory(max_gpus=None):
    """Get available memory for each GPU."""
    import torch

    gpu_memory = []
    num_gpus = (
        torch.cuda.device_count()
        if max_gpus is None
        else min(max_gpus, torch.cuda.device_count())
    )

    for gpu_id in range(num_gpus):
        with torch.cuda.device(gpu_id):
            device = torch.cuda.current_device()
            gpu_properties = torch.cuda.get_device_properties(device)
            total_memory = gpu_properties.total_memory / (1024**3)
            allocated_memory = torch.cuda.memory_allocated() / (1024**3)
            available_memory = total_memory - allocated_memory
            gpu_memory.append(available_memory)
    return gpu_memory


def oai_moderation(text, custom_thresholds=None):
    """
    Check whether the text violates OpenAI moderation API.
    """
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    flagged = False
    MAX_RETRY = 2
    for _ in range(MAX_RETRY):
        try:
            res = client.moderations.create(input=text, timeout=3)
            flagged = res.results[0].flagged
            if custom_thresholds is not None:
                for category, threshold in custom_thresholds.items():
                    if getattr(res.results[0].category_scores, category) > threshold:
                        flagged = True
            break
        except (openai.OpenAIError, KeyError, IndexError) as e:
            print(f"MODERATION ERROR: {e}\nInput: {text}")
    return flagged


def moderation_filter(text, model_list, do_moderation=False):
    # Apply moderation for below models
    MODEL_KEYWORDS = [
        "claude",
        "gpt",
        "bard",
        "gemini",
        "mistral-large",
        "command-r",
        "dbrx",
        "gemini",
        "reka",
        "eureka",
        "grok",
        "amazon",
    ]

    custom_thresholds = {"sexual": 0.3}
    # set a stricter threshold for claude
    for model in model_list:
        if "claude" in model:
            custom_thresholds = {"sexual": 0.2}

    for keyword in MODEL_KEYWORDS:
        for model in model_list:
            if keyword in model:
                do_moderation = True
                break

    if do_moderation:
        return oai_moderation(text, custom_thresholds)
    return False


def clean_flant5_ckpt(ckpt_path):
    """
    Flan-t5 trained with HF+FSDP saves corrupted  weights for shared embeddings,
    Use this function to make sure it can be correctly loaded.
    """
    import torch

    index_file = os.path.join(ckpt_path, "pytorch_model.bin.index.json")
    index_json = json.load(open(index_file, "r"))

    weightmap = index_json["weight_map"]

    share_weight_file = weightmap["shared.weight"]
    share_weight = torch.load(os.path.join(ckpt_path, share_weight_file))[
        "shared.weight"
    ]

    for weight_name in ["decoder.embed_tokens.weight", "encoder.embed_tokens.weight"]:
        weight_file = weightmap[weight_name]
        weight = torch.load(os.path.join(ckpt_path, weight_file))
        weight[weight_name] = share_weight
        torch.save(weight, os.path.join(ckpt_path, weight_file))


def pretty_print_semaphore(semaphore):
    """Print a semaphore in better format."""
    if semaphore is None:
        return "None"
    return f"Semaphore(value={semaphore._value}, locked={semaphore.locked()})"


"""A javascript function to get url parameters for the gradio web server."""
get_window_url_params_js = """
function() {
    const params = new URLSearchParams(window.location.search);
    url_params = Object.fromEntries(params);
    console.log("url_params", url_params);
    return url_params;
    }
"""

get_window_url_params_with_tos_js = """
function() {
    const params = new URLSearchParams(window.location.search);
    const url_params = Object.fromEntries(params);
    console.log("url_params", url_params);

    const urlContainsLeaderboard = Object.keys(url_params).some(key => key.toLowerCase().includes("leaderboard"));
    const msg = "Users of this website are required to agree to the following terms:\\n\\nThe service is a research preview. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes.\\nPlease do not upload any private information.\\nThe service collects user dialogue data, including both text and images, and reserves the right to distribute it under a Creative Commons Attribution (CC-BY) or a similar license.";
    if (!urlContainsLeaderboard) {
        if (window.alerted_before) return;
        alert(msg);
        window.alerted_before = true;
    }
    return url_params;
    }
"""

alert_js = """
() => {
    if (window.alerted_before) return;
    const msg = "Users of this website are required to agree to the following terms:\\n\\nThe service is a research preview. It only provides limited safety measures and may generate offensive content. It must not be used for any illegal, harmful, violent, racist, or sexual purposes.\\nPlease do not upload any private information.\\nThe service collects user dialogue data, including both text and images, and reserves the right to distribute it under a Creative Commons Attribution (CC-BY) or a similar license.";
    alert(msg);
    window.alerted_before = true;
}
"""


def iter_over_async(
    async_gen: AsyncGenerator, event_loop: AbstractEventLoop
) -> Generator:
    """
    Convert async generator to sync generator

    :param async_gen: the AsyncGenerator to convert
    :param event_loop: the event loop to run on
    :returns: Sync generator
    """
    ait = async_gen.__aiter__()

    async def get_next():
        try:
            obj = await ait.__anext__()
            return False, obj
        except StopAsyncIteration:
            return True, None

    while True:
        done, obj = event_loop.run_until_complete(get_next())
        if done:
            break
        yield obj


def detect_language(text: str) -> str:
    """Detect the langauge of a string."""
    import polyglot  # pip3 install polyglot pyicu pycld2
    from polyglot.detect import Detector
    from polyglot.detect.base import logger as polyglot_logger
    import pycld2

    polyglot_logger.setLevel("ERROR")

    try:
        lang_code = Detector(text).language.name
    except (pycld2.error, polyglot.detect.base.UnknownLanguage):
        lang_code = "unknown"
    return lang_code


def parse_gradio_auth_creds(filename: str):
    """Parse a username:password file for gradio authorization."""
    gradio_auth_creds = []
    with open(filename, "r", encoding="utf8") as file:
        for line in file.readlines():
            gradio_auth_creds += [x.strip() for x in line.split(",") if x.strip()]
    if gradio_auth_creds:
        auth = [tuple(cred.split(":")) for cred in gradio_auth_creds]
    else:
        auth = None
    return auth


def is_partial_stop(output: str, stop_str: str):
    """Check whether the output contains a partial stop str."""
    for i in range(0, min(len(output), len(stop_str))):
        if stop_str.startswith(output[-i:]):
            return True
    return False


def run_cmd(cmd: str):
    """Run a bash command."""
    print(cmd)
    return os.system(cmd)


def is_sentence_complete(output: str):
    """Check whether the output is a complete sentence."""
    end_symbols = (".", "?", "!", "...", "。", "？", "！", "…", '"', "'", "”")
    return output.endswith(end_symbols)


# Models don't use the same configuration key for determining the maximum
# sequence length.  Store them here so we can sanely check them.
# NOTE: The ordering here is important.  Some models have two of these and we
# have a preference for which value gets used.
SEQUENCE_LENGTH_KEYS = [
    "max_position_embeddings",
    "max_sequence_length",
    "seq_length",
    "max_seq_len",
    "model_max_length",
]


def get_context_length(config):
    """Get the context length of a model from a huggingface model config."""
    rope_scaling = getattr(config, "rope_scaling", None)
    if rope_scaling:
        rope_scaling_factor = config.rope_scaling["factor"]
    else:
        rope_scaling_factor = 1

    for key in SEQUENCE_LENGTH_KEYS:
        val = getattr(config, key, None)
        if val is not None:
            return int(rope_scaling_factor * val)
    return 2048


def str_to_torch_dtype(dtype: str):
    import torch

    if dtype is None:
        return None
    elif dtype == "float32":
        return torch.float32
    elif dtype == "float16":
        return torch.float16
    elif dtype == "bfloat16":
        return torch.bfloat16
    else:
        raise ValueError(f"Unrecognized dtype: {dtype}")



def save_music(music_response, music_directory_name, use_remote_storage):
    """
    Save a single music file from the generation response.

    Args:
        music_response: MusicResponseOutput containing audio_data
        music_directory_name: Directory to save the music in
        use_remote_storage: Whether to use GCS storage

    Returns:
        str: Path or URL where the music was saved
    """
    import hashlib
    import os

    if music_response.audio_data is None:
        raise ValueError("No audio data in music response")

    # Generate hash from audio data
    hash_str = hashlib.md5(music_response.audio_data).hexdigest()

    # All music files are MP3s from the server
    filename = os.path.join(
        music_directory_name,
        f"{hash_str}.mp3",
    )

    if use_remote_storage:
        bucket_name = "arena_service_data"
        music_url = upload_music_file_to_gcs(
            music_response.audio_data, bucket_name, filename
        )
        filename = os.path.join("gs://", bucket_name, filename)
    else:
        filename = os.path.join(LOGDIR, filename)
        if not os.path.isfile(filename):
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "wb") as f:
                f.write(music_response.audio_data)
        filename = os.path.abspath(filename)

    return filename


def save_music_files(music_responses, music_directory_name, use_remote_storage):
    """
    Save multiple music files from generation responses.

    Args:
        music_responses: List of MusicResponseOutput objects
        music_directory_name: Directory to save the music in
        use_remote_storage: Whether to use GCS storage

    Returns:
        list: List of paths/URLs where the music files were saved
    """
    filenames = []
    for music in music_responses:
        filenames.append(save_music(music, music_directory_name, use_remote_storage))
    return filenames


def get_music_directory_name_and_remote_storage_flag(use_remote_storage):
    """
    Get the directory name and storage flag for music files.

    Args:
        use_remote_storage: Whether remote storage was requested

    Returns:
        tuple: (directory_name, remote_storage_flag)
    """
    music_directory_name = "txt2music"
    return music_directory_name, use_remote_storage


def upload_music_file_to_gcs(audio_data, bucket_name, filename):
    """
    Upload a music file to Google Cloud Storage.

    Args:
        audio_data: Raw bytes of the audio file
        bucket_name: Name of the GCS bucket
        filename: Destination filename in the bucket

    Returns:
        str: Public URL of the uploaded file
    """
    from google.cloud import storage
    import io

    storage_client = storage.Client()
    # upload file to GCS
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(f"{filename}")

    if not blob.exists():
        buffer = io.BytesIO(audio_data)
        buffer.seek(0)
        blob.upload_from_file(buffer, content_type="audio/mpeg")

    return blob.public_url