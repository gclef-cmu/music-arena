RUN python -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

RUN git clone https://github.com/ace-step/ACE-Step.git /ace-step && \
    cd /ace-step && \
    git checkout e825b65 && \
    sed -i '1i from setuptools import find_packages' setup.py && \
    sed -i 's/packages=\["acestep"\]/packages=find_packages()/' setup.py && \
    python -m pip install -e .

RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='music_dcae_f8c8', filename='config.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='music_dcae_f8c8', filename='diffusion_pytorch_model.safetensors', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='music_vocoder', filename='config.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='music_vocoder', filename='diffusion_pytorch_model.safetensors', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='ace_step_transformer', filename='config.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='ace_step_transformer', filename='diffusion_pytorch_model.safetensors', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='umt5-base', filename='config.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='umt5-base', filename='model.safetensors', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='umt5-base', filename='special_tokens_map.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='umt5-base', filename='tokenizer_config.json', local_dir=None, local_dir_use_symlinks=False)"
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='ACE-Step/ACE-Step-v1-3.5B', subfolder='umt5-base', filename='tokenizer.json', local_dir=None, local_dir_use_symlinks=False)"