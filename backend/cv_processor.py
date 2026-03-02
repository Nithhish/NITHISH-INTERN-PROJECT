import cv2
import os
from time import time
from ultralytics import YOLO
from analysis import get_pose_metrics
from shot_detector import ShotDetector

# Load model once at module level for efficiency
pose_model = YOLO('yolov8n-pose.pt')

def process_video_inference(video_path: str):
    """
    Core CV processing loop for the backend.
    Processes a video and returns shot data.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    detector = ShotDetector(fps=fps)
    
    frame_count = 0
    shots_results = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # YOLO Detection
        results = pose_model(frame, verbose=False, conf=0.4)
        
        batsman_metrics = None
        bowler_metrics = None
        
        if len(results) > 0 and results[0].keypoints is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            kpts = results[0].keypoints.data.cpu().numpy()
            
            # Identify batsman (rightmost)/bowler (leftmost)
            if len(boxes) > 0:
                indices = list(range(len(boxes)))
                indices.sort(key=lambda i: boxes[i][0]) # Sort by X
                
                # Simple logic for this specific camera angle
                b_idx = indices[-1]  # Rightmost is batsman
                bow_idx = indices[0] if len(indices) > 1 else None
                
                # Convert to our metric format
                def to_mp_format(raw_kpts):
                    return [{"x": float(k[0]/frame.shape[1]), "y": float(k[1]/frame.shape[0]), "visibility": float(k[2])} for k in raw_kpts]

                batsman_metrics = get_pose_metrics(to_mp_format(kpts[b_idx]), fps=fps)
                if bow_idx is not None:
                    bowler_metrics = get_pose_metrics(to_mp_format(kpts[bow_idx]), fps=fps)

        # Detector logic
        shot = detector.process_frame(batsman_metrics, bowler_metrics, frame_idx=frame_count)
        if shot:
            shots_results.append(shot.to_dict())
            
        frame_count += 1
        
    cap.release()
    return shots_results, frame_count
