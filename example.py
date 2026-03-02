import cv2
import json
import os
import sys
import numpy as np
from time import time
from analysis import get_pose_metrics
from shot_detector import ShotDetector

print("[INFO] Initializing Multi-Person Skeleton Tracking...")

# -------------------------------
# YOLO Pose Setup (built-in skeleton detection)
# -------------------------------
from ultralytics import YOLO

# YOLOv8 Pose model — detects multiple people + 17 keypoints each
pose_model = YOLO("yolov8n-pose.pt")
print("[OK] YOLOv8-Pose model loaded (multi-person skeleton detection)")

# COCO Pose keypoint names (17 keypoints)
COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# COCO Pose skeleton connections
COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),           # Head
    (5, 6),                                      # Shoulders
    (5, 7), (7, 9),                              # Left arm
    (6, 8), (8, 10),                             # Right arm
    (5, 11), (6, 12),                            # Torso
    (11, 12),                                    # Hips
    (11, 13), (13, 15),                          # Left leg
    (12, 14), (14, 16),                          # Right leg
]

# Map COCO 17-keypoint indices to MediaPipe-like 33-keypoint format
# for compatibility with analysis.py
COCO_TO_MP = {
    0: 0,    # nose
    1: 2,    # left_eye → left_eye (inner)
    2: 5,    # right_eye → right_eye (inner)
    3: 7,    # left_ear
    4: 8,    # right_ear
    5: 11,   # left_shoulder
    6: 12,   # right_shoulder
    7: 13,   # left_elbow
    8: 14,   # right_elbow
    9: 15,   # left_wrist
    10: 16,  # right_wrist
    11: 23,  # left_hip
    12: 24,  # right_hip
    13: 25,  # left_knee
    14: 26,  # right_knee
    15: 27,  # left_ankle
    16: 28,  # right_ankle
}

# -------------------------------
# Video Sources
# -------------------------------
VIDEO_SOURCES = [
    r"E:\my Pro\day 1 and 2 and 3,4\cricket.mp4",
    r"videoplayback.mp4",
    0
]

# -------------------------------
# Output Directory
# -------------------------------
keypoints_dir = "keypoints_json"
os.makedirs(keypoints_dir, exist_ok=True)

# -------------------------------
# Open Video Source
# -------------------------------
cap = None

for source in VIDEO_SOURCES:
    test_cap = cv2.VideoCapture(source)
    if test_cap.isOpened():
        cap = test_cap
        print(f"[OK] Video source opened: {source}")
        break
    test_cap.release()

if cap is None:
    print("[ERROR] No video source available")
    sys.exit(0)

# -------------------------------
# Video Properties
# -------------------------------
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"[OK] Resolution: {width}x{height} @ {fps:.1f} FPS")
print(f"[OK] JSON Output Folder: {os.path.abspath(keypoints_dir)}")
print("[INFO] Tracking: Batsman (GREEN) + Bowler (ORANGE)")
print("[INFO] Press 'q' to quit")
print("-" * 60)

# -------------------------------
# Color Schemes
# -------------------------------
COLORS = {
    "Batsman": {
        "skeleton": (0, 255, 0),       # Green
        "bbox": (0, 255, 0),
        "point": (0, 200, 0),
    },
    "Bowler": {
        "skeleton": (0, 165, 255),     # Orange
        "bbox": (0, 165, 255),
        "point": (0, 140, 255),
    },
}

# -------------------------------
# Convert YOLO 17-keypoint to MediaPipe 33-keypoint format
# (for compatibility with analysis.py)
# -------------------------------
def yolo_kp_to_mediapipe(kp_array, frame_w, frame_h):
    """Convert YOLO 17 keypoints to MediaPipe-compatible 33 keypoint dict list."""
    mp_keypoints = []
    for i in range(33):
        mp_keypoints.append({
            "x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.0
        })

    for coco_idx, mp_idx in COCO_TO_MP.items():
        if coco_idx < len(kp_array):
            x, y, conf = kp_array[coco_idx]
            mp_keypoints[mp_idx] = {
                "x": float(x / frame_w),
                "y": float(y / frame_h),
                "z": 0.0,
                "visibility": float(conf)
            }

    return mp_keypoints

# -------------------------------
# Classify players as Batsman/Bowler
# -------------------------------
def classify_players(boxes, frame_w):
    """
    Heuristic: 
    - Rightmost person → Batsman (at crease)
    - Leftmost person → Bowler (approaching)
    Adjust if your camera angle is different.
    """
    if len(boxes) == 0:
        return []
    if len(boxes) == 1:
        return [("Batsman", 0)]

    # Sort by x-center of bounding box
    centers = []
    for i, box in enumerate(boxes):
        x_center = (box[0] + box[2]) / 2
        centers.append((x_center, i))
    centers.sort()

    labels = []
    labels.append(("Bowler", centers[0][1]))
    labels.append(("Batsman", centers[1][1]))

    for i in range(2, len(centers)):
        labels.append((f"Player_{i+1}", centers[i][1]))

    return labels

# -------------------------------
# Draw skeleton on frame
# -------------------------------
def draw_skeleton(frame, kp_array, color_skeleton, color_point, min_conf=0.3):
    """Draw COCO skeleton connections and keypoints on frame."""
    # Draw connections
    for (i, j) in COCO_SKELETON:
        if i < len(kp_array) and j < len(kp_array):
            x1, y1, c1 = kp_array[i]
            x2, y2, c2 = kp_array[j]
            if c1 > min_conf and c2 > min_conf:
                pt1 = (int(x1), int(y1))
                pt2 = (int(x2), int(y2))
                cv2.line(frame, pt1, pt2, color_skeleton, 3, cv2.LINE_AA)

    # Draw keypoints
    for i, (x, y, c) in enumerate(kp_array):
        if c > min_conf:
            pt = (int(x), int(y))
            cv2.circle(frame, pt, 5, color_point, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 6, (255, 255, 255), 1, cv2.LINE_AA)

# -------------------------------
# Main Loop
# -------------------------------
frame_count = 0
prev_keypoints = {"Batsman": None, "Bowler": None}
start_time = time()

# Initialize Shot Detection Engine
shot_detector = ShotDetector(fps=fps)
shot_flash_counter = 0  # For flashing "SHOT!" indicator
last_shot_event = None

print("[INFO] Starting multi-person skeleton tracking + shot detection...")
print("=" * 60)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] End of video")
            break

        frame_h, frame_w = frame.shape[:2]
        players_data = []

        # ---------------------------
        # YOLO Pose Detection (multi-person)
        # ---------------------------
        results = pose_model(frame, verbose=False, conf=0.4)

        detected_boxes = []
        detected_keypoints = []

        for result in results:
            if result.keypoints is not None and result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                kps = result.keypoints.data.cpu().numpy()  # (N, 17, 3)

                for i in range(len(boxes)):
                    if confs[i] >= 0.4:
                        detected_boxes.append(boxes[i])
                        detected_keypoints.append(kps[i])

        # Classify detected persons
        labeled = classify_players(detected_boxes, frame_w)
        player_count = len(labeled)

        # Process each player
        for label, idx in labeled:
            bbox = detected_boxes[idx]
            kp_array = detected_keypoints[idx]  # (17, 3) — x, y, conf
            x1, y1, x2, y2 = bbox.astype(int)

            # Get color scheme
            colors = COLORS.get(label, COLORS["Batsman"])

            # Draw skeleton
            draw_skeleton(frame, kp_array, colors["skeleton"], colors["point"])

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), colors["bbox"], 2)

            # Draw label background + text
            label_w = len(label) * 14 + 10
            label_h = 28
            label_y = max(y1 - label_h, 0)
            cv2.rectangle(frame, (x1, label_y), (x1 + label_w, y1), colors["bbox"], -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

            # Convert to MediaPipe format for analysis
            mp_keypoints = yolo_kp_to_mediapipe(kp_array, frame_w, frame_h)

            # Calculate biomechanical metrics
            prev_kp = prev_keypoints.get(label, None)
            metrics = get_pose_metrics(mp_keypoints, prev_kp, fps)
            prev_keypoints[label] = mp_keypoints

            players_data.append({
                "label": label,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "keypoints_coco": [{"x": float(k[0]), "y": float(k[1]), "conf": float(k[2])} for k in kp_array],
                "keypoints_mp33": mp_keypoints,
                "metrics": metrics
            })

        # ---------------------------
        # Shot Detection Engine
        # ---------------------------
        batsman_metrics = {}
        bowler_metrics = {}
        for pdata in players_data:
            if pdata["label"] == "Batsman":
                batsman_metrics = pdata.get("metrics", {})
            elif pdata["label"] == "Bowler":
                bowler_metrics = pdata.get("metrics", {})

        shot_event = shot_detector.process_frame(batsman_metrics, bowler_metrics, frame_idx=frame_count)

        if shot_event:
            last_shot_event = shot_event
            shot_flash_counter = int(fps * 1.5)  # Flash for 1.5 seconds
            print(f"  \U0001F3CF SHOT #{shot_event.shot_id} | "
                  f"Speed: {shot_event.swing_speed_max:.0f} deg/s | "
                  f"Duration: {shot_event.swing_duration:.3f}s | "
                  f"Reaction: {shot_event.reaction_time:.3f}s | "
                  f"Stability: {shot_event.stability_deviation:.4f} | "
                  f"Confidence: {shot_event.confidence:.0%}")

        # ---------------------------
        # Save JSON
        # ---------------------------
        shot_hud = shot_detector.get_hud_status()

        json_data = {
            "frame": frame_count,
            "timestamp": frame_count / fps,
            "players_detected": player_count,
            "players": players_data,
            "shot_detection": shot_hud,
        }

        if shot_event:
            json_data["shot_event"] = shot_event.to_dict()

        json_path = os.path.join(
            keypoints_dir,
            f"frame_{frame_count:06d}.json"
        )

        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)

        frame_count += 1

        # ---------------------------
        # HUD Overlay
        # ---------------------------
        # Top info bar
        cv2.rectangle(frame, (0, 0), (300, 70), (0, 0, 0), -1)
        cv2.putText(frame, f"Frame: {frame_count}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Players: {player_count}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Metrics panel for each player
        y_offset = 90
        for pdata in players_data:
            label = pdata["label"]
            metrics = pdata.get("metrics", {})
            color = COLORS.get(label, COLORS["Batsman"])["skeleton"]

            cv2.putText(frame, f"[ {label} ]", (10, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            y_offset += 22

            for k in ['right_elbow_angle', 'right_knee_angle', 'bat_angular_velocity']:
                if k in metrics:
                    val = metrics[k]
                    short_name = k.replace('_', ' ').title()
                    cv2.putText(frame, f"  {short_name}: {val:.1f}", (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
                    y_offset += 17
            y_offset += 8

        # Legend (top-right)
        cv2.rectangle(frame, (frame_w - 230, 0), (frame_w, 65), (0, 0, 0), -1)
        cv2.putText(frame, "GREEN = Batsman", (frame_w - 220, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(frame, "ORANGE = Bowler", (frame_w - 220, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

        # ---------------------------
        # Shot Detection HUD
        # ---------------------------
        shot_hud = shot_detector.get_hud_status()

        # Shot counter
        total_shots = shot_hud.get('total_shots', 0)
        cv2.putText(frame, f"Shots: {total_shots}", (frame_w - 220, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # Swing indicator
        if shot_hud.get('in_swing', False):
            cv2.rectangle(frame, (frame_w - 230, 95), (frame_w, 125), (0, 0, 200), -1)
            cv2.putText(frame, "SWINGING...", (frame_w - 220, 118),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Flash "SHOT DETECTED!" when a shot is found
        if shot_flash_counter > 0:
            shot_flash_counter -= 1
            # Flashing effect
            if shot_flash_counter % 6 < 4:
                cv2.rectangle(frame, (frame_w // 2 - 160, 5), (frame_w // 2 + 160, 45), (0, 0, 220), -1)
                cv2.putText(frame, "SHOT DETECTED!", (frame_w // 2 - 140, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

            # Show last shot details
            if last_shot_event:
                panel_y = frame_h - 100
                cv2.rectangle(frame, (0, panel_y), (350, frame_h), (0, 0, 0), -1)
                cv2.putText(frame, f"Shot #{last_shot_event.shot_id}", (10, panel_y + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                cv2.putText(frame, f"Speed: {last_shot_event.swing_speed_max:.0f} deg/s", (10, panel_y + 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, f"Duration: {last_shot_event.swing_duration:.3f}s", (10, panel_y + 57),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, f"Reaction: {last_shot_event.reaction_time:.3f}s", (10, panel_y + 74),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, f"Stability: {last_shot_event.stability_deviation:.4f}", (10, panel_y + 91),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, f"Conf: {last_shot_event.confidence:.0%}", (200, panel_y + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        cv2.imshow("Cricket Skeleton Tracking - Batsman & Bowler", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[INFO] User quit")
            break

        # FPS logging
        if frame_count % 30 == 0:
            elapsed = time() - start_time
            print(f"[INFO] {frame_count} frames | {frame_count/max(1,elapsed):.1f} FPS | Players: {player_count}")

except Exception as e:
    print(f"[ERROR] Runtime error: {e}")
    import traceback
    traceback.print_exc()

finally:
    cap.release()
    cv2.destroyAllWindows()

# -------------------------------
# Shot Detection Summary
# -------------------------------
summary = shot_detector.get_summary()
summary_path = os.path.join(keypoints_dir, "shot_detection_summary.json")
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)

# -------------------------------
# Final Report
# -------------------------------
print("\n" + "=" * 60)
print("\U0001F3CF CRICKET SHOT DETECTION — FINAL REPORT")
print("=" * 60)
print(f"  Total Frames Processed: {frame_count}")
print(f"  JSON Files Created:     {frame_count}")
print(f"  Output Folder:          {os.path.abspath(keypoints_dir)}")
print(f"  Players Tracked:        Batsman (Green) + Bowler (Orange)")
print("-" * 60)
print(f"  Total Shots Detected:   {summary['total_shots']}")
print(f"  Avg Swing Speed:        {summary['avg_swing_speed']} deg/s")
print(f"  Max Swing Speed:        {summary['max_swing_speed']} deg/s")
print(f"  Avg Swing Duration:     {summary['avg_swing_duration']}s")
print(f"  Avg Reaction Time:      {summary['avg_reaction_time']}s")
print(f"  Avg Stability Dev:      {summary['avg_stability_deviation']}")
print("-" * 60)

for shot in summary.get('shots', []):
    print(f"  Shot #{shot['shot_id']}:")
    print(f"    Frames: {shot['swing_start_frame']} → {shot['impact_frame']} → {shot['swing_end_frame']}")
    print(f"    Speed:  {shot['swing_speed_max_deg_per_sec']} deg/s max | {shot['swing_speed_avg_deg_per_sec']} avg")
    print(f"    Duration: {shot['swing_duration_sec']}s | Reaction: {shot['reaction_time_sec']}s")
    print(f"    Stability: {shot['stability_deviation']} | Confidence: {shot['confidence']:.0%}")

print("=" * 60)
print(f"  Summary saved to: {summary_path}")
print("=" * 60)