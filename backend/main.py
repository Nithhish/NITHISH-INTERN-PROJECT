from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
import uuid

from . import models, schemas, database, cv_processor
from .database import engine, get_db

# Initialize Database
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cricket Training Analysis API")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@app.get("/")
def read_root():
    return {"message": "Cricket Training API is running"}

# --- Player Endpoints ---
@app.post("/players/", response_model=schemas.PlayerBase)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(name=player.name, email=player.email)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

@app.get("/players/", response_model=List[schemas.PlayerBase])
def list_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()

# --- Video Processing Endpoint ---
@app.post("/upload/{player_id}")
async def upload_video(
    player_id: int, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # 1. Verify player
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # 2. Save file
    file_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Create Session Entry
    db_session = models.Session(player_id=player_id, video_path=file_path)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # 4. Run CV Processing in Background
    background_tasks.add_task(process_session_task, db_session.id, file_path)

    return {
        "message": "Video uploaded successfully. Processing started in background.",
        "session_id": db_session.id
    }

def process_session_task(session_id: int, video_path: str):
    """Background task for processing the video and storing metrics."""
    # We create a new DB session for background task
    db = database.SessionLocal()
    try:
        shots, frames = cv_processor.process_video_inference(video_path)
        
        for s in shots:
            db_shot = models.ShotMetric(
                session_id=session_id,
                shot_id=s['shot_id'],
                swing_speed_max=s['swing_speed_max_deg_per_sec'],
                swing_duration=s['swing_duration_sec'],
                reaction_time=s['reaction_time_sec'],
                stability_deviation=s['stability_deviation'],
                technique_score=s['technique_score'],
                impact_frame=s['impact_frame'],
                score_breakdown=s['score_breakdown'],
                angle_metrics={
                    "elbow": s['elbow_angle_at_impact'],
                    "knee": s['knee_angle_at_impact']
                }
            )
            db.add(db_shot)
            db.flush() # Get shot ID

            # Add Injury Flags
            for risk in s['injury_risks']:
                db_flag = models.InjuryFlag(
                    shot_metric_id=db_shot.id,
                    type=risk['type'],
                    severity=risk['severity'],
                    message=risk['message'],
                    value=risk.get('value', 0.0)
                )
                db.add(db_flag)
        
        db.commit()
    except Exception as e:
        print(f"[ERROR] Session {session_id} failed: {e}")
    finally:
        db.close()

@app.get("/sessions/{session_id}")
def get_session_results(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
