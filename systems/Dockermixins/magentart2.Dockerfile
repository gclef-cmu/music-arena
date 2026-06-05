ENV MAGENTA_HOME=/magenta
ENV MAGENTA_RT_DIR=/magenta-realtime

RUN git clone --branch v2.0.2 --recurse-submodules \
    https://github.com/magenta/magenta-realtime.git ${MAGENTA_RT_DIR}
RUN python -m pip install -e "${MAGENTA_RT_DIR}[jax]"

# Install a CUDA-enabled JAX wheel (the cuda12 plugin ships its own CUDA libs).
RUN python -m pip install "jax[cuda12]"

# Cache shared resources: MusicCoCa (style) and SpectroStream (codec).
RUN mrt models init
RUN ls -la ${MAGENTA_HOME}/magenta-rt-v2/resources/musiccoca || exit 1
RUN ls -la ${MAGENTA_HOME}/magenta-rt-v2/resources/spectrostream || exit 1
