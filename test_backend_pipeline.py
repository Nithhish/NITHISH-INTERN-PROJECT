import requests
import os

API_BASE = "http://localhost:8000"

def test_pipeline():
    # 1. Create a player
    print("[1] Creating player...")
    p_res = requests.post(f"{API_BASE}/players/", json={"name": "Nithish Test", "email": "test@cricket.ai"})
    player = p_res.json()
    player_id = player['id']
    print(f"    Player Created: {player['name']} (ID: {player_id})")

    # 2. Upload the local cricket video
    video_path = r"E:\my Pro\day 1 and 2 and 3,4\cricket.mp4"
    if not os.path.exists(video_path):
        print(f"[ERR] Video not found at {video_path}")
        return

    print(f"[2] Uploading video: {video_path}")
    with open(video_path, "rb") as f:
        files = {"file": ("cricket.mp4", f, "video/mp4")}
        u_res = requests.post(f"{API_BASE}/upload/{player_id}", files=files)
    
    upload_data = u_res.json()
    session_id = upload_data['session_id']
    print(f"    Upload Success. Session ID: {session_id}")
    print(f"    Processing started in background...")
    
    print("\n[OK] Pipeline test initiated. Check backend logs for CV processing progress.")
    print(f"     Once finished, you can fetch results at: {API_BASE}/sessions/{session_id}")

if __name__ == "__main__":
    try:
        test_pipeline()
    except Exception as e:
        print(f"[ERR] Connection failed: {e}. Is the backend running?")
        print("      Run: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
