"""
media_utils.py — Utilities for extracting metadata from uploaded images & videos
and generating thumbnails for the media gallery.
"""
import os
import cv2
import hashlib
import datetime
from typing import Optional, Dict, Any


def get_file_hash(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_image_metadata(file_path: str) -> Dict[str, Any]:
    """Extract width, height from an image file."""
    meta: Dict[str, Any] = {"width": None, "height": None}
    try:
        img = cv2.imread(file_path)
        if img is not None:
            h, w = img.shape[:2]
            meta["width"] = w
            meta["height"] = h
    except Exception as e:
        print(f"[media_utils] Could not read image metadata: {e}")
    return meta


def get_video_metadata(file_path: str) -> Dict[str, Any]:
    """Extract width, height, fps, duration, total_frames from a video file."""
    meta: Dict[str, Any] = {
        "width": None, "height": None,
        "fps": None, "duration_sec": None, "total_frames": None
    }
    try:
        cap = cv2.VideoCapture(file_path)
        if cap.isOpened():
            meta["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            meta["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            meta["fps"] = cap.get(cv2.CAP_PROP_FPS) or None
            meta["total_frames"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if meta["fps"] and meta["total_frames"]:
                meta["duration_sec"] = round(meta["total_frames"] / meta["fps"], 2)
            cap.release()
    except Exception as e:
        print(f"[media_utils] Could not read video metadata: {e}")
    return meta


def generate_thumbnail(file_path: str, media_type: str,
                       thumb_dir: str = "uploads/thumbnails",
                       thumb_size: tuple = (320, 240)) -> Optional[str]:
    """
    Generate a JPEG thumbnail for an image or video.
    Returns the thumbnail file path, or None on failure.
    """
    os.makedirs(thumb_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb.jpg")

    try:
        if media_type == "image":
            img = cv2.imread(file_path)
            if img is None:
                return None
            resized = cv2.resize(img, thumb_size, interpolation=cv2.INTER_AREA)
            cv2.imwrite(thumb_path, resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return thumb_path

        elif media_type == "video":
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return None
            # Grab a frame ~10% into the video for a meaningful thumbnail
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            target_frame = max(1, int(total * 0.1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            resized = cv2.resize(frame, thumb_size, interpolation=cv2.INTER_AREA)
            cv2.imwrite(thumb_path, resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return thumb_path

    except Exception as e:
        print(f"[media_utils] Thumbnail generation failed: {e}")
    return None


def get_file_size(file_path: str) -> int:
    """Return file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0
