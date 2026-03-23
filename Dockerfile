ARG BASE_CONTAINER="python:3.10-slim"
FROM ${BASE_CONTAINER}

ENV MUSIC_ARENA_REPO_DIR=/music-arena
WORKDIR ${MUSIC_ARENA_REPO_DIR}

# Configure shell
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# Fix GPG keys
RUN apt-get update --allow-releaseinfo-change --allow-insecure-repositories || true \
    && apt-get install -y --no-install-recommends --allow-unauthenticated \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install core system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    wget \
    git \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install ffmpeg
RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python 3 (in case BASE_CONTAINER does not have it)
ENV LANG=C.UTF-8
RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN [ ! -f /usr/local/bin/python ] && ln -s $(which python3) /usr/local/bin/python || true
ENV PIP_NO_CACHE_DIR=1
ARG PEP_668_OVERRIDE=0
ENV PIP_BREAK_SYSTEM_PACKAGES=${PEP_668_OVERRIDE}
ENV PIP_IGNORE_INSTALLED=${PEP_668_OVERRIDE}
RUN python -m pip install --upgrade pip
#RUN python -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor == 10"

# Create placeholder for music_arena
ENV MUSIC_ARENA_EXECUTING_IN_CONTAINER=1
ENV MUSIC_ARENA_LIB_DIR=${MUSIC_ARENA_REPO_DIR}/music_arena
RUN mkdir -p ${MUSIC_ARENA_LIB_DIR}
RUN touch ${MUSIC_ARENA_LIB_DIR}/__init__.py
COPY setup.py ${MUSIC_ARENA_REPO_DIR}/setup.py
RUN python -m pip install -e ${MUSIC_ARENA_REPO_DIR}
ENV MUSIC_ARENA_IO_DIR=${MUSIC_ARENA_REPO_DIR}/io
RUN mkdir -p ${MUSIC_ARENA_IO_DIR}
ENV MUSIC_ARENA_SYSTEMS_DIR=${MUSIC_ARENA_REPO_DIR}/systems
RUN mkdir -p ${MUSIC_ARENA_SYSTEMS_DIR}
ENV MUSIC_ARENA_CACHE_DIR=${MUSIC_ARENA_REPO_DIR}/cache
RUN mkdir -p ${MUSIC_ARENA_CACHE_DIR}
ENV MUSIC_ARENA_COMPONENTS_DIR=${MUSIC_ARENA_REPO_DIR}/components
RUN mkdir -p ${MUSIC_ARENA_COMPONENTS_DIR}

CMD ["python", "-m", "unittest", "discover", "-v", "."]