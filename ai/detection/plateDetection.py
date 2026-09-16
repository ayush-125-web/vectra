"""
VECTRA ANPR - Plate Detection
=============================
One PlateDetector object owns one YOLO model + one PaddleOCR engine.

PARALLEL SAFETY
---------------
Neither YOLO nor PaddleOCR is thread-safe, so every worker (thread or
process) must build its OWN PlateDetector. Never share one instance
between two workers - you get garbage OCR or a hard crash.

cv2.imshow() only works on the main thread, so pass show=False when
several videos are running at once.

LIVE MODE
---------
loop=True makes process_video() restart the video from frame 0 every
time it ends, so a 30-second clip behaves like a permanent camera feed.
Because it never truly "ends", it can't wait until the video finishes
to hand back a final vector - so instead, pass on_verified (a
callback) and it fires the moment a plate crosses frequency_threshold,
in real time. That plate's counter is then reset, so if the same car
loops back around (or the clip plays again), it counts as a fresh pass
and can fire again - which is exactly what you want for a live feed.

stop_event (a threading.Event) lets an outside controller stop a
looping video cleanly.

Goes to: ai/detection/plateDetection.py
"""

import re
from collections import defaultdict

import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR


class PlateDetector:

    def __init__(
        self,
        model_path="models/best.pt",
        frequency_threshold=5,
        show=False,
        frame_skip=1,
        conf=0.4,
        on_verified=None,
    ):
        self.model_path = model_path
        self.frequency_threshold = frequency_threshold
        self.show = show
        self.frame_skip = max(1, int(frame_skip))
        self.conf = conf

        # Called as on_verified(tag, plate_text, frequency, avg_confidence)
        # the instant a plate crosses the threshold. Used by live mode to
        # push a detection to the DB immediately instead of waiting for
        # the video to end (which, in loop mode, never happens).
        self.on_verified = on_verified

        self.model = YOLO(model_path)
        self.ocr = PaddleOCR(lang="en", use_angle_cls=True)

        self.plate_data = defaultdict(
            lambda: {"frequency": 0, "confidence_sum": 0.0}
        )
        self.final_plates = {}

    # =====================================================
    # STATE
    # =====================================================

    def reset(self):
        """
        Wipe per-video state.

        Without this a detector reused for CAM-02 still holds CAM-01's
        verified plates, and those get written to the DB a second time
        under the wrong camera_id.
        """
        self.plate_data.clear()
        self.final_plates.clear()

    # =====================================================
    # CLEAN OCR TEXT
    # =====================================================

    def clean_plate(self, text):
        text = re.sub(r"[^A-Z0-9]", "", text.upper())

        if len(text) != 7:
            return ""

        return text

    # =====================================================
    # UPDATE PLATE DATA
    # =====================================================

    def update_plate(self, plate_text, confidence, tag=None):
        entry = self.plate_data[plate_text]

        entry["frequency"] += 1
        entry["confidence_sum"] += confidence

        frequency = entry["frequency"]
        avg_confidence = entry["confidence_sum"] / frequency

        if frequency >= self.frequency_threshold:
            self.final_plates[plate_text] = {
                "frequency": frequency,
                "avg_confidence": avg_confidence,
            }

            if self.on_verified:
                self.on_verified(tag, plate_text, frequency, avg_confidence)

                # Reset just this plate's counter. In live/loop mode this
                # is what lets the SAME plate fire again later - either
                # the same car really does pass again, or the clip loops
                # back to frame 0 and "sees" it again. Without this reset
                # it would only ever fire once, the very first time.
                del self.plate_data[plate_text]

        return frequency, avg_confidence

    # =====================================================
    # PROCESS VIDEO
    # =====================================================

    def process_video(
        self,
        video_path,
        show=None,
        frame_skip=None,
        tag=None,
        verbose=True,
        reset=True,
        loop=False,
        stop_event=None,
    ):
        """
        Run detection over one video.

        show        - draw a live window. MUST be False off the main thread.
        frame_skip  - process every Nth frame (2 or 3 roughly halves runtime).
        tag         - prefix for log lines / callback, usually the camera_id.
        reset       - clear previous video's plates first. Keep this True.
        loop        - restart from frame 0 when the video ends, forever.
                      Combine with on_verified (set in __init__) so results
                      stream out instead of only arriving at the end.
        stop_event  - threading.Event; when set, the loop exits (checked
                      once per frame). Required to ever stop loop=True.

        Returns the final vector accumulated up to the point it stopped:
            [[plate_number, frequency, avg_confidence], ...]
        In loop mode this only matters for whatever hasn't already been
        reset-and-fired via on_verified.
        """
        if reset:
            self.reset()

        show = self.show if show is None else show
        frame_skip = (
            self.frame_skip if frame_skip is None else max(1, int(frame_skip))
        )
        prefix = f"[{tag}] " if tag else ""

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        window = f"VECTRA ANPR - {tag or video_path}"
        frame_index = 0

        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break

                ret, frame = cap.read()

                if not ret:
                    if loop:
                        cap.release()
                        cap = cv2.VideoCapture(video_path)
                        frame_index = 0
                        continue
                    break

                frame_index += 1

                if frame_index % frame_skip != 0:
                    continue

                # -----------------------------------------
                # LICENSE PLATE DETECTION
                # -----------------------------------------

                results = self.model(frame, conf=self.conf, verbose=False)

                for result in results:
                    for box in result.boxes:

                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        plate_crop = frame[y1:y2, x1:x2]

                        if plate_crop.size == 0:
                            continue

                        # ---------------------------------
                        # OCR
                        # ---------------------------------

                        plate_text = ""
                        ocr_result = self.ocr.predict(plate_crop)

                        for res in ocr_result:
                            texts = res.get("rec_texts", [])
                            scores = res.get("rec_scores", [])

                            for text, confidence in zip(texts, scores):
                                confidence = float(confidence)

                                plate_text = self.clean_plate(text)

                                if not plate_text:
                                    continue

                                frequency, avg_confidence = self.update_plate(
                                    plate_text, confidence, tag=tag
                                )

                                if verbose:
                                    print(
                                        f"{prefix}OCR: {plate_text} | "
                                        f"Frequency: {frequency} | "
                                        f"Avg Confidence: {avg_confidence:.2f}"
                                    )

                        # ---------------------------------
                        # DRAW (only when a window is shown)
                        # ---------------------------------

                        if show:
                            cv2.rectangle(
                                frame, (x1, y1), (x2, y2), (0, 255, 0), 2
                            )

                            if plate_text:
                                cv2.putText(
                                    frame,
                                    plate_text,
                                    (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.9,
                                    (0, 255, 0),
                                    2,
                                )

                if show:
                    cv2.imshow(window, frame)

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        if stop_event is not None:
                            stop_event.set()
                        break

        finally:
            cap.release()

            if show:
                try:
                    cv2.destroyWindow(window)
                except cv2.error:
                    pass

        return self.get_final_vector()

    # =====================================================
    # FINAL VECTOR
    # =====================================================

    def get_final_vector(self):
        return [
            [plate, data["frequency"], round(data["avg_confidence"], 3)]
            for plate, data in self.final_plates.items()
        ]


if __name__ == "__main__":
    detector = PlateDetector(
        model_path="ai/models/best.pt",
        frequency_threshold=5,
        show=True,
    )

    final_vector = detector.process_video("data/videos/cam3.mp4", tag="CAM-03")

    print("\n" + "=" * 40)
    print("FINAL VECTOR")
    print("=" * 40)
    print(final_vector)