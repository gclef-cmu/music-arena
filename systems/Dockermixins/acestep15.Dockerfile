RUN git clone https://github.com/ace-step/ACE-Step-1.5.git /ace-step-1.5 && \
    cd /ace-step-1.5 && \
    git checkout 2b1ad8c && \
    python -m pip install --break-system-packages -e acestep/third_parts/nano-vllm && \
    PIP_IGNORE_INSTALLED=0 python -m pip install --break-system-packages --extra-index-url https://download.pytorch.org/whl/cu128 -e .

# Pre-cache ACE-Step 1.5 MAIN_MODEL_COMPONENTS one-by-one.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='ACE-Step/Ace-Step1.5', local_dir='/ace-step-1.5/checkpoints', local_dir_use_symlinks=False, allow_patterns=['acestep-v15-turbo/*'])"
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='ACE-Step/Ace-Step1.5', local_dir='/ace-step-1.5/checkpoints', local_dir_use_symlinks=False, allow_patterns=['vae/*'])"
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='ACE-Step/Ace-Step1.5', local_dir='/ace-step-1.5/checkpoints', local_dir_use_symlinks=False, allow_patterns=['Qwen3-Embedding-0.6B/*'])"

RUN cd /ace-step-1.5 && git checkout 816825b121c50c6aec547a5bbd0e34cbd21561c5