from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class InjuryFlagBase(BaseModel):
    type: str
    severity: str
    message: str
    value: float

class ShotMetricBase(BaseModel):
    shot_id: int
    swing_speed_max: float
    swing_duration: float
    reaction_time: float
    stability_deviation: float
    technique_score: float
    impact_frame: int
    score_breakdown: Dict
    angle_metrics: Dict
    injury_flags: List[InjuryFlagBase]

class SessionBase(BaseModel):
    id: int
    player_id: int
    video_path: str
    processed_at: datetime
    shots: List[ShotMetricBase]

    class Config:
        orm_mode = True

class PlayerBase(BaseModel):
    id: int
    name: str
    email: str
    
    class Config:
        orm_mode = True

class PlayerCreate(BaseModel):
    name: str
    email: str
