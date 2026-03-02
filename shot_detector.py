"""
Shot Detection Engine for Cricket Training Analysis
=====================================================
Detects batting shots by analyzing multi-frame pose data:
  - Impact Frame Detection (bat-ball contact)
  - Swing Start & End Identification
  - Swing Speed Computation
  - Reaction Time Estimation
  - Stability Deviation Analysis

Usage:
  Integrated into example.py for real-time detection, or run standalone
  to analyze existing JSON keypoint files.
"""

import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ============================================================
# Shot Data Structure
# ============================================================
@dataclass
class ShotEvent:
    """Represents a detected batting shot."""
    shot_id: int = 0
    swing_start_frame: int = 0
    swing_end_frame: int = 0
    impact_frame: int = 0
    swing_start_time: float = 0.0
    swing_end_time: float = 0.0
    impact_time: float = 0.0
    swing_duration: float = 0.0           # seconds
    swing_speed_max: float = 0.0          # deg/sec (peak angular velocity)
    swing_speed_avg: float = 0.0          # deg/sec (average angular velocity)
    hands_speed_max: float = 0.0          # normalized units/sec
    reaction_time: float = 0.0            # seconds (bowler release → swing start)
    stability_deviation: float = 0.0      # COG deviation during swing
    cog_path: List[List[float]] = field(default_factory=list)
    elbow_angle_at_impact: float = 0.0
    knee_angle_at_impact: float = 0.0
    shoulder_rotation_max: float = 0.0
    hip_rotation_max: float = 0.0
    confidence: float = 0.0              # 0-1 confidence of detection

    def to_dict(self):
        return {
            "shot_id": self.shot_id,
            "swing_start_frame": self.swing_start_frame,
            "swing_end_frame": self.swing_end_frame,
            "impact_frame": self.impact_frame,
            "swing_start_time": round(self.swing_start_time, 4),
            "swing_end_time": round(self.swing_end_time, 4),
            "impact_time": round(self.impact_time, 4),
            "swing_duration_sec": round(self.swing_duration, 4),
            "swing_speed_max_deg_per_sec": round(self.swing_speed_max, 2),
            "swing_speed_avg_deg_per_sec": round(self.swing_speed_avg, 2),
            "hands_speed_max": round(self.hands_speed_max, 4),
            "reaction_time_sec": round(self.reaction_time, 4),
            "stability_deviation": round(self.stability_deviation, 6),
            "elbow_angle_at_impact": round(self.elbow_angle_at_impact, 2),
            "knee_angle_at_impact": round(self.knee_angle_at_impact, 2),
            "shoulder_rotation_max": round(self.shoulder_rotation_max, 2),
            "hip_rotation_max": round(self.hip_rotation_max, 2),
            "confidence": round(self.confidence, 3),
        }


# ============================================================
# Bowler Event (for reaction time calculation)
# ============================================================
@dataclass
class BowlerRelease:
    """Detected bowler ball release moment."""
    frame: int = 0
    time: float = 0.0
    wrist_height: float = 0.0        # y-coordinate of wrist at release


# ============================================================
# Shot Detection Engine
# ============================================================
class ShotDetector:
    """
    Real-time shot detection engine that processes frame-by-frame metrics
    and detects batting shots using velocity thresholds and signal analysis.
    """

    def __init__(self, fps=25.0, config=None):
        self.fps = fps
        self.dt = 1.0 / max(fps, 1.0)

        # --- Configuration ---
        cfg = config or {}
        # Thresholds for swing detection
        self.swing_velocity_threshold = cfg.get('swing_velocity_threshold', 150.0)    # deg/sec to detect swing
        self.swing_end_velocity = cfg.get('swing_end_velocity', 50.0)                 # deg/sec swing ended
        self.min_swing_frames = cfg.get('min_swing_frames', 3)                        # minimum frames for valid swing
        self.max_swing_frames = cfg.get('max_swing_frames', int(fps * 1.5))           # max ~1.5 sec swing
        self.cooldown_frames = cfg.get('cooldown_frames', int(fps * 0.5))             # 0.5 sec between shots

        # Bowler release detection
        self.bowler_wrist_rise_threshold = cfg.get('bowler_wrist_rise_threshold', 0.15)
        self.bowler_release_velocity_threshold = cfg.get('bowler_release_velocity_threshold', 100.0)

        # --- State ---
        self.frame_count = 0
        self.shot_count = 0
        self.detected_shots: List[ShotEvent] = []

        # Batsman tracking buffers
        self.bat_velocity_history = deque(maxlen=int(fps * 3))     # 3 seconds history
        self.hands_velocity_history = deque(maxlen=int(fps * 3))
        self.cog_history = deque(maxlen=int(fps * 3))
        self.metrics_history = deque(maxlen=int(fps * 3))

        # Bowler tracking buffers
        self.bowler_wrist_y_history = deque(maxlen=int(fps * 2))
        self.bowler_velocity_history = deque(maxlen=int(fps * 2))
        self.last_bowler_release: Optional[BowlerRelease] = None

        # Swing state machine
        self.in_swing = False
        self.swing_start_frame = 0
        self.swing_metrics_buffer = []
        self.cooldown_counter = 0

        # Running statistics for adaptive thresholds
        self._velocity_samples = deque(maxlen=int(fps * 10))

    # --------------------------------------------------------
    # Process a single frame's metrics (call every frame)
    # --------------------------------------------------------
    def process_frame(self, batsman_metrics: Dict, bowler_metrics: Optional[Dict] = None,
                      frame_idx: int = -1) -> Optional[ShotEvent]:
        """
        Process one frame of metrics. Returns a ShotEvent if a shot is detected.

        Args:
            batsman_metrics: Dict from get_pose_metrics() for the batsman
            bowler_metrics: Dict from get_pose_metrics() for the bowler (optional)
            frame_idx: Current frame index

        Returns:
            ShotEvent if a shot was just completed, else None
        """
        if frame_idx >= 0:
            self.frame_count = frame_idx
        else:
            self.frame_count += 1

        # Cooldown between shots
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1

        if not batsman_metrics:
            return None

        # Extract key velocities
        bat_vel = batsman_metrics.get('bat_angular_velocity', 0.0)
        hands_vel = batsman_metrics.get('hands_velocity', 0.0)
        cog_x = batsman_metrics.get('cog_x', 0.5)
        cog_y = batsman_metrics.get('cog_y', 0.5)

        # Store in buffers
        self.bat_velocity_history.append(bat_vel)
        self.hands_velocity_history.append(hands_vel)
        self.cog_history.append([cog_x, cog_y])
        self.metrics_history.append(batsman_metrics)
        self._velocity_samples.append(bat_vel)

        # Process bowler for reaction time
        if bowler_metrics:
            self._process_bowler(bowler_metrics)

        # --- Swing Detection State Machine ---
        detected_shot = None

        if not self.in_swing:
            # Check for swing start
            if bat_vel >= self.swing_velocity_threshold and self.cooldown_counter == 0:
                self.in_swing = True
                self.swing_start_frame = self.frame_count
                self.swing_metrics_buffer = [batsman_metrics]

        else:
            # We're in a swing — accumulate data
            self.swing_metrics_buffer.append(batsman_metrics)
            swing_frames = self.frame_count - self.swing_start_frame

            # Check for swing end conditions
            swing_ended = False

            if bat_vel < self.swing_end_velocity and swing_frames >= self.min_swing_frames:
                swing_ended = True
            elif swing_frames >= self.max_swing_frames:
                swing_ended = True

            if swing_ended:
                # Build the shot event
                detected_shot = self._build_shot_event()
                self.in_swing = False
                self.swing_metrics_buffer = []
                self.cooldown_counter = self.cooldown_frames

        return detected_shot

    # --------------------------------------------------------
    # Bowler release detection
    # --------------------------------------------------------
    def _process_bowler(self, bowler_metrics: Dict):
        """Detect bowler's ball release point for reaction time calculation."""
        wrist_y = bowler_metrics.get('right_wrist_y', 0.5)
        wrist_vel = bowler_metrics.get('right_wrist_velocity', 0.0)

        self.bowler_wrist_y_history.append(wrist_y)
        self.bowler_velocity_history.append(wrist_vel)

        # Detect release: wrist reaches highest point (lowest y value) with high velocity
        if len(self.bowler_wrist_y_history) >= 3:
            recent_y = list(self.bowler_wrist_y_history)
            # Wrist at peak (y was decreasing, now increasing) = release point
            if (len(recent_y) >= 3 and
                recent_y[-2] < recent_y[-3] and
                recent_y[-1] > recent_y[-2] and
                recent_y[-2] < (0.5 - self.bowler_wrist_rise_threshold) and
                wrist_vel > self.bowler_release_velocity_threshold):

                self.last_bowler_release = BowlerRelease(
                    frame=self.frame_count - 1,
                    time=(self.frame_count - 1) * self.dt,
                    wrist_height=recent_y[-2]
                )

    # --------------------------------------------------------
    # Build ShotEvent from accumulated swing data
    # --------------------------------------------------------
    def _build_shot_event(self) -> ShotEvent:
        """Construct a ShotEvent from the current swing buffer."""
        self.shot_count += 1

        swing_start = self.swing_start_frame
        swing_end = self.frame_count
        swing_frames = swing_end - swing_start

        # Extract velocity profile during swing
        velocities = [m.get('bat_angular_velocity', 0.0) for m in self.swing_metrics_buffer]
        hands_vels = [m.get('hands_velocity', 0.0) for m in self.swing_metrics_buffer]
        cog_xs = [m.get('cog_x', 0.5) for m in self.swing_metrics_buffer]
        cog_ys = [m.get('cog_y', 0.5) for m in self.swing_metrics_buffer]
        shoulder_rots = [m.get('shoulder_rotation_velocity', 0.0) for m in self.swing_metrics_buffer]
        hip_rots = [m.get('hip_rotation_velocity', 0.0) for m in self.swing_metrics_buffer]

        # --- Impact Frame: frame with peak velocity ---
        peak_idx = int(np.argmax(velocities))
        impact_frame = swing_start + peak_idx

        # --- Swing Speed ---
        swing_speed_max = float(np.max(velocities)) if velocities else 0.0
        swing_speed_avg = float(np.mean(velocities)) if velocities else 0.0
        hands_speed_max = float(np.max(hands_vels)) if hands_vels else 0.0

        # --- Swing Duration ---
        swing_duration = swing_frames * self.dt

        # --- Reaction Time ---
        reaction_time = 0.0
        if self.last_bowler_release and self.last_bowler_release.frame < swing_start:
            reaction_time = (swing_start - self.last_bowler_release.frame) * self.dt

        # --- Stability Deviation (COG variance during swing) ---
        cog_points = np.array([[x, y] for x, y in zip(cog_xs, cog_ys)])
        if len(cog_points) > 1:
            cog_mean = np.mean(cog_points, axis=0)
            stability_deviation = float(np.mean(np.linalg.norm(cog_points - cog_mean, axis=1)))
        else:
            stability_deviation = 0.0

        # --- Angles at impact ---
        impact_metrics = self.swing_metrics_buffer[peak_idx] if peak_idx < len(self.swing_metrics_buffer) else {}
        elbow_at_impact = impact_metrics.get('right_elbow_angle', 0.0)
        knee_at_impact = impact_metrics.get('right_knee_angle', 0.0)

        # --- Rotation maximums ---
        shoulder_rot_max = float(np.max(shoulder_rots)) if shoulder_rots else 0.0
        hip_rot_max = float(np.max(hip_rots)) if hip_rots else 0.0

        # --- Confidence score ---
        confidence = self._compute_confidence(swing_speed_max, swing_frames, stability_deviation)

        # --- COG path ---
        cog_path = [[float(x), float(y)] for x, y in zip(cog_xs, cog_ys)]

        shot = ShotEvent(
            shot_id=self.shot_count,
            swing_start_frame=swing_start,
            swing_end_frame=swing_end,
            impact_frame=impact_frame,
            swing_start_time=swing_start * self.dt,
            swing_end_time=swing_end * self.dt,
            impact_time=impact_frame * self.dt,
            swing_duration=swing_duration,
            swing_speed_max=swing_speed_max,
            swing_speed_avg=swing_speed_avg,
            hands_speed_max=hands_speed_max,
            reaction_time=reaction_time,
            stability_deviation=stability_deviation,
            cog_path=cog_path,
            elbow_angle_at_impact=elbow_at_impact,
            knee_angle_at_impact=knee_at_impact,
            shoulder_rotation_max=shoulder_rot_max,
            hip_rotation_max=hip_rot_max,
            confidence=confidence,
        )

        self.detected_shots.append(shot)
        return shot

    # --------------------------------------------------------
    # Confidence scoring
    # --------------------------------------------------------
    def _compute_confidence(self, peak_velocity, swing_frames, stability):
        """
        Compute confidence that this is a genuine batting shot.
        Based on:
          - Peak velocity (higher = more likely a real shot)
          - Swing duration (too short/long = less likely)
          - Stability (reasonable stability expected)
        """
        score = 0.0

        # Velocity score (0-0.5)
        if peak_velocity > 300:
            score += 0.5
        elif peak_velocity > 200:
            score += 0.35
        elif peak_velocity > self.swing_velocity_threshold:
            score += 0.2

        # Duration score (0-0.3): ideal swing is 0.2-0.8 seconds
        duration = swing_frames * self.dt
        if 0.15 <= duration <= 1.0:
            score += 0.3
        elif 0.1 <= duration <= 1.5:
            score += 0.15

        # Stability score (0-0.2): some movement expected but not too much
        if stability < 0.05:
            score += 0.2
        elif stability < 0.1:
            score += 0.1

        return min(score, 1.0)

    # --------------------------------------------------------
    # Get adaptive threshold based on running stats
    # --------------------------------------------------------
    def get_adaptive_threshold(self):
        """Calculate adaptive swing threshold based on recent velocity data."""
        if len(self._velocity_samples) < 30:
            return self.swing_velocity_threshold

        samples = np.array(self._velocity_samples)
        mean_vel = np.mean(samples)
        std_vel = np.std(samples)

        # Swing threshold = mean + 2 * std (significant motion)
        adaptive = mean_vel + 2.0 * std_vel
        return max(adaptive, self.swing_velocity_threshold * 0.5)

    # --------------------------------------------------------
    # Summary report
    # --------------------------------------------------------
    def get_summary(self) -> Dict:
        """Generate a summary of all detected shots."""
        if not self.detected_shots:
            return {
                "total_shots": 0,
                "total_frames": self.frame_count,
                "shots": []
            }

        shots_data = [s.to_dict() for s in self.detected_shots]

        # Aggregate stats
        speeds = [s.swing_speed_max for s in self.detected_shots]
        durations = [s.swing_duration for s in self.detected_shots]
        reactions = [s.reaction_time for s in self.detected_shots if s.reaction_time > 0]
        stabilities = [s.stability_deviation for s in self.detected_shots]

        return {
            "total_shots": len(self.detected_shots),
            "total_frames": self.frame_count,
            "avg_swing_speed": round(float(np.mean(speeds)), 2) if speeds else 0,
            "max_swing_speed": round(float(np.max(speeds)), 2) if speeds else 0,
            "avg_swing_duration": round(float(np.mean(durations)), 4) if durations else 0,
            "avg_reaction_time": round(float(np.mean(reactions)), 4) if reactions else 0,
            "avg_stability_deviation": round(float(np.mean(stabilities)), 6) if stabilities else 0,
            "shots": shots_data,
        }

    # --------------------------------------------------------
    # Get real-time status for HUD overlay
    # --------------------------------------------------------
    def get_hud_status(self) -> Dict:
        """Get current status for real-time HUD display."""
        status = {
            "in_swing": self.in_swing,
            "total_shots": self.shot_count,
            "current_velocity": float(self.bat_velocity_history[-1]) if self.bat_velocity_history else 0.0,
        }

        if self.in_swing:
            swing_frames = self.frame_count - self.swing_start_frame
            status["swing_duration"] = round(swing_frames * self.dt, 3)
            if self.swing_metrics_buffer:
                vels = [m.get('bat_angular_velocity', 0.0) for m in self.swing_metrics_buffer]
                status["current_peak_velocity"] = round(float(np.max(vels)), 1)

        if self.detected_shots:
            last = self.detected_shots[-1]
            status["last_shot"] = {
                "id": last.shot_id,
                "speed": round(last.swing_speed_max, 1),
                "duration": round(last.swing_duration, 3),
                "reaction": round(last.reaction_time, 3),
                "stability": round(last.stability_deviation, 4),
                "confidence": round(last.confidence, 2),
            }

        return status


# ============================================================
# Standalone analysis: process existing JSON files
# ============================================================
def analyze_keypoints_folder(folder_path, fps=25.0):
    """
    Analyze a folder of keypoint JSON files and detect all shots.
    Returns the shot detection summary.
    """
    import json
    import os
    import glob

    json_files = sorted(glob.glob(os.path.join(folder_path, "frame_*.json")))

    if not json_files:
        print(f"[ERROR] No JSON files found in {folder_path}")
        return None

    print(f"[INFO] Analyzing {len(json_files)} frames from: {folder_path}")

    detector = ShotDetector(fps=fps)
    shot_events = []

    for i, json_path in enumerate(json_files):
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Extract batsman and bowler metrics
        batsman_metrics = {}
        bowler_metrics = {}

        if 'players' in data:
            for player in data['players']:
                label = player.get('label', '')
                metrics = player.get('metrics', {})
                if label == 'Batsman':
                    batsman_metrics = metrics
                elif label == 'Bowler':
                    bowler_metrics = metrics
        elif 'metrics' in data:
            batsman_metrics = data['metrics']

        shot = detector.process_frame(batsman_metrics, bowler_metrics, frame_idx=i)

        if shot:
            shot_events.append(shot)
            print(f"  🏏 Shot #{shot.shot_id} detected!")
            print(f"     Frames: {shot.swing_start_frame} → {shot.impact_frame} → {shot.swing_end_frame}")
            print(f"     Speed: {shot.swing_speed_max:.1f} deg/s | Duration: {shot.swing_duration:.3f}s")
            print(f"     Reaction: {shot.reaction_time:.3f}s | Stability: {shot.stability_deviation:.4f}")
            print(f"     Confidence: {shot.confidence:.0%}")

    summary = detector.get_summary()

    # Save summary
    summary_path = os.path.join(folder_path, "shot_detection_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n[OK] Summary saved to: {summary_path}")

    return summary


# ============================================================
# Main: run standalone analysis
# ============================================================
if __name__ == "__main__":
    import sys

    folder = sys.argv[1] if len(sys.argv) > 1 else "keypoints_json"
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0

    print("=" * 60)
    print("🏏 CRICKET SHOT DETECTION ENGINE")
    print("=" * 60)

    summary = analyze_keypoints_folder(folder, fps)

    if summary:
        print("\n" + "=" * 60)
        print("📊 SHOT DETECTION RESULTS")
        print("=" * 60)
        print(f"  Total Frames Analyzed: {summary['total_frames']}")
        print(f"  Total Shots Detected:  {summary['total_shots']}")
        print(f"  Avg Swing Speed:       {summary['avg_swing_speed']} deg/s")
        print(f"  Max Swing Speed:       {summary['max_swing_speed']} deg/s")
        print(f"  Avg Swing Duration:    {summary['avg_swing_duration']}s")
        print(f"  Avg Reaction Time:     {summary['avg_reaction_time']}s")
        print(f"  Avg Stability Dev:     {summary['avg_stability_deviation']}")
        print("=" * 60)

        for shot in summary['shots']:
            print(f"\n  Shot #{shot['shot_id']}:")
            print(f"    Swing:    Frame {shot['swing_start_frame']} → {shot['impact_frame']} → {shot['swing_end_frame']}")
            print(f"    Speed:    {shot['swing_speed_max_deg_per_sec']} deg/s (max) | {shot['swing_speed_avg_deg_per_sec']} deg/s (avg)")
            print(f"    Duration: {shot['swing_duration_sec']}s")
            print(f"    Reaction: {shot['reaction_time_sec']}s")
            print(f"    Stability:{shot['stability_deviation']}")
            print(f"    Impact:   Elbow={shot['elbow_angle_at_impact']}° Knee={shot['knee_angle_at_impact']}°")
            print(f"    Rotation: Shoulder={shot['shoulder_rotation_max']}° Hip={shot['hip_rotation_max']}°")
            print(f"    Confidence: {shot['confidence']:.0%}")
