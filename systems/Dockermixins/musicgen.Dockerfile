RUN python -m pip install --no-cache-dir torch==2.1.0 transformers==4.34.0 audiocraft==1.3.0
RUN python -m pip install --no-cache-dir --upgrade numpy==1.26.4
# No need to set AUDIOCRAFT_CACHE_DIR since we want to cache the weights in the container
#ENV AUDIOCRAFT_CACHE_DIR=$MUSIC_ARENA_CACHE_DIR/systems/musicgen

# Fix numba/librosa caching issue in containers
ENV NUMBA_DISABLE_JIT=1
# Fix NumPy/PyTorch compatibility warnings
ENV NUMPY_EXPERIMENTAL_ARRAY_FUNCTION=0