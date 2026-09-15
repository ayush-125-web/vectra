import cv2
import re
from collections import defaultdict
from ultralytics import YOLO
from paddleocr import PaddleOCR


class PlateDetector:

    def __init__(
        self,
        model_path="models/best.pt",
        frequency_threshold=5
    ):

        # =========================================
        # SETTINGS
        # =========================================

        self.frequency_threshold = frequency_threshold


        # =========================================
        # LOAD MODELS
        # =========================================

        self.model = YOLO(model_path)

        self.ocr = PaddleOCR(
            lang="en",
            use_angle_cls=True
        )


        # =========================================
        # PLATE STORAGE
        # =========================================

        self.plate_data = defaultdict(
            lambda: {
                "frequency": 0,
                "confidence_sum": 0.0
            }
        )


        # =========================================
        # FINAL VERIFIED PLATES
        # =========================================

        self.final_plates = {}


    # =========================================
    # CLEAN OCR TEXT
    # =========================================

    def clean_plate(self, text):

        text = text.upper()

        text = re.sub(
            r'[^A-Z0-9]',
            '',
            text
        )

        if len(text) != 7:
          return ""

        return text


    # =========================================
    # UPDATE PLATE DATA
    # =========================================

    def update_plate(
        self,
        plate_text,
        confidence
    ):

        # Increase frequency
        self.plate_data[
            plate_text
        ]["frequency"] += 1


        # Add confidence
        self.plate_data[
            plate_text
        ]["confidence_sum"] += confidence


        # Get frequency
        frequency = self.plate_data[
            plate_text
        ]["frequency"]


        # Calculate average confidence
        avg_confidence = (
            self.plate_data[
                plate_text
            ]["confidence_sum"]
            / frequency
        )


        # =====================================
        # CHECK FREQUENCY THRESHOLD
        # =====================================

        if frequency >= self.frequency_threshold:

            self.final_plates[
                plate_text
            ] = {
                "frequency": frequency,
                "avg_confidence": avg_confidence
            }


    # =========================================
    # PROCESS VIDEO
    # =========================================

    def process_video(self, video_path):

        cap = cv2.VideoCapture(
            video_path
        )


        while True:

            ret, frame = cap.read()

            if not ret:
                break


            # =================================
            # LICENSE PLATE DETECTION
            # =================================

            results = self.model(
                frame,
                conf=0.4,
                verbose=False
            )


            for result in results:

                # Loop through all detected plates
                for box in result.boxes:


                    # =============================
                    # GET COORDINATES
                    # =============================

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )


                    # =============================
                    # CROP PLATE
                    # =============================

                    plate_crop = frame[
                        y1:y2,
                        x1:x2
                    ]


                    if plate_crop.size == 0:
                        continue


                    # =============================
                    # OCR
                    # =============================

                    ocr_result = self.ocr.predict(
                        plate_crop
                    )


                    plate_text = ""


                    # =============================
                    # EXTRACT OCR RESULT
                    # =============================

                    for res in ocr_result:

                        texts = res.get(
                            "rec_texts",
                            []
                        )

                        scores = res.get(
                            "rec_scores",
                            []
                        )


                        for text, confidence in zip(
                            texts,
                            scores
                        ):

                            confidence = float(
                                confidence
                            )


                            # =========================
                            # CLEAN TEXT
                            # =========================

                            plate_text = self.clean_plate(
                                text
                            )


                            if not plate_text:
                                continue


                            # =========================
                            # UPDATE PLATE DATA
                            # =========================

                            self.update_plate(
                                plate_text,
                                confidence
                            )


                            # =========================
                            # TERMINAL OUTPUT
                            # =========================

                            frequency = self.plate_data[
                                plate_text
                            ]["frequency"]


                            avg_confidence = (
                                self.plate_data[
                                    plate_text
                                ]["confidence_sum"]
                                / frequency
                            )


                            print(
                                f"OCR: {plate_text} | "
                                f"Frequency: {frequency} | "
                                f"Avg Confidence: "
                                f"{avg_confidence:.2f}"
                            )


                    # =============================
                    # DRAW BOUNDING BOX
                    # =============================

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )


                    # =============================
                    # DISPLAY PLATE NUMBER
                    # =============================

                    if plate_text:

                        cv2.putText(
                            frame,
                            plate_text,
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.9,
                            (0, 255, 0),
                            2
                        )


            # =================================
            # SHOW VIDEO
            # =================================

            cv2.imshow(
                "VECTRA ANPR",
                frame
            )


            # Press Q to stop
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break


        cap.release()

        cv2.destroyAllWindows()


        # =====================================
        # RETURN FINAL VECTOR
        # =====================================

        return self.get_final_vector()


    # =========================================
    # CREATE FINAL VECTOR
    # =========================================

    def get_final_vector(self):

        final_vector = []


        for plate, data in self.final_plates.items():

            final_vector.append([
                plate,
                data["frequency"],
                round(
                    data["avg_confidence"],
                    3
                )
            ])


        return final_vector

if __name__ == "__main__":

    detector = PlateDetector(
        model_path="ai/models/best.pt",
        frequency_threshold=5
    )


    final_vector = detector.process_video(
        "data/videos/cam3.mp4"
    )


    print("\n")
    print("========================================")
    print("FINAL VECTOR")
    print("========================================")

    print(final_vector)