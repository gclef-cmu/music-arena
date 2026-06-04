# Cache the raw JAX checkpoint (safetensors) for the base (2.4B) model.
RUN mrt checkpoints download mrt2_base.safetensors
RUN ls -la ${MAGENTA_HOME}/magenta-rt-v2/checkpoints/mrt2_base.safetensors || exit 1
