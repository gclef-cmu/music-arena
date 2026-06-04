# Cache the raw JAX checkpoint (safetensors) for the small (230M) model.
RUN mrt checkpoints download mrt2_small.safetensors
RUN ls -la ${MAGENTA_HOME}/magenta-rt-v2/checkpoints/mrt2_small.safetensors || exit 1
