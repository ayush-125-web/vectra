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

Usage:
    system = ANPRController()
    system.register_camera("CAM001", "MG Road Junction", "MG Road")
    system.start()

    system.on_ocr_result("CAM001", "TN01AB1234", 0.96)

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

    def on_ocr_result(self, camera_id, plate_number, confidence_score, timestamp=None) -> str:
        """
        Call this once per OCR hit from the detection pipeline: plate
        number, confidence, and (optionally) a timestamp. Handles the
        detection record AND the density-monitor bucket count in one go.
        """
        stored_ts = self.db.add_detection(plate_number, camera_id, confidence_score, timestamp)
        self.density_monitor.record(camera_id, plate_number)
        return stored_ts

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
    system = ANPRController()

    system.register_camera("CAM001", "MG Road Junction", "MG Road")
    system.register_camera("CAM002", "Anna Salai Signal", "Anna Salai")

    system.start()  # density monitor now running in the background

    system.on_ocr_result("CAM001", "TN01AB1234", 0.96, "2026-09-14 08:15:00")
    system.on_ocr_result("CAM002", "TN01AB1234", 0.89, "2026-09-14 08:32:00")
    system.on_ocr_result("CAM001", "TN22CD5678", 0.94, "2026-09-14 08:20:00")
    system.on_ocr_result("CAM001", "TN22CD5678", 0.91)  # no timestamp -> auto current time

    system.blacklist_plate("TN01AB1234", "Reported stolen")

    system.print_report("TN01AB1234")
    system.print_report("TN99ZZ0000")  # not found case

    print("\nLast known location, TN22CD5678:")
    print(system.last_known_location("TN22CD5678"))

    system.stop()  # flushes the density buffer before we read it back
    print("\nTraffic density (10-min buckets):")
    for row in system.get_density():
        print(row)

    system.close()  # only close the DB once we're done reading