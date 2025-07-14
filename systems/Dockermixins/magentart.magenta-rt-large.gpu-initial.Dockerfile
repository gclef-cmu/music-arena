RUN python -m pip install -e /magenta-realtime[gpu]
RUN python -m pip uninstall -y tensorflow tf-nightly tensorflow-cpu tf-nightly-cpu tensorflow-tpu tf-nightly-tpu tensorflow-hub tf-hub-nightly tensorflow-text tensorflow-text-nightly
RUN python -m pip install --no-cache-dir tf-nightly==2.20.0.dev20250619 tensorflow-text-nightly==2.20.0.dev20250316 tf-hub-nightly
