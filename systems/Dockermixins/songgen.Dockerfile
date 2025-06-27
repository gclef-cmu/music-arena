# Install Python dependencies
RUN pip install --no-cache-dir \
    torch==2.3.0 \
    torchvision==0.18.0 \
    torchaudio==2.3.0

# TODO(chrisdonahue): figure out how to install flash-attn in Docker
#RUN pip install --no-cache-dir flash-attn==2.6.1 --no-build-isolation

# Clone SongGen repository
RUN git clone https://github.com/LiuZH-19/SongGen.git /songgen
WORKDIR /songgen
RUN git checkout f18fad1
RUN pip install -e .

# Cache X-Codec checkpoint
RUN apt install -y wget
RUN mkdir -p songgen/xcodec_wrapper/xcodec_infer/ckpts/general_more
RUN wget https://huggingface.co/ZhenYe234/xcodec/resolve/main/xcodec_hubert_general_audio_v2.pth \
    -O songgen/xcodec_wrapper/xcodec_infer/ckpts/general_more/xcodec_hubert_general_audio_v2.pth

# Cache other component weights
RUN pip install --no-cache-dir huggingface_hub
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('LiuZH-19/SongGen_mixed_pro')"
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('m-a-p/MERT-v1-330M')"
RUN mkdir -p /root/.cache/torch/hub/checkpoints
RUN wget https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th -O /root/.cache/torch/hub/checkpoints/955717e8-8726e21a.th
RUN python -c "import transformers; transformers.utils.move_cache()"

# Install nest_asyncio for lyrics generation support
RUN pip install --no-cache-dir nest_asyncio