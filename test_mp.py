import mediapipe as mp
try:
    print("Trying mp.solutions...")
    import mediapipe.solutions.pose as mp_pose
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
