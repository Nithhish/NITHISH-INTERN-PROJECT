import sys
print("Starting script...")
try:
    from backend.cv_processor import process_video_inference
    print("Imported cv_processor")
    print("Testing process_video_inference...")
    process_video_inference('uploads/089e5e9d-d980-4f0d-a81b-874353ed1e7d.mp4')
    print("Done")
except Exception as e:
    import traceback
    traceback.print_exc()
