# Stable Audio 3 Medium requires Flash Attention 2. Install a prebuilt wheel
# matching CUDA 12.6 / PyTorch 2.7 / Python 3.10 (no compilation needed).
# --no-deps is critical: the wheel declares an unpinned `torch` dependency, so
# without it pip would pull the latest torch and clobber the cu126 2.7.1 build.
RUN python -m pip install --no-deps \
    https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.16/flash_attn-2.6.3+cu126torch2.7-cp310-cp310-linux_x86_64.whl
RUN python -c "import flash_attn; from flash_attn import flash_attn_func; print('flash_attn', flash_attn.__version__)"
