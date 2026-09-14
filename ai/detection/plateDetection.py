import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR

# Load pretrained license plate detector
model = YOLO("models/best.pt")
ocr = PaddleOCR(
    lang="en"
)

video_path = "../data/videos/cam3.mp4"

cap = cv2.VideoCapture(video_path)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    # Detect license plates
    results = model(frame, conf=0.4)

    for result in results:

        for box in result.boxes:

            # Get coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Crop the license plate
            plate_crop = frame[y1:y2, x1:x2]

             # OCR
            ocr_result = ocr.predict(plate_crop)

            ##print(ocr_result)

            # Show the cropped plate
            ## cv2.imshow("Plate", plate_crop)

            for result in ocr_result:
                print("TEXT:", result['rec_texts'])
                print("CONFIDENCE:", result['rec_scores'])

    #press q to stop

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()