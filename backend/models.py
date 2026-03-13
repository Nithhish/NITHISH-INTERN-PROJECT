from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Boolean, Text, BigInteger
from sqlalchemy.orm import relationship
from .database import Base
import datetime


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    sessions = relationship("Session", back_populates="player")


class MediaFile(Base):
    """Tracks every uploaded image/video with rich metadata."""
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    file_uuid = Column(String, unique=True, index=True)          # UUID used for disk filename
    original_filename = Column(String)
    media_type = Column(String, index=True)                      # "video" | "image"
    mime_type = Column(String, nullable=True)                     # e.g. "video/mp4", "image/jpeg"
    extension = Column(String)                                    # e.g. "mp4", "jpg"
    file_path = Column(String)                                    # relative path on disk
    file_size_bytes = Column(BigInteger, default=0)               # file size in bytes
    width = Column(Integer, nullable=True)                        # image/video width px
    height = Column(Integer, nullable=True)                       # image/video height px
    duration_sec = Column(Float, nullable=True)                   # video duration in seconds
    fps = Column(Float, nullable=True)                            # video FPS
    total_frames = Column(Integer, nullable=True)                 # video frame count
    thumbnail_path = Column(String, nullable=True)                # path to auto-generated thumbnail
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    checksum_sha256 = Column(String, nullable=True)               # file integrity hash

    # Relationships
    sessions = relationship("Session", back_populates="media_file")
    annotated_outputs = relationship("AnnotatedOutput", back_populates="media_file")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    media_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=True)
    video_path = Column(String)
    media_type = Column(String, default="video")  # video | image
    original_filename = Column(String, nullable=True)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="processing")  # processing | done | error
    error_message = Column(Text, nullable=True)    # error details if status == "error"
    processing_time_sec = Column(Float, nullable=True)  # total wall-clock processing time

    player = relationship("Player", back_populates="sessions")
    media_file = relationship("MediaFile", back_populates="sessions")
    shots = relationship("ShotMetric", back_populates="session")
    processing_logs = relationship("ProcessingLog", back_populates="session",
                                   order_by="ProcessingLog.started_at")


class ShotMetric(Base):
    __tablename__ = "shot_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    shot_id = Column(Integer)  # ID from the CV engine

    # Core Metrics
    swing_speed_max = Column(Float)
    swing_duration = Column(Float)
    reaction_time = Column(Float)
    stability_deviation = Column(Float)
    technique_score = Column(Float)

    # Detailed Data
    impact_frame = Column(Integer)
    score_breakdown = Column(JSON)
    angle_metrics = Column(JSON)  # Impact elbow/knee etc.

    session = relationship("Session", back_populates="shots")
    injury_flags = relationship("InjuryFlag", back_populates="shot")


class InjuryFlag(Base):
    __tablename__ = "injury_flags"

    id = Column(Integer, primary_key=True, index=True)
    shot_metric_id = Column(Integer, ForeignKey("shot_metrics.id"))
    type = Column(String)
    severity = Column(String)
    message = Column(String)
    value = Column(Float)

    shot = relationship("ShotMetric", back_populates="injury_flags")


class ProcessingLog(Base):
    """Tracks each step of the CV processing pipeline for a session."""
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), index=True)
    step_name = Column(String)        # e.g. "upload", "yolo_inference", "shot_detection", "scoring"
    status = Column(String)           # "started" | "completed" | "failed"
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)   # any extra info (frame count, shots found, etc.)
    error_message = Column(Text, nullable=True)

    session = relationship("Session", back_populates="processing_logs")


class AnnotatedOutput(Base):
    """Stores generated output files (annotated images, overlay videos, keypoint JSONs)."""
    __tablename__ = "annotated_outputs"

    id = Column(Integer, primary_key=True, index=True)
    media_file_id = Column(Integer, ForeignKey("media_files.id"), index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), index=True)
    output_type = Column(String)      # "annotated_image" | "annotated_video" | "keypoints_json" | "thumbnail"
    file_path = Column(String)        # path on disk
    file_size_bytes = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    extra_metadata = Column(JSON, nullable=True)  # extra info (e.g. overlay settings used)

    media_file = relationship("MediaFile", back_populates="annotated_outputs")
