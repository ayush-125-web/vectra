"""
ANPR City-Wide Vehicle Tracking - Controller
===============================================
This is the ONLY file that talks to all three other files. It doesn't
duplicate any of their code - it just imports the three classes and
wires them together behind a single controller class:

    anpr_db.py           -> ANPRDatabase        (schema + inserts)
    anpr_query.py         -> PlateQueryEngine     (read-only lookups)
    density_monitor.py    -> TrafficDensityMonitor (background bucket counts)

All input (OCR results, camera registration, blacklist entries,
plate lookups) goes IN through ANPRController's methods only - callers
never touch ANPRDatabase / PlateQueryEngine / TrafficDensityMonitor
directly.

The controller does NOT hardcode any plate numbers itself. It exposes
one ingestion method, process_detection(), that takes whatever vector
your friend's OCR model emits per video frame - camera_id, plate_number,
confidence_score, and optionally a timestamp - as a single dict, and
routes it into storage + density counting. The model is the source of
input; the controller only reacts to it.

Usage:
    system = ANPRController()
    system.register_camera("CAM001", "MG Road Junction", "MG Road")
    system.start()

    # camera_id is fixed per video feed - you pass it in yourself when
    # you set up that feed. Everything else (plate_number, confidence,
    # timestamp) comes straight out of the model's output vector.
    model_output = ocr_model.predict(video_frame)   # -> vector from the model
    system.process_detection("CAM001", model_output)

    system.blacklist_plate("TN01AB1234", "Reported stolen")
    system.report("TN01AB1234")

    system.stop()
"""

from anpr_db import ANPRDatabase
from anpr_query import PlateQueryEngine
from density_monitor import TrafficDensityMonitor


class ANPRController:
    """
    Single entry point for the whole ANPR system. Holds one instance
    each of ANPRDatabase, PlateQueryEngine and TrafficDensityMonitor,
    and exposes everything the outside world needs as plain methods.
    """

    def __init__(self, db_name: str = None):
        self.db = ANPRDatabase(db_name) if db_name else ANPRDatabase()
        self.query_engine = PlateQueryEngine(self.db)
        self.density_monitor = TrafficDensityMonitor(self.db)

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def start(self) -> None:
        """Starts the background density monitor thread."""
        self.density_monitor.start()

    def stop(self) -> None:
        """Stops the density monitor, flushing whatever is left in its buffer."""
        self.density_monitor.stop()

    def close(self) -> None:
        """Closes the database connection. Call after stop(), once you're done reading."""
        self.db.close()

    # -----------------------------------------------------------------
    # Write-side input (camera setup, OCR hits, blacklist)
    # -----------------------------------------------------------------

    def register_camera(self, camera_id, location_name, road_name=None) -> None:
        self.db.add_camera(camera_id, location_name, road_name)

    def process_detection(self, model_output) -> str:
        """
        Single entry point for the OCR model's output. Call this once per
        vector the model produces - the vector already contains everything
        about that detection (which camera, the plate number, the
        confidence score, optionally a timestamp). The controller does
        not generate or guess any of this - it only unpacks and stores
        whatever vector it's handed.

        Accepts either:
          - a dict:  {"camera_id": ..., "plate_number": ..., "confidence_score": ..., "timestamp": ...}
          - a tuple/list: (camera_id, plate_number, confidence_score[, timestamp])

        Handles the detection record AND the density-monitor bucket
        count in one go, so nothing downstream needs to call either
        ANPRDatabase or TrafficDensityMonitor directly.
        """
        camera_id, plate_number, confidence_score, timestamp = self._parse_model_output(model_output)
        # Guarantees the FK on detections.camera_id is satisfied even if this
        # camera hasn't been registered yet - INSERT OR IGNORE means a real
        # registration (via register_camera) is never overwritten.
        self.db.add_camera(camera_id, f"Unregistered camera {camera_id}")
        stored_ts = self.db.add_detection(plate_number, camera_id, confidence_score, timestamp)
        self.density_monitor.record(camera_id, plate_number)
        return stored_ts

    @staticmethod
    def _parse_model_output(model_output):
        """Unpacks whatever vector shape the model hands back into (camera_id, plate, confidence, timestamp)."""
        if isinstance(model_output, dict):
            camera_id = model_output.get("camera_id")
            plate_number = model_output.get("plate_number") or model_output.get("plate")
            confidence_score = model_output.get("confidence_score", model_output.get("confidence"))
            timestamp = model_output.get("timestamp")
        elif isinstance(model_output, (tuple, list)):
            camera_id = model_output[0] if len(model_output) > 0 else None
            plate_number = model_output[1] if len(model_output) > 1 else None
            confidence_score = model_output[2] if len(model_output) > 2 else None
            timestamp = model_output[3] if len(model_output) > 3 else None
        else:
            raise TypeError(
                "model_output must be a dict or a (camera_id, plate_number, confidence_score[, timestamp]) "
                f"tuple/list, got {type(model_output).__name__}"
            )

        if not camera_id:
            raise ValueError("model output vector is missing a camera_id")
        if not plate_number:
            raise ValueError("model output vector is missing a plate_number")

        return camera_id, plate_number, confidence_score, timestamp

    def blacklist_plate(self, plate_number, reason, flagged_on=None) -> None:
        self.db.add_to_blacklist(plate_number, reason, flagged_on)

    # -----------------------------------------------------------------
    # Read-side input (lookups / reports)
    # -----------------------------------------------------------------

    def report(self, plate_number, start_time=None, end_time=None) -> dict:
        return self.query_engine.query(plate_number, start_time, end_time)

    def print_report(self, plate_number, start_time=None, end_time=None) -> dict:
        return self.query_engine.print_report(plate_number, start_time, end_time)

    def last_known_location(self, plate_number):
        return self.query_engine.get_last_known_location(plate_number)

    def is_blacklisted(self, plate_number):
        return self.query_engine.is_blacklisted(plate_number)

    def get_density(self, camera_id=None, start_time=None, end_time=None) -> list:
        return self.density_monitor.get_density(camera_id, start_time, end_time)


if __name__ == "__main__":
    """
    Reads real detection vectors from stdin - one JSON object per line -
    and feeds each one straight into the controller. No plate numbers,
    confidence scores, or camera IDs are defined inside this file; every
    vector processed here comes from whatever is piped in at runtime,
    e.g. from your friend's OCR model:

        echo '{"camera_id": "CAM001", "plate_number": "TN01AB1234", "confidence_score": 0.96}' | python3 anpr_controller.py

    or, streaming multiple detections (one vector per line):

        cat detections.jsonl | python3 anpr_controller.py
    """
    import sys
    import json

    system = ANPRController()
    system.start()  # density monitor running in the background

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            vector = json.loads(line)
            stored_ts = system.process_detection(vector)
            print(f"Stored: {vector.get('plate_number')} @ {vector.get('camera_id')} ({stored_ts})")
    finally:
        system.stop()   # flush the density buffer
        system.close()  # close the DB connection