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
    Returns a dict of per-frame metrics used by the shot detection engine.
    """
    if not keypoints or len(keypoints) < 33:
        return {}

    def get_pt(idx):
        return [keypoints[idx]['x'], keypoints[idx]['y']]

    def get_vis(idx):
        return keypoints[idx].get('visibility', 0.0)

    # Keypoint indices (MediaPipe 33-point format)
    L_SHOULDER, R_SHOULDER = 11, 12
    L_ELBOW, R_ELBOW = 13, 14
    L_WRIST, R_WRIST = 15, 16
    L_HIP, R_HIP = 23, 24
    L_KNEE, R_KNEE = 25, 26
    L_ANKLE, R_ANKLE = 27, 28
    NOSE = 0

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
    # 2. Center of Gravity (midpoint of hips)
    # ==========================================
    l_hip = np.array(get_pt(L_HIP))
    r_hip = np.array(get_pt(R_HIP))
    cog = (l_hip + r_hip) / 2.0
    metrics['cog_x'] = float(cog[0])
    metrics['cog_y'] = float(cog[1])

    # ==========================================
    # 3. Head Deviation from COG vertical
    # ==========================================
    nose = np.array(get_pt(NOSE))
    metrics['head_deviation'] = float(nose[0] - cog[0])

    # ==========================================
    # 4. Wrist positions (for tracking swing arc)
    # ==========================================
    r_wrist = np.array(get_pt(R_WRIST))
    l_wrist = np.array(get_pt(L_WRIST))
    metrics['right_wrist_x'] = float(r_wrist[0])
    metrics['right_wrist_y'] = float(r_wrist[1])
    metrics['left_wrist_x'] = float(l_wrist[0])
    metrics['left_wrist_y'] = float(l_wrist[1])

    # ==========================================
    # 5. Motion-based metrics (require previous frame)
    # ==========================================
    if prev_keypoints and len(prev_keypoints) >= 33:
        def get_prev_pt(idx):
            return [prev_keypoints[idx]['x'], prev_keypoints[idx]['y']]

        # --- Bat Angular Velocity (arm swing proxy) ---
        curr_wrist = np.array(get_pt(R_WRIST))
        prev_wrist = np.array(get_prev_pt(R_WRIST))
        pivot = np.array(get_pt(R_SHOULDER))

        v_curr = curr_wrist - pivot
        v_prev = prev_wrist - pivot

        cos_theta = np.dot(v_curr, v_prev) / (np.linalg.norm(v_curr) * np.linalg.norm(v_prev) + 1e-6)
        d_theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
        metrics['bat_angular_velocity'] = float(np.degrees(d_theta) / dt)

        # --- Wrist Linear Velocity (both hands) ---
        metrics['right_wrist_velocity'] = float(point_velocity(get_pt(R_WRIST), get_prev_pt(R_WRIST), dt))
        metrics['left_wrist_velocity'] = float(point_velocity(get_pt(L_WRIST), get_prev_pt(L_WRIST), dt))

        # --- Combined hands velocity (bat swing indicator) ---
        metrics['hands_velocity'] = float(
            (metrics['right_wrist_velocity'] + metrics['left_wrist_velocity']) / 2.0
        )

        # --- COG velocity (body movement/stability) ---
        prev_l_hip = np.array(get_prev_pt(L_HIP))
        prev_r_hip = np.array(get_prev_pt(R_HIP))
        prev_cog = (prev_l_hip + prev_r_hip) / 2.0
        cog_displacement = np.linalg.norm(cog - prev_cog)
        metrics['cog_velocity'] = float(cog_displacement / dt)

        # --- Shoulder rotation velocity ---
        curr_shoulder_vec = np.array(get_pt(R_SHOULDER)) - np.array(get_pt(L_SHOULDER))
        prev_shoulder_vec = np.array(get_prev_pt(R_SHOULDER)) - np.array(get_prev_pt(L_SHOULDER))
        cos_s = np.dot(curr_shoulder_vec, prev_shoulder_vec) / (
            np.linalg.norm(curr_shoulder_vec) * np.linalg.norm(prev_shoulder_vec) + 1e-6
        )
        d_theta_s = np.arccos(np.clip(cos_s, -1.0, 1.0))
        metrics['shoulder_rotation_velocity'] = float(np.degrees(d_theta_s) / dt)

        # --- Hip rotation velocity ---
        curr_hip_vec = np.array(get_pt(R_HIP)) - np.array(get_pt(L_HIP))
        prev_hip_vec = np.array(get_prev_pt(R_HIP)) - np.array(get_prev_pt(L_HIP))
        cos_h = np.dot(curr_hip_vec, prev_hip_vec) / (
            np.linalg.norm(curr_hip_vec) * np.linalg.norm(prev_hip_vec) + 1e-6
        )
        d_theta_h = np.arccos(np.clip(cos_h, -1.0, 1.0))
        metrics['hip_rotation_velocity'] = float(np.degrees(d_theta_h) / dt)

    else:
        metrics['bat_angular_velocity'] = 0.0
        metrics['right_wrist_velocity'] = 0.0
        metrics['left_wrist_velocity'] = 0.0
        metrics['hands_velocity'] = 0.0
        metrics['cog_velocity'] = 0.0
        metrics['shoulder_rotation_velocity'] = 0.0
        metrics['hip_rotation_velocity'] = 0.0

    return metrics
