import numpy as np


def calculate_angle(a, b, c):
    """Calculates the angle at point b given points a, b, c."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))

    return np.degrees(angle)


def point_velocity(curr_pt, prev_pt, dt):
    """Calculate velocity (pixels/sec normalized) between two points."""
    curr = np.array(curr_pt)
    prev = np.array(prev_pt)
    displacement = np.linalg.norm(curr - prev)
    return displacement / max(dt, 1e-6)


def get_pose_metrics(keypoints, prev_keypoints=None, fps=30.0):
    """
    Extracts biomechanical metrics from keypoints (MediaPipe 33-format).
    Returns a dict of per-frame metrics used by the shot detection and scoring engines.
    """
    if not keypoints or len(keypoints) < 33:
        return {}

    def get_pt(idx):
        return [keypoints[idx]['x'], keypoints[idx]['y']]

    def get_vis(idx):
        return keypoints[idx].get('visibility', 0.0)

    # Keypoint indices (MediaPipe 33-point format)
    NOSE = 0
    L_SHOULDER, R_SHOULDER = 11, 12
    L_ELBOW, R_ELBOW = 13, 14
    L_WRIST, R_WRIST = 15, 16
    L_HIP, R_HIP = 23, 24
    L_KNEE, R_KNEE = 25, 26
    L_ANKLE, R_ANKLE = 27, 28

    dt = 1.0 / max(fps, 1.0)
    metrics = {}

    # ==========================================
    # 1. Joint Angles
    # ==========================================
    metrics['left_elbow_angle'] = calculate_angle(get_pt(L_SHOULDER), get_pt(L_ELBOW), get_pt(L_WRIST))
    metrics['right_elbow_angle'] = calculate_angle(get_pt(R_SHOULDER), get_pt(R_ELBOW), get_pt(R_WRIST))

    metrics['left_shoulder_angle'] = calculate_angle(get_pt(L_ELBOW), get_pt(L_SHOULDER), get_pt(L_HIP))
    metrics['right_shoulder_angle'] = calculate_angle(get_pt(R_ELBOW), get_pt(R_SHOULDER), get_pt(R_HIP))

    metrics['left_knee_angle'] = calculate_angle(get_pt(L_HIP), get_pt(L_KNEE), get_pt(L_ANKLE))
    metrics['right_knee_angle'] = calculate_angle(get_pt(R_HIP), get_pt(R_KNEE), get_pt(R_ANKLE))

    # ==========================================
    # 2. Stability & Posture
    # ==========================================
    l_hip = np.array(get_pt(L_HIP))
    r_hip = np.array(get_pt(R_HIP))
    cog = (l_hip + r_hip) / 2.0
    metrics['cog_x'] = float(cog[0])
    metrics['cog_y'] = float(cog[1])

    nose = np.array(get_pt(NOSE))
    metrics['head_deviation'] = float(nose[0] - cog[0])

    # ==========================================
    # 3. Injury Risk Metrics (New)
    # ==========================================
    
    # --- Knee Valgus Detection ---
    # Heuristic: If knees are closer together than hips relative to ankles
    hip_width = np.linalg.norm(np.array(get_pt(L_HIP)) - np.array(get_pt(R_HIP)))
    knee_width = np.linalg.norm(np.array(get_pt(L_KNEE)) - np.array(get_pt(R_KNEE)))
    metrics['knee_valgus_ratio'] = float(knee_width / max(hip_width, 1e-6))
    
    # --- Lumbar Extension ---
    # Angle between mid-shoulders, mid-hips, and mid-knees
    mid_shoulder = (np.array(get_pt(L_SHOULDER)) + np.array(get_pt(R_SHOULDER))) / 2.0
    mid_hip = (np.array(get_pt(L_HIP)) + np.array(get_pt(R_HIP))) / 2.0
    mid_knee = (np.array(get_pt(L_KNEE)) + np.array(get_pt(R_KNEE))) / 2.0
    
    # In a side view, this angle > 180 implies arching back (over-extension)
    # Since calculate_angle returns 0-180, we use coordinate geometry for signed angle
    def get_signed_angle(p1, p2, p3):
        v1 = p1 - p2
        v2 = p3 - p2
        angle = np.arctan2(v2[1], v2[0]) - np.arctan2(v1[1], v1[0])
        return np.degrees(angle) % 360

    metrics['lumbar_angle'] = get_signed_angle(mid_shoulder, mid_hip, mid_knee)

    # ==========================================
    # 4. Motion-based metrics
    # ==========================================
    if prev_keypoints and len(prev_keypoints) >= 33:
        def get_prev_pt(idx):
            return [prev_keypoints[idx]['x'], prev_keypoints[idx]['y']]

        curr_wrist = np.array(get_pt(R_WRIST))
        prev_wrist = np.array(get_prev_pt(R_WRIST))
        pivot = np.array(get_pt(R_SHOULDER))

        v_curr = curr_wrist - pivot
        v_prev = prev_wrist - pivot

        cos_theta = np.dot(v_curr, v_prev) / (np.linalg.norm(v_curr) * np.linalg.norm(v_prev) + 1e-6)
        d_theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        metrics['bat_angular_velocity'] = float(np.degrees(d_theta) / dt)

        metrics['right_wrist_velocity'] = float(point_velocity(get_pt(R_WRIST), get_prev_pt(R_WRIST), dt))
        metrics['left_wrist_velocity'] = float(point_velocity(get_pt(L_WRIST), get_prev_pt(L_WRIST), dt))
        metrics['hands_velocity'] = float((metrics['right_wrist_velocity'] + metrics['left_wrist_velocity']) / 2.0)

        prev_cog = (np.array(get_prev_pt(L_HIP)) + np.array(get_prev_pt(R_HIP))) / 2.0
        metrics['cog_velocity'] = float(np.linalg.norm(cog - prev_cog) / dt)

        # Rotation velocities & Absolute Angles
        def get_body_angle(pt_a, pt_b):
            """Get angle of a line relative to horizontal."""
            dx = pt_a[0] - pt_b[0]
            dy = pt_a[1] - pt_b[1]
            return float(np.degrees(np.arctan2(dy, dx)) % 360)

        metrics['shoulder_angle'] = get_body_angle(get_pt(R_SHOULDER), get_pt(L_SHOULDER))
        metrics['hip_angle'] = get_body_angle(get_pt(R_HIP), get_pt(L_HIP))
        metrics['hip_shoulder_separation'] = abs(metrics['shoulder_angle'] - metrics['hip_angle'])

        def get_rot_vel(curr_a, curr_b, prev_a, prev_b):
            c_vec = np.array(curr_a) - np.array(curr_b)
            p_vec = np.array(prev_a) - np.array(prev_b)
            cos = np.dot(c_vec, p_vec) / (np.linalg.norm(c_vec) * np.linalg.norm(p_vec) + 1e-6)
            return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))) / dt)

        metrics['shoulder_rotation_velocity'] = get_rot_vel(get_pt(R_SHOULDER), get_pt(L_SHOULDER), get_prev_pt(R_SHOULDER), get_prev_pt(L_SHOULDER))
        metrics['hip_rotation_velocity'] = get_rot_vel(get_pt(R_HIP), get_pt(L_HIP), get_prev_pt(R_HIP), get_prev_pt(L_HIP))
    else:
        for k in ['bat_angular_velocity', 'right_wrist_velocity', 'left_wrist_velocity', 'hands_velocity', 'cog_velocity', 'shoulder_rotation_velocity', 'hip_rotation_velocity', 'shoulder_angle', 'hip_angle', 'hip_shoulder_separation']:
            metrics[k] = 0.0

    return metrics
