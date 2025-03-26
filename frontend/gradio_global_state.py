'''
[Source] https://github.com/lmarena/FastChat-dev/blob/yonghyun/txt2music-dev/fastchat/serve/gradio_global_state.py
'''

from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel, Field

class ArenaType:
    TXT2MUSIC = "txt2music-arena"

@dataclass
class Context:
    music_models: List[str] = field(default_factory=list)
    all_music_models: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    all_models: List[str] = field(default_factory=list)
    arena_type: str = ArenaType.TXT2MUSIC

class RepoChatContext(BaseModel):
    repo_link: str = Field(default="")
    user_query: str = Field(default="")
    retriever_config: dict = Field(default={})
    files: List[str] = Field(default=[])
    filtered_files: List[str] = Field(default=[])
    metadata: dict = Field(default={})

class RepoChatBattleContext(BaseModel):
    inputs: Optional[List[str]] = Field(default=[None, None])
    contexts: Optional[List[RepoChatContext]] = Field(default=[None, None])