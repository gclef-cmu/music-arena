ENV SA3_DIR=/stable-audio-3

# Install CUDA-enabled torch matching the stable-audio-3 pin (cu126). Installing
# it explicitly first means the editable install below finds the requirement
# already satisfied and does not pull a CPU-only wheel from PyPI.
RUN python -m pip install torch==2.7.1 torchaudio==2.7.1 \
    --index-url https://download.pytorch.org/whl/cu126

# Clone and install stable-audio-3.
RUN git clone https://github.com/Stability-AI/stable-audio-3.git ${SA3_DIR}
RUN python -m pip install -e ${SA3_DIR}
