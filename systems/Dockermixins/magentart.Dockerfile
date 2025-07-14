RUN git clone https://github.com/magenta/magenta-realtime /magenta-realtime && \
    cd /magenta-realtime && \
    git checkout ac01a5e93efc71646f0629be4ca3c123cef73e8f && \
    python -m pip install -e . --no-deps

# Patch magenta-realtime to use AnonymousCredentials for public access
RUN sed -i '1i\from google.auth.credentials import AnonymousCredentials' /magenta-realtime/magenta_rt/asset.py
RUN sed -i 's/storage\.Client()/storage.Client(project=None, credentials=AnonymousCredentials())/g' /magenta-realtime/magenta_rt/asset.py

# Cache model checkpoints
ENV MAGENTA_RT_CACHE_DIR=/magenta-realtime/cache
RUN python -m pip install --no-cache-dir absl-py google-cloud-storage tqdm
RUN python -m magenta_rt.fetch_asset --asset=README.md
RUN ls -la $MAGENTA_RT_CACHE_DIR/assets/README.md || exit 1
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212f_cpu_compat --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212_quant --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/encoder --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/decoder --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/quantizer --is_dir