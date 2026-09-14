"""
ANPR System Integration
=======================
Connects the existing modules WITHOUT modifying them.

Flow:
    Camera video
        -> PlateDetector
        -> final vector
        -> ANPRDatabase
        -> TrafficDensityMonitor

    ANPRDatabase
        -> PlateQueryEngine
        -> dashboard/API can read the results later

The existing files are kept separate. This file is only the coordinator.
"""

from plateDetection import PlateDetector
from anpr_db import ANPRDatabase
from anpr_query import PlateQueryEngine
from den_monitor import TrafficDensityMonitor


class ANPRSystem:
    """Coordinates plate detection, database storage, queries and density."""

    def __init__(
        self,
        db_name="anpr_system.db",
        model_path="models/best.pt",
        frequency_threshold=5,
    ):
        # 1. Database layer
        self.db = ANPRDatabase(db_name)

        # 2. Plate detection layer
        self.detector = PlateDetector(
            model_path=model_path,
            frequency_threshold=frequency_threshold,
        )

        # 3. Query layer - reads the same database
        self.query_engine = PlateQueryEngine(self.db)

        # 4. Traffic-density layer - uses the same database
        self.density_monitor = TrafficDensityMonitor(self.db)

    def start(self):
        """Start the 10-minute traffic-density monitor."""
        self.density_monitor.start()

    def stop(self):
        """Stop the density monitor and flush its current bucket."""
        self.density_monitor.stop()
        self.db.close()

    def register_camera(self, camera_id, location_name, road_name=None):
        """Register a camera before processing its video."""
        self.db.add_camera(camera_id, location_name, road_name)

    def process_camera(self, camera_id, video_path):
        """
        Process ONE camera.

        PlateDetector returns:
            [plate_number, frequency, average_confidence]

        Each item is then sent to:
            ANPRDatabase.add_detection()
            TrafficDensityMonitor.record()
        """

        print(f"\n{'=' * 60}")
        print(f"PROCESSING CAMERA: {camera_id}")
        print(f"VIDEO: {video_path}")
        print(f"{'=' * 60}")

        # Detect plates from this camera's video.
        final_vector = self.detector.process_video(video_path)

        print(f"\nFINAL VECTOR FROM {camera_id}:")
        print(final_vector)

        # Store every verified plate from the vector.
        for plate_number, frequency, avg_confidence in final_vector:
            # ANPR database stores the plate, camera and confidence.
            timestamp = self.db.add_detection(
                plate_number=plate_number,
                camera_id=camera_id,
                confidence_score=avg_confidence,
            )

            # Density monitor counts a plate only once per 10-minute bucket.
            self.density_monitor.record(
                camera_id=camera_id,
                plate_number=plate_number,
            )

            print(
                f"DB UPDATED | camera={camera_id} | plate={plate_number} "
                f"| frequency={frequency} | confidence={avg_confidence} "
                f"| time={timestamp}"
            )

        return final_vector

    def process_all_cameras(self, cameras):
        """
        Process multiple cameras.

        cameras format:
        {
            "CAM-01": "videos/cam1.mp4",
            "CAM-02": "videos/cam2.mp4",
            "CAM-03": "videos/cam3.mp4",
        }
        """
        results = {}

        for camera_id, video_path in cameras.items():
            results[camera_id] = self.process_camera(
                camera_id=camera_id,
                video_path=video_path,
            )

        return results

    # ---------------------------
    # Query layer shortcuts
    # ---------------------------

    def get_vehicle(self, plate_number):
        """Get the complete trajectory report for a plate."""
        return self.query_engine.query(plate_number)

    def get_trajectory(self, plate_number, start_time=None, end_time=None):
        """Get all camera detections for one plate."""
        return self.query_engine.get_trajectory(
            plate_number,
            start_time,
            end_time,
        )

    def get_last_location(self, plate_number):
        """Get the latest known camera/location for a plate."""
        return self.query_engine.get_last_known_location(plate_number)

    def get_density(self, camera_id=None, start_time=None, end_time=None):
        """Read traffic-density records."""
        return self.density_monitor.get_density(
            camera_id,
            start_time,
            end_time,
        )


# ================================================================
# EXAMPLE RUN
# ================================================================

if __name__ == "__main__":

    system = ANPRSystem(
        db_name="anpr_system.db",
        model_path="models/best.pt",
        frequency_threshold=5,
    )

    try:
        # Register the cameras.
        system.register_camera("CAM-01", "Main Road Junction")
        system.register_camera("CAM-02", "Market Street")
        system.register_camera("CAM-03", "Civic Center")

        # Start traffic-density monitoring.
        system.start()

        # Process each camera.
        cameras = {
            "CAM-01": "videos/cam1.mp4",
            "CAM-02": "videos/cam2.mp4",
            "CAM-03": "videos/cam3.mp4",
        }

        results = system.process_all_cameras(cameras)

        print("\nALL CAMERA RESULTS")
        print(results)

        # Example query after detection.
        # report = system.get_vehicle("TN01AB1234")
        # print(report)

    finally:
        system.stop()
