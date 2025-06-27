ARG BASE_CONTAINER="music-arena-base"
FROM ${BASE_CONTAINER}

ENV MUSIC_ARENA_CONTAINER_COMPONENT=gateway
WORKDIR ${MUSIC_ARENA_REPO_DIR}/components/${MUSIC_ARENA_CONTAINER_COMPONENT}

COPY setup.py .
RUN mkdir -p ma_gateway/
RUN touch ma_gateway/__init__.py
RUN pip install --no-cache-dir -e .

EXPOSE 8080
ENTRYPOINT [ "python", "-m", "ma_gateway.gateway" ]