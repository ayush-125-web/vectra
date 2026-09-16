"""
ANPR City-Wide Vehicle Tracking - Traffic Density Monitor
=============================================================
Keeps an in-memory buffer of the DISTINCT plates seen per camera and
flushes it into `traffic_density` every 10 minutes on a background
thread.

Deduped by plate within each bucket on purpose: a car sitting at a
signal can get OCR'd across several frames, and that shouldn't count as
several vehicles. The same plate in a LATER bucket is a separate pass
and does count again.

Only change for the parallel runner: _flush() now copies the buffer out
first, releases the buffer lock, then takes the DB's write lock. This
stops the background thread from interleaving with the main thread's
detection inserts on the shared SQLite connection.

Goes to: database/den_monitor.py
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
        self._buffer = defaultdict(set)      # camera_id -> {plate, ...}
        self._buffer_lock = threading.Lock()
        self._current_bucket = current_bucket_start()
        self._stop_event = threading.Event()
        self._thread = None

    def record(self, camera_id: str, plate_number: str) -> None:
        """
        Call once per detection. Cheap enough for every OCR hit, and a
        set means the same plate twice in one bucket only counts once.
        Thread-safe, so parallel workers could call it directly.
        """
        with self._buffer_lock:
            self._buffer[camera_id].add(plate_number)

    def _flush(self) -> None:
        """Writes the current buffer to the DB (one row per camera), then clears it."""
        with self._buffer_lock:
            if not self._buffer:
                self._current_bucket = current_bucket_start()
                return

            snapshot = {cam: len(plates) for cam, plates in self._buffer.items()}
            bucket = self._current_bucket

            self._buffer.clear()
            self._current_bucket = current_bucket_start()

        # DB write happens outside the buffer lock, and under the DB's
        # own lock so it can't interleave with a detection insert.
        with self.db.lock:
            cur = self.db.conn.cursor()
            for camera_id, count in snapshot.items():
                cur.execute("""
                    INSERT INTO traffic_density (camera_id, bucket_start, vehicle_count)
                    VALUES (?, ?, ?)
                """, (camera_id, bucket, count))
            self.db.conn.commit()

    def _run_loop(self) -> None:
        """Background loop - wakes every `bucket_minutes` and flushes."""
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
        """Stops the loop and flushes whatever is still in the buffer."""
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