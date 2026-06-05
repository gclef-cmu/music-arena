# Bake the model weights (config + safetensors) into the image so the container
# does not download them on first run.
ARG MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN="replace-this-via-docker-build-arg"
RUN python -c "from huggingface_hub import login as hf_login; hf_login(token='$MUSIC_ARENA_SECRET_HUGGINGFACE_READ_TOKEN'); from stable_audio_3.model_configs import all_models; all_models['small-music'].resolve()"
