from fastapi import FastAPI, Depends, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
import shutil
import os
import uuid
import time
import datetime
from dotenv import load_dotenv
load_dotenv()

from . import models, schemas, database, cv_processor, telegram_bot, openai_bot, media_utils, firebase_manager
from .firebase_manager import firebase_client
from .database import engine, get_db

# Initialize Database
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cricket Training Analysis API")

# Allow CORS for all origins (needed for Capacitor/mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
THUMBNAIL_DIR = os.path.join(UPLOAD_DIR, "thumbnails")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(THUMBNAIL_DIR):
    os.makedirs(THUMBNAIL_DIR)

ALLOWED_VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm", "3gp"}
ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp"}

# =========================================================================
#  Helper: Create a ProcessingLog entry
# =========================================================================
def _log_step(db: Session, session_id: int, step_name: str,
              status: str = "started", details: dict = None,
              error_message: str = None) -> models.ProcessingLog:
    log = models.ProcessingLog(
        session_id=session_id,
        step_name=step_name,
        status=status,
        started_at=datetime.datetime.utcnow(),
        details=details,
        error_message=error_message
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _complete_log(db: Session, log: models.ProcessingLog,
                  details: dict = None, error: str = None):
    log.completed_at = datetime.datetime.utcnow()
    log.duration_sec = (log.completed_at - log.started_at).total_seconds()
    log.status = "failed" if error else "completed"
    if details:
        log.details = details
    if error:
        log.error_message = error
    db.commit()


# =========================================================================
#  Helper: Create a MediaFile record & extract metadata
# =========================================================================
def _create_media_file(db: Session, file_path: str, file_uuid: str,
                       original_filename: str, ext: str, media_type: str,
                       mime_type: str = None) -> models.MediaFile:
    """Create a MediaFile record with full metadata + thumbnail."""
    file_size = media_utils.get_file_size(file_path)
    checksum = media_utils.get_file_hash(file_path)

    width = height = duration_sec = fps = total_frames = None
    if media_type == "image":
        meta = media_utils.get_image_metadata(file_path)
        width, height = meta["width"], meta["height"]
    elif media_type == "video":
        meta = media_utils.get_video_metadata(file_path)
        width, height = meta["width"], meta["height"]
        fps = meta["fps"]
        duration_sec = meta["duration_sec"]
        total_frames = meta["total_frames"]

    # Generate thumbnail
    thumb_path = media_utils.generate_thumbnail(file_path, media_type, THUMBNAIL_DIR)

    media_file = models.MediaFile(
        file_uuid=file_uuid,
        original_filename=original_filename,
        media_type=media_type,
        mime_type=mime_type,
        extension=ext,
        file_path=file_path,
        file_size_bytes=file_size,
        width=width,
        height=height,
        duration_sec=duration_sec,
        fps=fps,
        total_frames=total_frames,
        thumbnail_path=thumb_path,
        checksum_sha256=checksum
    )
    db.add(media_file)
    db.commit()
    db.refresh(media_file)
    return media_file


# =========================================================================
#  Helper: Save AnnotatedOutput record
# =========================================================================
def _save_annotated_output(db: Session, media_file_id: int, session_id: int,
                           output_type: str, file_path: str,
                           extra_meta: dict = None):
    size = media_utils.get_file_size(file_path) if os.path.exists(file_path) else 0
    out = models.AnnotatedOutput(
        media_file_id=media_file_id,
        session_id=session_id,
        output_type=output_type,
        file_path=file_path,
        file_size_bytes=size,
        extra_metadata=extra_meta
    )
    db.add(out)
    db.commit()


# =========================================================================
#  Player Endpoints
# =========================================================================
@app.post("/players/", response_model=schemas.PlayerBase)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(name=player.name, email=player.email)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    
    # Sync to Firebase
    if firebase_client.initialized:
        firebase_client.create_player(db_player.id, db_player.name, db_player.email)
        
    return db_player

@app.get("/players/", response_model=List[schemas.PlayerBase])
def list_players(db: Session = Depends(get_db)):
    # Source of truth is still SQL, but we could return from Firebase if desired
    return db.query(models.Player).all()


# =========================================================================
#  Video Upload & Processing Endpoint
# =========================================================================
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

    # 2. Detect extension — from filename or content-type header
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Fallback: guess from content-type (handles Android gallery content:// URIs)
    if ext not in ALLOWED_VIDEO_EXTS:
        ct = (file.content_type or "").lower()
        ct_map = {
            "video/mp4": "mp4", "video/quicktime": "mov",
            "video/x-msvideo": "avi", "video/x-matroska": "mkv",
            "video/webm": "webm", "video/3gpp": "3gp",
        }
        ext = ct_map.get(ct, "mp4")  # default mp4

    # 3. Save file
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Create MediaFile record with metadata
    media_file = _create_media_file(
        db, file_path, file_id, filename, ext,
        media_type="video", mime_type=file.content_type
    )

    # 5. Create Session Entry (linked to MediaFile)
    db_session = models.Session(
        player_id=player_id,
        media_file_id=media_file.id,
        video_path=file_path,
        media_type="video",
        original_filename=filename
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # 6. Log the upload step
    _log_step(db, db_session.id, "upload", "completed",
              details={"file_size": media_file.file_size_bytes,
                       "resolution": f"{media_file.width}x{media_file.height}",
                       "duration": media_file.duration_sec})

    # 7. Run CV Processing in Background
    background_tasks.add_task(process_session_task, db_session.id, file_path, media_file.id)

    return {
        "message": "Video uploaded successfully. Processing started in background.",
        "session_id": db_session.id,
        "media_file_id": media_file.id,
        "media_url": f"/media/{file_id}.{ext}",
        "thumbnail_url": f"/media/thumbnails/{file_id}_thumb.jpg" if media_file.thumbnail_path else None
    }


# =========================================================================
#  Image Upload & Processing Endpoint
# =========================================================================
@app.post("/upload-image/{player_id}")
async def upload_image(
    player_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Verify player
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # 2. Detect extension
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_IMAGE_EXTS:
        ct = (file.content_type or "").lower()
        ct_map = {
            "image/jpeg": "jpg", "image/png": "png",
            "image/webp": "webp", "image/bmp": "bmp",
        }
        ext = ct_map.get(ct, "jpg")  # default jpg

    # 3. Save file
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Create MediaFile record with metadata
    media_file = _create_media_file(
        db, file_path, file_id, filename, ext,
        media_type="image", mime_type=file.content_type
    )

    # 5. Create Session Entry (linked to MediaFile)
    db_session = models.Session(
        player_id=player_id,
        media_file_id=media_file.id,
        video_path=file_path,
        media_type="image",
        original_filename=filename
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # 6. Log the upload step
    _log_step(db, db_session.id, "upload", "completed",
              details={"file_size": media_file.file_size_bytes,
                       "resolution": f"{media_file.width}x{media_file.height}"})

    # 7. Process image in background
    background_tasks.add_task(process_image_task, db_session.id, file_path, media_file.id)

    return {
        "message": "Image uploaded successfully. Processing started.",
        "session_id": db_session.id,
        "media_file_id": media_file.id,
        "media_url": f"/media/{file_id}.{ext}",
        "thumbnail_url": f"/media/thumbnails/{file_id}_thumb.jpg" if media_file.thumbnail_path else None
    }


# =========================================================================
#  Background Processing Tasks (with logging & annotated output tracking)
# =========================================================================
def process_session_task(session_id: int, video_path: str, media_file_id: int = None):
    """Background task for processing the video and storing metrics."""
    db = database.SessionLocal()
    start_time = time.time()
    try:
        # Log: YOLO inference
        log_yolo = _log_step(db, session_id, "yolo_inference")
        shots, frames = cv_processor.process_video_inference(video_path)
        _complete_log(db, log_yolo, details={"total_frames": frames, "shots_detected": len(shots)})

        # Log: metric storage
        log_store = _log_step(db, session_id, "metric_storage")
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
                    "knee": s['knee_angle_at_impact'],
                    "hip_rotation": s.get('hip_angle', 0.0),
                    "shoulder_rotation": s.get('shoulder_angle', 0.0),
                    "separation": s.get('hip_shoulder_separation', 0.0)
                }
            )
            db.add(db_shot)
            db.flush()

            for risk in s['injury_risks']:
                db_flag = models.InjuryFlag(
                    shot_metric_id=db_shot.id,
                    type=risk['type'],
                    severity=risk['severity'],
                    message=risk['message'],
                    value=risk.get('value', 0.0)
                )
                db.add(db_flag)
        _complete_log(db, log_store, details={"shots_stored": len(shots)})

        # Mark session as done
        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if session:
            session.status = "done"
            session.processing_time_sec = round(time.time() - start_time, 2)
        db.commit()
        print(f"[OK] Session {session_id} processed: {len(shots)} shots.")
        
        # Firebase Sync (Optional cloud backup)
        if firebase_client.initialized:
            try:
                # 1. Upload original video
                remote_path = f"sessions/{session_id}/raw_{os.path.basename(video_path)}"
                fb_url = firebase_client.upload_file(video_path, remote_path)
                
                # 2. Sync session metadata to Firestore
                fb_data = {
                    "player_id": session.player_id,
                    "media_type": "video",
                    "status": "done",
                    "processed_at": session.processed_at.isoformat() if session.processed_at else None,
                    "original_filename": session.original_filename,
                    "cloud_url": fb_url,
                    "shots_count": len(shots)
                }
                firebase_client.save_session_data(session_id, fb_data)
                
                # 3. Save shot metrics to subcollection
                for i, s in enumerate(shots):
                    firebase_client.save_shot_metrics(session_id, i, s)
            except Exception as fbe:
                print(f"[Firebase] Sync error in session task: {fbe}")

        # Telegram Notification
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8669701587:AAFiRK40sur96_F82auBXGU106-E3mu6i1s")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2040084906")
        msg = f"🏏 *New Video Analysis Complete!*\n\nFile: `{session.original_filename}`\nDetected {len(shots)} shots.\nOpen the GameIQ app to view detailed biomechanics and injury flags."
        telegram_bot.send_telegram_alert(msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    except Exception as e:
        print(f"[ERROR] Session {session_id} failed: {e}")
        _log_step(db, session_id, "error", "failed", error_message=str(e))
        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if session:
            session.status = "error"
            session.error_message = str(e)
            session.processing_time_sec = round(time.time() - start_time, 2)
        db.commit()
    finally:
        db.close()


def process_image_task(session_id: int, image_path: str, media_file_id: int = None):
    """Background task for analysing a single image and storing metrics."""
    db = database.SessionLocal()
    start_time = time.time()
    try:
        # Log: YOLO inference
        log_yolo = _log_step(db, session_id, "yolo_inference")
        shots = cv_processor.process_image_inference(image_path)
        _complete_log(db, log_yolo, details={"poses_detected": len(shots)})

        # Log: metric storage
        log_store = _log_step(db, session_id, "metric_storage")
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
                    "knee": s['knee_angle_at_impact'],
                    "hip_rotation": s.get('hip_angle', 0.0),
                    "shoulder_rotation": s.get('shoulder_angle', 0.0),
                    "separation": s.get('hip_shoulder_separation', 0.0)
                }
            )
            db.add(db_shot)
            db.flush()

            for risk in s['injury_risks']:
                db_flag = models.InjuryFlag(
                    shot_metric_id=db_shot.id,
                    type=risk['type'],
                    severity=risk['severity'],
                    message=risk['message'],
                    value=risk.get('value', 0.0)
                )
                db.add(db_flag)
        _complete_log(db, log_store, details={"shots_stored": len(shots)})

        # Track annotated output if one was created by cv_processor
        annotated_path = image_path.rsplit('.', 1)[0] + "_annotated.jpg"
        if os.path.exists(annotated_path) and media_file_id:
            _save_annotated_output(db, media_file_id, session_id,
                                   "annotated_image", annotated_path)

        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if session:
            session.status = "done"
            session.processing_time_sec = round(time.time() - start_time, 2)
        db.commit()
        print(f"[OK] Image session {session_id} processed: {len(shots)} pose snapshots.")
        
        # Firebase Sync (Optional cloud backup)
        if firebase_client.initialized:
            try:
                # 1. Upload original image
                remote_path = f"sessions/{session_id}/raw_{os.path.basename(image_path)}"
                fb_url = firebase_client.upload_file(image_path, remote_path)
                
                # 2. Upload annotated image if exists
                if os.path.exists(annotated_path):
                    remote_ann_path = f"sessions/{session_id}/annotated_{os.path.basename(annotated_path)}"
                    firebase_client.upload_file(annotated_path, remote_ann_path)

                # 3. Sync to Firestore
                fb_data = {
                    "player_id": session.player_id,
                    "media_type": "image",
                    "status": "done",
                    "processed_at": session.processed_at.isoformat() if session.processed_at else None,
                    "cloud_url": fb_url,
                    "avg_score": avg_score
                }
                firebase_client.save_session_data(session_id, fb_data)
            except Exception as fbe:
                print(f"[Firebase] Sync error in image task: {fbe}")

        # Telegram Notification
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8669701587:AAFiRK40sur96_F82auBXGU106-E3mu6i1s")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2040084906")
        avg_score = sum(s['technique_score'] for s in shots) / len(shots) if shots else 0
        msg = f"📸 *New Pose Analysis Complete!*\n\nFile: `{session.original_filename}`\nOverall Tech Score: *{avg_score:.1f}/100*\nOpen the GameIQ app to view detailed biomechanics."
        telegram_bot.send_telegram_alert(msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    except Exception as e:
        print(f"[ERROR] Image session {session_id} failed: {e}")
        _log_step(db, session_id, "error", "failed", error_message=str(e))
        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if session:
            session.status = "error"
            session.error_message = str(e)
            session.processing_time_sec = round(time.time() - start_time, 2)
        db.commit()
    finally:
        db.close()


# =========================================================================
#  Session / Player Query Endpoints
# =========================================================================
@app.get("/players/{player_id}/sessions", response_model=List[schemas.SessionBase])
def list_player_sessions(player_id: int, db: Session = Depends(get_db)):
    return db.query(models.Session).filter(models.Session.player_id == player_id).order_by(models.Session.processed_at.desc()).all()

@app.get("/sessions/{session_id}/status")
def get_session_status(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "status": session.status, "shots_count": len(session.shots)}

@app.get("/sessions/{session_id}", response_model=schemas.SessionDetail)
def get_session_results(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# =========================================================================
#  Processing Log Endpoints
# =========================================================================
@app.get("/sessions/{session_id}/logs", response_model=List[schemas.ProcessingLogBase])
def get_session_logs(session_id: int, db: Session = Depends(get_db)):
    """Get the processing pipeline log for a session."""
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.processing_logs


# =========================================================================
#  Media File Endpoints (Gallery / Detail)
# =========================================================================
@app.get("/media-files/", response_model=List[schemas.MediaFileBase])
def list_media_files(
    media_type: Optional[str] = Query(None, description="Filter by 'video' or 'image'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List all uploaded media files with pagination and optional type filter."""
    q = db.query(models.MediaFile)
    if media_type:
        q = q.filter(models.MediaFile.media_type == media_type)
    return q.order_by(models.MediaFile.uploaded_at.desc()).offset(offset).limit(limit).all()


@app.get("/media-files/{file_id}", response_model=schemas.MediaFileDetail)
def get_media_file(file_id: int, db: Session = Depends(get_db)):
    """Get a single media file's full details including annotated outputs."""
    mf = db.query(models.MediaFile).filter(models.MediaFile.id == file_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Media file not found")
    return mf


@app.get("/media-files/by-uuid/{file_uuid}", response_model=schemas.MediaFileDetail)
def get_media_file_by_uuid(file_uuid: str, db: Session = Depends(get_db)):
    """Get a media file by its UUID."""
    mf = db.query(models.MediaFile).filter(models.MediaFile.file_uuid == file_uuid).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Media file not found")
    return mf


@app.get("/media-files/{file_id}/outputs", response_model=List[schemas.AnnotatedOutputBase])
def get_media_outputs(file_id: int, db: Session = Depends(get_db)):
    """List all annotated/processed outputs for a media file."""
    return db.query(models.AnnotatedOutput).filter(
        models.AnnotatedOutput.media_file_id == file_id
    ).all()


# =========================================================================
#  Dashboard / Stats Endpoint
# =========================================================================
@app.get("/dashboard/stats", response_model=schemas.ProcessingStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregate processing statistics for the dashboard."""
    total_uploads = db.query(func.count(models.MediaFile.id)).scalar() or 0
    total_images = db.query(func.count(models.MediaFile.id)).filter(
        models.MediaFile.media_type == "image").scalar() or 0
    total_videos = db.query(func.count(models.MediaFile.id)).filter(
        models.MediaFile.media_type == "video").scalar() or 0
    total_sessions = db.query(func.count(models.Session.id)).scalar() or 0
    completed = db.query(func.count(models.Session.id)).filter(
        models.Session.status == "done").scalar() or 0
    failed = db.query(func.count(models.Session.id)).filter(
        models.Session.status == "error").scalar() or 0
    processing = db.query(func.count(models.Session.id)).filter(
        models.Session.status == "processing").scalar() or 0
    total_shots = db.query(func.count(models.ShotMetric.id)).scalar() or 0
    avg_score = db.query(func.avg(models.ShotMetric.technique_score)).scalar()
    total_storage = db.query(func.sum(models.MediaFile.file_size_bytes)).scalar() or 0

    return schemas.ProcessingStats(
        total_uploads=total_uploads,
        total_images=total_images,
        total_videos=total_videos,
        total_sessions=total_sessions,
        completed_sessions=completed,
        failed_sessions=failed,
        processing_sessions=processing,
        total_shots_analyzed=total_shots,
        avg_technique_score=round(avg_score, 1) if avg_score else None,
        total_storage_bytes=total_storage
    )


# =========================================================================
#  Gallery Endpoint — player-specific media
# =========================================================================
@app.get("/players/{player_id}/gallery")
def player_gallery(player_id: int, db: Session = Depends(get_db)):
    """Return all media files uploaded by a player, with session status."""
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    sessions = db.query(models.Session).filter(
        models.Session.player_id == player_id
    ).order_by(models.Session.processed_at.desc()).all()

    gallery = []
    for s in sessions:
        mf = s.media_file
        gallery.append({
            "session_id": s.id,
            "media_file_id": mf.id if mf else None,
            "original_filename": s.original_filename,
            "media_type": s.media_type,
            "status": s.status,
            "processed_at": s.processed_at.isoformat() if s.processed_at else None,
            "processing_time_sec": s.processing_time_sec,
            "shots_count": len(s.shots),
            "media_url": f"/media/{mf.file_uuid}.{mf.extension}" if mf else None,
            "thumbnail_url": f"/media/thumbnails/{mf.file_uuid}_thumb.jpg" if mf and mf.thumbnail_path else None,
            "file_size_bytes": mf.file_size_bytes if mf else 0,
            "width": mf.width if mf else None,
            "height": mf.height if mf else None,
            "duration_sec": mf.duration_sec if mf else None,
        })

    return {"player_id": player_id, "player_name": player.name, "gallery": gallery}


# --- Chat to Telegram Endpoint ---
class ChatMessage(BaseModel):
    message: str

@app.post("/telegram-chat")
def send_chat_to_telegram(chat: ChatMessage):
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8669701587:AAFiRK40sur96_F82auBXGU106-E3mu6i1s")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2040084906")
    telegram_bot.send_telegram_alert(f"💬 *GameIQ Web App Message:*\n{chat.message}", TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    return {"status": "sent"}

# --- OpenAI Chat GPT Endpoint ---
class GPTChatRequest(BaseModel):
    message: str
    session_id: int = None

@app.post("/chat")
def chat_with_gpt(req: GPTChatRequest, db: Session = Depends(get_db)):
    context_data = {"player": None, "current_session": None, "career_stats": None}
    
    if req.session_id:
        session = db.query(models.Session).filter(models.Session.id == req.session_id).first()
        if session:
            # Current Session context
            context_data["current_session"] = {
                "id": session.id,
                "media_type": session.media_type,
                "shots": [{"technique_score": s.technique_score, "swing_speed": s.swing_speed_max} for s in session.shots],
                "filename": session.original_filename,
                "file_path": os.path.join(UPLOAD_DIR, os.path.basename(session.video_path))
            }
            
            # Player context
            player = session.player
            if player:
                context_data["player"] = {"name": player.name, "email": player.email}
                
                # Career / Aggregate Statistics
                all_sessions = player.sessions
                all_shots = [shot for s in all_sessions for shot in s.shots]
                
                context_data["career_stats"] = {
                    "total_sessions": len(all_sessions),
                    "total_shots_analyzed": len(all_shots),
                    "avg_career_score": sum(sh.technique_score for sh in all_shots) / len(all_shots) if all_shots else 0,
                    "max_swing_speed": max((sh.swing_speed_max for sh in all_shots), default=0)
                }
            
    response = openai_bot.get_gpt_response(req.message, context_data)
    
    # Also forward to telegram for monitoring
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8669701587:AAFiRK40sur96_F82auBXGU106-E3mu6i1s")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2040084906")
    telegram_bot.send_telegram_alert(f"🤖 *GPT Response to User ({context_data['player']['name'] if context_data['player'] else 'Unknown'}):*\n*User:* {req.message}\n*GPT:* {response}", TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    return {"response": response}

# ✅ Mount LAST — StaticFiles intercepts all matching paths,
# so it must be registered after all API routes
app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media_files")

# Mount FRONTEND if it exists
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
