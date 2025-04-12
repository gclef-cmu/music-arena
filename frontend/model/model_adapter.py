"""
Model adapter registration. 
[Adapted from] https://github.com/lmarena/FastChat-dev/blob/yonghyun/txt2music-dev/fastchat/model/model_adapter.py
This part should be modified when any new model is added from the backend.
"""
import os
import sys

if sys.version_info >= (3, 9):
    from functools import cache
else:
    from functools import lru_cache as cache


from conversation import Conversation
from conversation import get_conv_template

class MusicGenSmallAdapter():
    def match(self, model_path: str):
        return "musicgen-small" in model_path.lower()

    def get_default_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("musicgen-small-style")

class MusicGenLargeAdapter():
    def match(self, model_path: str):
        return "musicgen-large" in model_path.lower()

    def get_default_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("musicgen-large-style")

class SaoAdapter():
    def match(self, model_path: str):
        return "sao" in model_path.lower()

    def get_default_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("sao-style")

class SongGenAdapter():
    def match(self, model_path: str):
        return "songgen" in model_path.lower()

    def get_default_conv_template(self, model_path: str) -> Conversation:
        return get_conv_template("songgen-style")

model_adapters = [
    MusicGenSmallAdapter(),
    MusicGenLargeAdapter(),
    SaoAdapter(),
    SongGenAdapter()
]
