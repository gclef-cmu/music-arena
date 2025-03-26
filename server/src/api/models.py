from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AudioPairRequest(BaseModel):
    """Request model for generating a pair of audio samples."""
    prompt: str
    user_id: str = Field(..., alias="userId")
    seed: Optional[int] = None
    model_key: Optional[str] = Field(None, alias="modelKey")
    
class AudioPairResponse(BaseModel):
    """Response model for a pair of generated audio samples."""
    pair_id: str = Field(..., alias="pairId")
    audio_items: List[Dict[str, Any]] = Field(..., alias="audioItems")

class AudioMetadata(BaseModel):
    """Metadata for an audio file."""
    audio_id: str = Field(..., alias="audioId")
    user_id: str = Field(..., alias="userId")
    timestamp: int
    prompt: str
    model: str
    seed: Optional[int] = None
    latency: float
    pair_audio_id: Optional[str] = Field(None, alias="pairAudioId")
    pair_index: Optional[int] = Field(None, alias="pairIndex")