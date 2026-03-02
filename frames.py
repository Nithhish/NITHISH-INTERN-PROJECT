import cv2
import os

video_path = r"E:\tesy\cricket_training-main\videoplayback.mp4"
output_folder = "frame"

os.makedirs(output_folder, exist_ok=True)

cap = cv2.VideoCapture(video_path)
count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_path = f"{output_folder}/frame_{count:04d}.jpg"
    cv2.imwrite(frame_path, frame)

    count += 1

cap.release()
print("Frames saved:", count)