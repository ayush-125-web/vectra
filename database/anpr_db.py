"""
ANPR City-Wide Vehicle Tracking - Database Layer
==================================================
Schema creation + inserts ONLY. Queries live in anpr_query.py, density
logic lives in den_monitor.py.

Concurrency notes for the parallel runner:
    - WAL journal mode, so a reader never blocks a writer.
    - busy_timeout, so a locked DB retries instead of raising instantly.
    - self.lock, held around every write. The density monitor's
      background thread shares this connection, so without it two
      threads can interleave on the same cursor and corrupt a commit.

Goes to: database/anpr_db.py
"""

import sqlite3
import threading
from datetime import datetime

DB_NAME = "anpr_system.db"


def current_timestamp() -> str:
    """Returns 'now' in the format used everywhere in the DB."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ANPRDatabase:
    """
    Usage:
        db = ANPRDatabase()                      # connects + creates schema
        db.add_camera("CAM001", "MG Road Junction")
        db.add_detection("TN01AB1234", "CAM001", 0.96)   # timestamp auto-filled
    """

    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        # Guards every write. RLock so a write can call another write.
        self.lock = threading.RLock()
        self.conn = self.connect()
        self.create_schema()

    # -----------------------------------------------------------------
    # Connection / schema
    # -----------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        # check_same_thread=False because the density monitor's background
        # thread also uses this same connection.
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.row_factory = sqlite3.Row
        return conn

    def create_schema(self) -> None:
        with self.lock:
            cur = self.conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id     TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
                road_name     TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                plate_number    TEXT PRIMARY KEY,
                first_seen      TEXT,
                last_seen       TEXT,
                last_camera_id  TEXT,
                notes           TEXT,
                FOREIGN KEY (last_camera_id) REFERENCES cameras(camera_id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                detection_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number     TEXT NOT NULL,
                camera_id        TEXT NOT NULL,
                timestamp        TEXT NOT NULL,
                confidence_score REAL,
                FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number),
                FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                blacklist_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number  TEXT NOT NULL,
                reason        TEXT,
                flagged_on    TEXT,
                status        TEXT DEFAULT 'active',
                FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS traffic_density (
                density_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id     TEXT NOT NULL,
                bucket_start  TEXT NOT NULL,
                vehicle_count INTEGER NOT NULL,
                FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
            )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_plate ON detections(plate_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_time ON detections(timestamp)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_camera ON detections(camera_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_density_bucket ON traffic_density(bucket_start)")

            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    # -----------------------------------------------------------------
    # Inserts
    # -----------------------------------------------------------------

    def add_camera(self, camera_id, location_name, road_name=None) -> None:
        """Register a camera. Safe to call repeatedly (ignores duplicates)."""
        with self.lock:
            self.conn.execute("""
                INSERT OR IGNORE INTO cameras (camera_id, location_name, road_name)
                VALUES (?, ?, ?)
            """, (camera_id, location_name, road_name))
            self.conn.commit()

    def add_detection(self, plate_number, camera_id, confidence_score, timestamp=None) -> str:
        """
        Call this once per verified plate. Returns the timestamp actually
        stored (handy for logging).
        """
        timestamp = timestamp or current_timestamp()

        with self.lock:
            cur = self.conn.cursor()

            cur.execute("SELECT 1 FROM vehicles WHERE plate_number = ?", (plate_number,))
            exists = cur.fetchone()

            if exists is None:
                cur.execute("""
                    INSERT INTO vehicles (plate_number, first_seen, last_seen, last_camera_id)
                    VALUES (?, ?, ?, ?)
                """, (plate_number, timestamp, timestamp, camera_id))
            else:
                # last_seen / last_camera_id only move forward, in case
                # detections arrive out of order across cameras - which
                # is exactly what happens on a parallel run.
                cur.execute("""
                    UPDATE vehicles
                    SET last_seen = ?, last_camera_id = ?
                    WHERE plate_number = ? AND (last_seen IS NULL OR ? >= last_seen)
                """, (timestamp, camera_id, plate_number, timestamp))
                cur.execute("""
                    UPDATE vehicles SET first_seen = ?
                    WHERE plate_number = ? AND (first_seen IS NULL OR ? < first_seen)
                """, (timestamp, plate_number, timestamp))

            cur.execute("""
                INSERT INTO detections (plate_number, camera_id, timestamp, confidence_score)
                VALUES (?, ?, ?, ?)
            """, (plate_number, camera_id, timestamp, confidence_score))

            self.conn.commit()

        return timestamp

    def add_to_blacklist(self, plate_number, reason, flagged_on=None) -> None:
        flagged_on = flagged_on or current_timestamp()

        with self.lock:
            self.conn.execute("""
                INSERT INTO blacklist (plate_number, reason, flagged_on)
                VALUES (?, ?, ?)
            """, (plate_number, reason, flagged_on))
            self.conn.commit()

    # -----------------------------------------------------------------
    # Debug helper
    # -----------------------------------------------------------------

    def dump_table(self, table_name: str) -> list:
        """Print and return every row of a given table."""
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM {table_name}")
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            print(row)
        return rows