"""
Demo - shows how anpr_db, anpr_query and density_monitor fit together.
"""

from anpr_db import ANPRDatabase
from anpr_query import PlateQueryEngine
from density_monitor import TrafficDensityMonitor


def on_ocr_result(db, monitor, camera_id, plate_number, confidence_score, timestamp=None):
    """
    This is the function your friend's OCR pipeline should call for
    every plate it reads: plate number + confidence + (optionally) time.
    Everything else - vehicle bookkeeping, timestamping, density
    counting - happens automatically from here.
    """
    stored_ts = db.add_detection(plate_number, camera_id, confidence_score, timestamp)
    monitor.record(camera_id)
    return stored_ts


if __name__ == "__main__":
    db = ANPRDatabase()

    db.add_camera("CAM001", "MG Road Junction", "MG Road")
    db.add_camera("CAM002", "Anna Salai Signal", "Anna Salai")

    monitor = TrafficDensityMonitor(db)
    monitor.start()  # always running in the background from here on

    # Simulating what your friend's OCR model sends over (plate, confidence,
    # and here we also pass a time just to show it's optional either way):
    on_ocr_result(db, monitor, "CAM001", "TN01AB1234", 0.96, "2026-09-14 08:15:00")
    on_ocr_result(db, monitor, "CAM002", "TN01AB1234", 0.89, "2026-09-14 08:32:00")
    on_ocr_result(db, monitor, "CAM001", "TN22CD5678", 0.94, "2026-09-14 08:20:00")
    on_ocr_result(db, monitor, "CAM001", "TN22CD5678", 0.91)  # no timestamp -> auto current time

    db.add_to_blacklist("TN01AB1234", "Reported stolen")

    engine = PlateQueryEngine(db)
    engine.print_report("TN01AB1234")
    engine.print_report("TN99ZZ0000")  # not found case

    print("\nLast known location, TN22CD5678:")
    print(engine.get_last_known_location("TN22CD5678"))

    # In real use you'd just let the background thread flush on its own
    # every 10 minutes. For the demo we stop (which flushes) so the
    # buffered counts actually land in the table before we print them.
    monitor.stop()
    print("\nTraffic density (10-min buckets):")
    for row in monitor.get_density():
        print(row)

    db.close()