"""
ANPR System Integration
=======================
Coordinator only. Connects the existing modules without duplicating
their logic.

    Camera video -> PlateDetector -> final vector
                 -> ANPRDatabase  -> TrafficDensityMonitor
    ANPRDatabase -> PlateQueryEngine -> dashboard / API

Three ways to run the cameras:

    process_all_cameras(cameras)             one after another
    process_all_cameras_parallel(cameras)    all at once, videos run once
    (see anpr_live.py)                       all at once, videos loop forever

Goes to: database/anpr_system.py
"""

from database.anpr_db import ANPRDatabase
from database.anpr_query import PlateQueryEngine
from database.den_monitor import TrafficDensityMonitor


class ANPRSystem:
    """Coordinates plate detection, database storage, queries and density."""

    def __init__(
        self,
        db_name="anpr_system.db",
        model_path="ai/models/best.pt",
        frequency_threshold=5,
        show=False,
    ):
        # 1. Database layer
        self.db = ANPRDatabase(db_name)

        # 2. Detection settings. The detector itself is built lazily -
        #    a parallel/live run never uses this one (each worker builds
        #    its own), so there is no point loading the models here.
        self.model_path = model_path
        self.frequency_threshold = frequency_threshold
        self.show = show
        self._detector = None

        # 3. Query layer - reads the same database
        self.query_engine = PlateQueryEngine(self.db)

        # 4. Traffic-density layer - uses the same database
        self.density_monitor = TrafficDensityMonitor(self.db)

    @property
    def detector(self):
        """Shared detector for sequential runs only. Built on first use."""
        if self._detector is None:
            from ai.detection.plateDetection import PlateDetector

            self._detector = PlateDetector(
                model_path=self.model_path,
                frequency_threshold=self.frequency_threshold,
                show=self.show,
            )
        return self._detector

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def start(self):
        """Start the 10-minute traffic-density monitor."""
        self.density_monitor.start()

    def stop(self):
        """Stop the density monitor, flush its bucket, close the DB."""
        self.density_monitor.stop()
        self.db.close()

    def register_camera(self, camera_id, location_name, road_name=None):
        self.db.add_camera(camera_id, location_name, road_name)

    # -----------------------------------------------------------------
    # Storage
    # -----------------------------------------------------------------

    def _ensure_camera(self, camera_id):
        """
        detections.camera_id is a foreign key, so an unregistered camera
        would make every insert fail. Auto-register it instead of
        losing the whole video's results.
        """
        cur = self.db.conn.cursor()
        cur.execute(
            "SELECT 1 FROM cameras WHERE camera_id = ?", (camera_id,)
        )

        if cur.fetchone() is None:
            print(f"[{camera_id}] not registered - auto-registering")
            self.db.add_camera(camera_id, camera_id)

    def store_vector(self, camera_id, final_vector):
        """
        Write a whole batch (one camera's final vector) to the DB in one
        go. Used by the sequential and parallel (one-shot) run modes,
        where a camera's video actually finishes.

        Call this from the MAIN thread only - it is the single writer
        for SQLite, which is what lets detection itself run in parallel.
        """
        self._ensure_camera(camera_id)

        for plate_number, frequency, avg_confidence in final_vector:
            self.store_single_detection(camera_id, plate_number, avg_confidence)

            print(
                f"DB UPDATED | camera={camera_id} | plate={plate_number} "
                f"| frequency={frequency} | confidence={avg_confidence}"
            )

        return final_vector

    def store_single_detection(self, camera_id, plate_number, confidence):
        """
        Write ONE verified plate to the DB. Used by live mode, where
        results trickle in one at a time via a callback instead of
        arriving as a batch at the end of a video.

        Call this from the MAIN thread only, same rule as store_vector.
        """
        self._ensure_camera(camera_id)

        timestamp = self.db.add_detection(
            plate_number=plate_number,
            camera_id=camera_id,
            confidence_score=confidence,
        )

        self.density_monitor.record(
            camera_id=camera_id,
            plate_number=plate_number,
        )

        return timestamp

    # -----------------------------------------------------------------
    # Processing
    # -----------------------------------------------------------------

    def process_camera(self, camera_id, video_path):
        """Process ONE camera on this thread (blocking), video runs once."""
        print(f"\n{'=' * 60}")
        print(f"PROCESSING CAMERA: {camera_id}")
        print(f"VIDEO: {video_path}")
        print(f"{'=' * 60}")

        final_vector = self.detector.process_video(video_path, tag=camera_id)

        print(f"\nFINAL VECTOR FROM {camera_id}:")
        print(final_vector)

        return self.store_vector(camera_id, final_vector)

    def process_all_cameras(self, cameras):
        """
        Sequential: one camera at a time, each video runs once.

        cameras = {"CAM-01": "data/videos/cam1.mp4", ...}
        """
        return {
            camera_id: self.process_camera(camera_id, video_path)
            for camera_id, video_path in cameras.items()
        }

    def process_all_cameras_parallel(
        self,
        cameras,
        workers=2,
        mode="thread",
        frame_skip=1,
        threads_per_worker=1,
    ):
        """
        Parallel: several cameras at once, each video runs once and the
        call returns when every video has finished.

        cameras = {"CAM-01": "data/videos/cam1.mp4", ...}
        """
        from database.anpr_parallel import run_cameras_parallel

        return run_cameras_parallel(
            self,
            cameras,
            workers=workers,
            mode=mode,
            frame_skip=frame_skip,
            threads_per_worker=threads_per_worker,
        )

    def run_realtime(self, cameras, frame_skip=1):
        """
        Each video plays through ONCE, several at a time, but a plate is
        stored the INSTANT it crosses frequency_threshold - not batched
        up and written only after the whole video finishes. Returns
        when every camera's video has ended. See anpr_live.py.

        cameras = {"CAM-01": "data/videos/cam1.mp4", ...}
        """
        from database.anpr_live import run_realtime

        return run_realtime(self, cameras, frame_skip=frame_skip)

    def run_live(self, cameras, frame_skip=2):
        """
        Same real-time storage as run_realtime(), but every video loops
        forever, acting like a permanent camera feed. Runs until
        Ctrl+C. See anpr_live.py.

        cameras = {"CAM-01": "data/videos/cam1.mp4", ...}
        """
        from database.anpr_live import run_live

        return run_live(self, cameras, frame_skip=frame_skip)

    # -----------------------------------------------------------------
    # Query shortcuts
    # -----------------------------------------------------------------

    def get_vehicle(self, plate_number):
        return self.query_engine.query(plate_number)

    def get_trajectory(self, plate_number, start_time=None, end_time=None):
        return self.query_engine.get_trajectory(
            plate_number, start_time, end_time
        )

    def get_last_location(self, plate_number):
        return self.query_engine.get_last_known_location(plate_number)

    def get_density(self, camera_id=None, start_time=None, end_time=None):
        return self.density_monitor.get_density(
            camera_id, start_time, end_time
        )