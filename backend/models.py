from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Boolean
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

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    video_path = Column(String)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    player = relationship("Player", back_populates="sessions")
    shots = relationship("ShotMetric", back_populates="session")

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
