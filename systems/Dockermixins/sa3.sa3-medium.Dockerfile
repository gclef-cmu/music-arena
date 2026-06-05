# Stable Audio 3 Medium requires Flash Attention 2. Install a prebuilt wheel
# matching CUDA 12.6 / PyTorch 2.7 / Python 3.10 (no compilation needed).
# --no-deps is critical: the wheel declares an unpinned `torch` dependency, so
# without it pip would pull the latest torch and clobber the cu126 2.7.1 build.
RUN python -m pip install --no-deps \
    https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.16/flash_attn-2.6.3+cu126torch2.7-cp310-cp310-linux_x86_64.whl
RUN python -c "import flash_attn; from flash_attn import flash_attn_func; print('flash_attn', flash_attn.__version__)"

# Bake the model weights (config + safetensors) into the image so the container
# does not download them on first run.
ARG MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN="replace-this-via-docker-build-arg"
RUN python -c "from huggingface_hub import login as hf_login; hf_login(token='$MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN'); from stable_audio_3.model_configs import all_models; all_models['medium'].resolve()"
