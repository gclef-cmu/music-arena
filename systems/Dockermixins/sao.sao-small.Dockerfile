RUN python -m pip install --no-cache-dir stable-audio-tools==0.0.19
ARG MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN="replace-this-via-docker-build-arg"
RUN python -c "from huggingface_hub import login as hf_login; hf_login(token='$MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN'); from stable_audio_tools import get_pretrained_model; get_pretrained_model('stabilityai/stable-audio-open-small')"