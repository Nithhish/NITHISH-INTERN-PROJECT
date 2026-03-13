from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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


# --- Processing Log Schemas ---
class ProcessingLogBase(BaseModel):
    id: int
    step_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_sec: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# --- Annotated Output Schemas ---
class AnnotatedOutputBase(BaseModel):
    id: int
    output_type: str
    file_path: str
    file_size_bytes: int = 0
    created_at: datetime
    extra_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# --- Media File Schemas ---
class MediaFileBase(BaseModel):
    id: int
    file_uuid: str
    original_filename: str
    media_type: str
    mime_type: Optional[str] = None
    extension: str
    file_path: str
    file_size_bytes: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    duration_sec: Optional[float] = None
    fps: Optional[float] = None
    total_frames: Optional[int] = None
    thumbnail_path: Optional[str] = None
    uploaded_at: datetime
    checksum_sha256: Optional[str] = None

    class Config:
        from_attributes = True


class MediaFileDetail(MediaFileBase):
    """Includes related annotated outputs."""
    annotated_outputs: List[AnnotatedOutputBase] = []

    class Config:
        from_attributes = True


# --- Session Schemas ---
class SessionBase(BaseModel):
    id: int
    player_id: int
    video_path: str
    media_type: str = "video"
    original_filename: Optional[str] = None
    processed_at: datetime
    status: str = "processing"
    error_message: Optional[str] = None
    processing_time_sec: Optional[float] = None
    shots: List[ShotMetricBase]

    class Config:
        from_attributes = True


class SessionDetail(SessionBase):
    """Includes processing logs and media file info."""
    processing_logs: List[ProcessingLogBase] = []
    media_file: Optional[MediaFileBase] = None

    class Config:
        from_attributes = True


# --- Player Schemas ---
class PlayerBase(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class PlayerCreate(BaseModel):
    name: str
    email: str


# --- Gallery / Dashboard Schemas ---
class MediaGalleryItem(BaseModel):
    """Lightweight schema for gallery/listing views."""
    id: int
    file_uuid: str
    original_filename: str
    media_type: str
    thumbnail_url: Optional[str] = None
    uploaded_at: datetime
    width: Optional[int] = None
    height: Optional[int] = None
    duration_sec: Optional[float] = None
    file_size_bytes: int = 0
    session_count: int = 0
    latest_status: Optional[str] = None

    class Config:
        from_attributes = True


class ProcessingStats(BaseModel):
    """Dashboard statistics."""
    total_uploads: int = 0
    total_images: int = 0
    total_videos: int = 0
    total_sessions: int = 0
    completed_sessions: int = 0
    failed_sessions: int = 0
    processing_sessions: int = 0
    total_shots_analyzed: int = 0
    avg_technique_score: Optional[float] = None
    total_storage_bytes: int = 0
