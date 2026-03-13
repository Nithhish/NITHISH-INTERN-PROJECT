import traceback
from backend.cv_processor import process_video_inference

video_path = 'uploads/089e5e9d-d980-4f0d-a81b-874353ed1e7d.mp4'
try:
    shots, frame_count = process_video_inference(video_path)
    print(f'Success! Detected {len(shots)} shots across {frame_count} frames.')
except Exception as e:
    print('Failed with error:')
    traceback.print_exc()
