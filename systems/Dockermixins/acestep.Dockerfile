RUN python -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

RUN git clone https://github.com/ace-step/ACE-Step.git /ace-step && \
    cd /ace-step && \
    git checkout e825b65 && \
    sed -i '1i from setuptools import find_packages' setup.py && \
    sed -i 's/packages=\["acestep"\]/packages=find_packages()/' setup.py && \
    python -m pip install -e .