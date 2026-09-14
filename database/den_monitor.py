"""
ANPR City-Wide Vehicle Tracking - Traffic Density Monitor
=============================================================
The "always running" part: keeps an in-memory buffer of the DISTINCT
plates seen per camera, and flushes it into `traffic_density` every
10 minutes on a background thread. Nobody has to ask for density -
it's just kept up to date on its own the whole time the system runs.

Deduped by plate within each bucket on purpose: a car sitting at a
signal can get OCR'd across several frames, and that shouldn't count
as several vehicles. The same plate showing up again in a LATER
bucket is a separate pass and does count again.

Usage:
    db = ANPRDatabase()
    monitor = TrafficDensityMonitor(db)
    monitor.start()                 # runs in the background from here on

    # every time a detection comes in, from anywhere in your pipeline:
    monitor.record(camera_id, plate_number)

    monitor.get_density()           # read back the bucketed counts
    monitor.stop()                  # when shutting down
"""

import threading
from collections import defaultdict
from datetime import datetime

BUCKET_MINUTES = 10


def current_bucket_start(dt: datetime = None) -> str:
    """Rounds a timestamp down to the start of its 10-minute bucket."""
    dt = dt or datetime.now()
    floored_minute = (dt.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    bucket = dt.replace(minute=floored_minute, second=0, microsecond=0)
    return bucket.strftime("%Y-%m-%d %H:%M:%S")


class TrafficDensityMonitor:

    def __init__(self, database, bucket_minutes: int = BUCKET_MINUTES):
        self.db = database
        self.bucket_minutes = bucket_minutes
        self._buffer = defaultdict(set)          # camera_id -> {plate_number, ...}, current bucket only
        self._buffer_lock = threading.Lock()
        self._current_bucket = current_bucket_start()
        self._stop_event = threading.Event()
        self._thread = None

    def record(self, camera_id: str, plate_number: str) -> None:
        """
        Call this once per detection. Adds the plate to an in-memory
        set for that camera's current bucket - cheap enough to call on
        every single OCR hit without touching the database, and a set
        means the same plate showing up twice in one bucket (e.g. a
        car re-detected across a few frames while it's at a signal)
        only counts once.
        """
        with self._buffer_lock:
            self._buffer[camera_id].add(plate_number)

    def _flush(self) -> None:
        """Writes the current buffer to the DB (one row per camera), then clears it."""
        with self._buffer_lock:
            if self._buffer:
                bucket = self._current_bucket
                cur = self.db.conn.cursor()
                for camera_id, plates in self._buffer.items():
                    cur.execute("""
                        INSERT INTO traffic_density (camera_id, bucket_start, vehicle_count)
                        VALUES (?, ?, ?)
                    """, (camera_id, bucket, len(plates)))
                self.db.conn.commit()
            self._buffer.clear()
            self._current_bucket = current_bucket_start()

    def _run_loop(self) -> None:
        """Background loop - wakes up every `bucket_minutes` and flushes the buffer."""
        while not self._stop_event.is_set():
            woke_early = self._stop_event.wait(self.bucket_minutes * 60)
            if not woke_early:
                self._flush()

    def start(self) -> None:
        """Starts the always-running density job as a daemon thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the loop and flushes whatever is still sitting in the buffer."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._flush()

    # -----------------------------------------------------------------
    # Reading density back out
    # -----------------------------------------------------------------

    def get_density(self, camera_id=None, start_time=None, end_time=None) -> list:
        """Reads back the 10-min bucketed counts already written to the DB."""
        query = "SELECT camera_id, bucket_start, vehicle_count FROM traffic_density WHERE 1=1"
        params = []
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if start_time:
            query += " AND bucket_start >= ?"
            params.append(start_time)
        if end_time:
            query += " AND bucket_start <= ?"
            params.append(end_time)
        query += " ORDER BY bucket_start ASC"

        cur = self.db.conn.cursor()
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]