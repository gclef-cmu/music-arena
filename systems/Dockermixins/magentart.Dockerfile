RUN git clone https://github.com/magenta/magenta-realtime /magenta-realtime && \
    cd /magenta-realtime && \
    git checkout 3d74b1912911dbd612f4b63218c5be3eec43c08f && \
    python -m pip install -e . --no-deps

# Cache model checkpoints
ENV MAGENTA_RT_CACHE_DIR=/magenta-realtime/cache
RUN python -m pip install --no-cache-dir absl-py google-cloud-storage huggingface-hub tqdm
RUN python -m magenta_rt.fetch_asset --asset=README.md
RUN ls -la $MAGENTA_RT_CACHE_DIR/assets/README.md || exit 1
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212f_cpu_compat --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212_quant --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/encoder --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/decoder --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/quantizer --source=hf --is_dir

# Patch t5x to use flax 0.10.6 instead of latest (latest requires Python >3.10)
RUN git clone https://github.com/google-research/t5x.git /t5x && \
    pushd /t5x && \
    git checkout 92c5b467a5964d06c351c7eae4aa4bcd341c7ded && \
    sed -i 's|flax @ git+https://github.com/google/flax#egg=flax|flax==0.10.6|g' setup.py && \
    python -m pip install -e .[gpu] && \
    popd

# Also patch MagentaRT's pyproject.toml
RUN pushd /magenta-realtime && \
    sed -i 's|t5x[gpu] @ git+https://github.com/google-research/t5x.git@92c5b46|t5x[gpu]|g' pyproject.toml && \
    sed -i 's|t5x @ git+https://github.com/google-research/t5x.git@92c5b46|t5x|g' pyproject.toml && \
    popd