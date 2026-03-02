"""
Scoring & Injury Risk Engine for Cricket Training
=================================================
Calculates technique scores and flags injury risks:
  - Knee Valgus Detection (caving knees)
  - Lumbar Over-extension (excessive arching)
  - Technique Score: (Angle Accuracy * 0.4) + (Balance * 0.3) + (Timing * 0.3)
"""

import numpy as np
from typing import Dict, List, Optional


class ScoringEngine:
    def __init__(self, target_angles: Optional[Dict] = None):
        # Optimized target angles for a standard drive/shot
        self.target_angles = target_angles or {
            'right_elbow_angle': 160.0,
            'right_knee_angle': 140.0,
            'right_shoulder_angle': 90.0,
        }
        
        # Risk Thresholds
        self.VALGUS_THRESHOLD = 0.85        # Knee width < 85% of hip width
        self.LUMBAR_EXT_THRESHOLD = 195.0    # Degrees (mid-shld, mid-hip, mid-knee)
        self.LUMBAR_FLEX_THRESHOLD = 150.0   # Excessive slouching or forward lean
        
    def calculate_technique_score(self, shot_data: Dict) -> Dict:
        """
        Normalized scoring model:
        Technique Score = (Angle Accuracy * 0.4) + (Balance Stability * 0.3) + (Timing * 0.3)
        Returns a score from 0-100 and a breakdown.
        """
        # 1. Angle Accuracy (0-100)
        # Compare impact angles to targets
        elbow_diff = abs(shot_data.get('elbow_angle_at_impact', 0) - self.target_angles['right_elbow_angle'])
        knee_diff = abs(shot_data.get('knee_angle_at_impact', 0) - self.target_angles['right_knee_angle'])
        
        # Normalized accuracy: 100 - average error (clamped)
        angle_accuracy = max(0, 100 - (elbow_diff + knee_diff) / 2.0)
        
        # 2. Balance & Stability (0-100)
        # Stability is measured by COG deviation (lower is better)
        # Assuming deviation of 0.0 is perfect 100, deviation of 0.2 is 0
        stability_dev = shot_data.get('stability_deviation', 0.1)
        balance_score = max(0, 100 - (stability_dev * 500)) 
        
        # 3. Timing (0-100)
        # Based on peak velocity vs duration and reaction time
        # Ideal timing has high peak velocity and reasonable duration
        peak_vel = shot_data.get('swing_speed_max_deg_per_sec', 0)
        # Normalize peak velocity: 0-4000 deg/s map to 0-100
        timing_score = min(100, (peak_vel / 40.0))
        
        # Weighted Total
        total_score = (angle_accuracy * 0.4) + (balance_score * 0.3) + (timing_score * 0.3)
        
        return {
            "total": round(total_score, 1),
            "breakdown": {
                "angle_accuracy": round(angle_accuracy, 1),
                "balance": round(balance_score, 1),
                "timing": round(timing_score, 1)
            }
        }

    def detect_injury_risks(self, metrics: Dict) -> List[Dict]:
        """
        Flags injury risks based on per-frame metrics.
        """
        flags = []
        
        # --- 1. Knee Valgus ---
        valgus_ratio = metrics.get('knee_valgus_ratio', 1.0)
        if valgus_ratio < self.VALGUS_THRESHOLD:
            flags.append({
                "type": "Knee Valgus",
                "severity": "High" if valgus_ratio < 0.7 else "Moderate",
                "message": "Knees caving inward - risk of ACL strain.",
                "value": round(valgus_ratio, 2)
            })
            
        # --- 2. Lumbar Over-extension ---
        lumbar = metrics.get('lumbar_angle', 180.0)
        if lumbar > self.LUMBAR_EXT_THRESHOLD:
            flags.append({
                "type": "Lumbar Over-extension",
                "severity": "High" if lumbar > 210 else "Moderate",
                "message": "Excessive back arching - risk of stress fracture.",
                "value": round(lumbar, 1)
            })
        elif lumbar < self.LUMBAR_FLEX_THRESHOLD:
            flags.append({
                "type": "Excessive Lumbar Flexion",
                "severity": "Moderate",
                "message": "Too much forward slouch - check spinal posture.",
                "value": round(lumbar, 1)
            })
            
        return flags

    def get_shot_feedback(self, score: float, risks: List[Dict]) -> str:
        """User-friendly feedback string."""
        if risks:
            return "⚠️ HIGH INJURY RISK DETECTED. Review knee and back positioning."
        if score > 85:
            return "🌟 ELITE TECHNIQUE! Perfect balance and timing."
        if score > 70:
            return "👍 SOLID DRIVE. Work on holding your finish."
        return "🏏 PRACTICE NEEDED. Focus on head position and knee bend."
