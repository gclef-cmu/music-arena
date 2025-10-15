# Cache model checkpoints
ENV MAGENTA_RT_CACHE_DIR=/magenta-realtime/cache
RUN python -m magenta_rt.fetch_asset --asset=README.md
RUN ls -la $MAGENTA_RT_CACHE_DIR/assets/README.md || exit 1
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212f_cpu_compat --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/musiccoca_mv212_quant --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/encoder --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/decoder --source=hf --is_dir
RUN python -m magenta_rt.fetch_asset --asset=savedmodels/ssv2_48k_stereo/quantizer --source=hf --is_dir
