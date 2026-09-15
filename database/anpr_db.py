"""
ANPR City-Wide Vehicle Tracking - Database Layer
==================================================
Schema creation + inserts ONLY (cameras, vehicles, detections,
blacklist). No query/report logic lives here - that's anpr_query.py.
No traffic-density logic lives here either - that's density_monitor.py.

Kept deliberately small: no lat/lon on cameras (we're not doing
distance/speed math), and add_detection() only needs what the OCR
model actually gives you - plate number + confidence + time.
"""

import sqlite3
from datetime import datetime

DB_NAME = "anpr_system.db"


def current_timestamp() -> str:
    """
    Returns 'now' as a string in the format used everywhere in the DB.
    This is what gets called automatically at insert time, so nothing
    upstream has to pass a timestamp by hand if it doesn't have one.
    """
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
        conn.row_factory = sqlite3.Row
        return conn

    def create_schema(self) -> None:
        cur = self.conn.cursor()

        # No latitude/longitude - this project doesn't need distance or
        # speed calculations, just "which camera, when".
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

        # This matches what the OCR model actually hands us: plate,
        # confidence, time - plus which camera, which the caller knows.
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

        # 10-minute bucketed counts, written by density_monitor.py.
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
        self.conn.close()

    # -----------------------------------------------------------------
    # Inserts
    # -----------------------------------------------------------------

    def add_camera(self, camera_id, location_name, road_name=None) -> None:
        """Register a camera. Safe to call repeatedly (ignores duplicates)."""
        self.conn.execute("""
            INSERT OR IGNORE INTO cameras (camera_id, location_name, road_name)
            VALUES (?, ?, ?)
        """, (camera_id, location_name, road_name))
        self.conn.commit()

    def add_detection(self, plate_number, camera_id, confidence_score, timestamp=None) -> str:
        """
        Call this once per OCR hit - this is what your friend's model
        result plugs straight into: plate number, confidence, and
        (optionally) a timestamp. If timestamp isn't given, or your
        friend's clock isn't reliable, current_timestamp() is used
        instead so every row still gets stamped automatically.

        Returns the timestamp actually stored (handy for logging).
        """
        timestamp = timestamp or current_timestamp()
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
            # detections arrive slightly out of order across cameras.
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
        self.conn.execute("""
            INSERT INTO blacklist (plate_number, reason, flagged_on)
            VALUES (?, ?, ?)
        """, (plate_number, reason, flagged_on))
        self.conn.commit()

    # -----------------------------------------------------------------
    # Debug helper
    # -----------------------------------------------------------------

    def dump_table(self, table_name: str) -> list:
        """Print and return every row of a given table - quick debugging aid."""
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM {table_name}")
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            print(row)
        return rows