from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AudioPairRequest(BaseModel):
    """Request model for generating a pair of audio samples."""
    prompt: str
    user_id: str = Field(..., alias="userId")
    seed: Optional[int] = None
    model_key: Optional[str] = Field(None, alias="modelKey")
    
class AudioItem(BaseModel):
    """Model for an audio item with metadata and binary data."""
    audio_id: str = Field(..., alias="audioId")
    user_id: str = Field(..., alias="userId")
    timestamp: int
    prompt: str
    model: str
    seed: Optional[int] = None
    latency: float
    pair_audio_id: Optional[str] = Field(None, alias="pairAudioId")
    pair_index: Optional[int] = Field(None, alias="pairIndex")
    audio_url: str = Field(..., alias="audioUrl")
    audio_data_base64: str = Field(..., alias="audioDataBase64")
    
class AudioPairResponse(BaseModel):
    """Response model for a pair of generated audio samples."""
    pair_id: str = Field(..., alias="pairId")
    audio_items: List[AudioItem] = Field(..., alias="audioItems")

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

class VoteRequest(BaseModel):
    """Request model for recording a vote on an audio pair."""
    pair_id: str = Field(..., alias="pairId")
    user_id: str = Field(..., alias="userId")
    winning_audio_id: str = Field(..., alias="winningAudioId")
    losing_audio_id: str = Field(..., alias="losingAudioId")
    winning_model: str = Field(..., alias="winningModel")
    losing_model: str = Field(..., alias="losingModel")
    winning_index: int = Field(..., alias="winningIndex")
    prompt: str
    
class VoteResponse(BaseModel):
    """Response model for a recorded vote."""
    vote_id: str = Field(..., alias="voteId")
    timestamp: int
    status: str