import sqlite3
import math
from datetime import datetime


DB_NAME = "anpr_system.db"



def get_connection(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def create_schema(conn):
    cur = conn.cursor()

    # Cameras: static metadata about each ANPR/CCTV node
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cameras (
        camera_id       TEXT PRIMARY KEY,
        location_name   TEXT NOT NULL,
        latitude        REAL NOT NULL,
        longitude       REAL NOT NULL,
        road_name       TEXT,
        direction_faced TEXT,               -- e.g. 'North', 'Inbound'
        sector          TEXT                -- city zone/sector for aggregation
    )
    """)

    # Vehicles: one row per unique (normalized) plate number
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        plate_number    TEXT PRIMARY KEY,   -- normalized/corrected plate
        first_seen      TEXT,               -- timestamp of first detection
        last_seen       TEXT,               -- timestamp of most recent detection
        vehicle_type    TEXT,               -- optional: car/bike/truck if classified
        notes           TEXT
    )
    """)

    # Detections: one row per individual sighting/frame event from the OCR pipeline
    cur.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        detection_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number       TEXT NOT NULL,
        raw_ocr_text        TEXT,             -- unprocessed OCR output (before correction)
        camera_id            TEXT NOT NULL,
        timestamp             TEXT NOT NULL,    -- ISO format: 'YYYY-MM-DD HH:MM:SS'
        confidence_score     REAL,             -- OCR confidence, 0.0 - 1.0
        visibility_state     TEXT,             -- e.g. 'clear', 'angled', 'blurred',
                                                --      'dirty_plate', 'low_light'
        image_path            TEXT,             -- path/URL to the cropped plate image
        FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number),
        FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
    )
    """)

    # Blacklist / alerts
    cur.execute("""
    CREATE TABLE IF NOT EXISTS blacklist (
        blacklist_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number    TEXT NOT NULL,
        reason          TEXT,
        flagged_on      TEXT,
        status          TEXT DEFAULT 'active',   -- 'active' / 'resolved'
        FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number)
    )
    """)

    # Indexes for the query patterns we'll actually use
    cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_plate ON detections(plate_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_time ON detections(timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_detections_camera ON detections(camera_id)")

    conn.commit()


# ---------------------------------------------------------------------
# 2. INSERT / INGEST FUNCTIONS  (what your friend's OCR script feeds into)
# ---------------------------------------------------------------------

def add_camera(conn, camera_id, location_name, latitude, longitude,
                road_name=None, direction_faced=None, sector=None):
    conn.execute("""
        INSERT OR IGNORE INTO cameras
        (camera_id, location_name, latitude, longitude, road_name, direction_faced, sector)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (camera_id, location_name, latitude, longitude, road_name, direction_faced, sector))
    conn.commit()


def add_detection(conn, plate_number, raw_ocr_text, camera_id, timestamp,
                   confidence_score, visibility_state, image_path=None):
    """
    Call this once per OCR detection event.
    `plate_number` should be the corrected/normalized plate (uppercase,
    no spaces/dashes) — keep `raw_ocr_text` as whatever OCR actually output,
    so noisy reads don't corrupt the vehicle record.
    """
    cur = conn.cursor()

    # Ensure the vehicle exists, then update first/last seen
    cur.execute("SELECT plate_number, first_seen FROM vehicles WHERE plate_number = ?",
                (plate_number,))
    existing = cur.fetchone()

    if existing is None:
        cur.execute("""
            INSERT INTO vehicles (plate_number, first_seen, last_seen)
            VALUES (?, ?, ?)
        """, (plate_number, timestamp, timestamp))
    else:
        cur.execute("""
            UPDATE vehicles
            SET last_seen = ?
            WHERE plate_number = ? AND (last_seen IS NULL OR ? > last_seen)
        """, (timestamp, plate_number, timestamp))
        cur.execute("""
            UPDATE vehicles
            SET first_seen = ?
            WHERE plate_number = ? AND (first_seen IS NULL OR ? < first_seen)
        """, (timestamp, plate_number, timestamp))

    # Insert the detection event itself
    cur.execute("""
        INSERT INTO detections
        (plate_number, raw_ocr_text, camera_id, timestamp, confidence_score,
         visibility_state, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (plate_number, raw_ocr_text, camera_id, timestamp, confidence_score,
          visibility_state, image_path))

    conn.commit()


def add_to_blacklist(conn, plate_number, reason, flagged_on=None):
    flagged_on = flagged_on or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO blacklist (plate_number, reason, flagged_on)
        VALUES (?, ?, ?)
    """, (plate_number, reason, flagged_on))
    conn.commit()


# ---------------------------------------------------------------------
# 3. TRAJECTORY TRACKING  (Single Plate Trajectory module)
# ---------------------------------------------------------------------

def get_plate_trajectory(conn, plate_number, start_time=None, end_time=None):
    """
    Returns the full chronological path of a single vehicle:
    camera location, coordinates, timestamp, and visibility state
    for every detection, ordered by time.
    """
    query = """
        SELECT d.timestamp, d.plate_number, d.confidence_score, d.visibility_state,
               c.camera_id, c.location_name, c.latitude, c.longitude, c.road_name
        FROM detections d
        JOIN cameras c ON d.camera_id = c.camera_id
        WHERE d.plate_number = ?
    """
    params = [plate_number]

    if start_time:
        query += " AND d.timestamp >= ?"
        params.append(start_time)
    if end_time:
        query += " AND d.timestamp <= ?"
        params.append(end_time)

    query += " ORDER BY d.timestamp ASC"

    cur = conn.cursor()
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------
# 3b. PLATE QUERY ENGINE  (your friend's "search a plate -> full report" task)
# ---------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two GPS points, in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class PlateQueryEngine:
    """
    Takes a plate number as a query and returns a complete trajectory
    report: does it exist in the DB, every camera it crossed (in order),
    timestamps, estimated speed between consecutive cameras, total
    cameras crossed, first/last appearance, and whether it's blacklisted.

    Usage:
        conn = get_connection()
        engine = PlateQueryEngine(conn)
        report = engine.query("TN01AB1234")
    """

    def __init__(self, conn):
        self.conn = conn

    def exists(self, plate_number):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM vehicles WHERE plate_number = ?", (plate_number,))
        return cur.fetchone() is not None

    def _raw_detections(self, plate_number, start_time=None, end_time=None):
        """Chronological detections joined with camera info (reuses the
        trajectory function already defined above)."""
        return get_plate_trajectory(self.conn, plate_number, start_time, end_time)

    def _compute_hops(self, detections):
        """
        Builds camera-to-camera hop info: distance, time elapsed, and
        estimated speed (km/h) between each consecutive pair of detections.
        """
        hops = []
        for prev, curr in zip(detections, detections[1:]):
            t1 = datetime.strptime(prev["timestamp"], "%Y-%m-%d %H:%M:%S")
            t2 = datetime.strptime(curr["timestamp"], "%Y-%m-%d %H:%M:%S")
            elapsed_hours = (t2 - t1).total_seconds() / 3600.0

            distance_km = _haversine_km(
                prev["latitude"], prev["longitude"],
                curr["latitude"], curr["longitude"]
            )

            speed_kmh = round(distance_km / elapsed_hours, 2) if elapsed_hours > 0 else None

            hops.append({
                "from_camera": prev["camera_id"],
                "from_location": prev["location_name"],
                "to_camera": curr["camera_id"],
                "to_location": curr["location_name"],
                "distance_km": round(distance_km, 3),
                "time_elapsed_minutes": round(elapsed_hours * 60, 1),
                "estimated_speed_kmh": speed_kmh
            })
        return hops

    def _is_blacklisted(self, plate_number):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT reason, flagged_on FROM blacklist
            WHERE plate_number = ? AND status = 'active'
            ORDER BY flagged_on DESC LIMIT 1
        """, (plate_number,))
        row = cur.fetchone()
        return dict(row) if row else None

    def query(self, plate_number, start_time=None, end_time=None):
        """
        Main entry point. Returns a dict:
        {
            "plate_number": ...,
            "found": True/False,
            "total_cameras_crossed": int,
            "total_detections": int,
            "first_camera": {...},
            "last_camera": {...},
            "route": [ ...chronological list of every detection... ],
            "hops": [ ...distance/time/speed between consecutive cameras... ],
            "average_speed_kmh": float or None,
            "blacklist_status": {...} or None
        }
        """
        plate_number = plate_number.strip().upper()

        if not self.exists(plate_number):
            return {
                "plate_number": plate_number,
                "found": False,
                "message": "No record found for this plate in the database."
            }

        detections = self._raw_detections(plate_number, start_time, end_time)

        if not detections:
            return {
                "plate_number": plate_number,
                "found": False,
                "message": "Plate exists in vehicle records but has no detections in this time range."
            }

        hops = self._compute_hops(detections)
        speeds = [h["estimated_speed_kmh"] for h in hops if h["estimated_speed_kmh"] is not None]
        avg_speed = round(sum(speeds) / len(speeds), 2) if speeds else None

        unique_cameras = {d["camera_id"] for d in detections}

        return {
            "plate_number": plate_number,
            "found": True,
            "total_cameras_crossed": len(unique_cameras),
            "total_detections": len(detections),
            "first_camera": {
                "camera_id": detections[0]["camera_id"],
                "location_name": detections[0]["location_name"],
                "timestamp": detections[0]["timestamp"]
            },
            "last_camera": {
                "camera_id": detections[-1]["camera_id"],
                "location_name": detections[-1]["location_name"],
                "timestamp": detections[-1]["timestamp"]
            },
            "route": detections,
            "hops": hops,
            "average_speed_kmh": avg_speed,
            "blacklist_status": self._is_blacklisted(plate_number)
        }

    def print_report(self, plate_number, start_time=None, end_time=None):
        """Pretty-prints the trajectory report to console — handy for demos."""
        report = self.query(plate_number, start_time, end_time)

        print(f"\n{'='*50}")
        print(f"TRAJECTORY REPORT: {report['plate_number']}")
        print(f"{'='*50}")

        if not report["found"]:
            print(report["message"])
            return report

        print(f"Total cameras crossed : {report['total_cameras_crossed']}")
        print(f"Total detections      : {report['total_detections']}")
        print(f"First seen            : {report['first_camera']['location_name']} "
              f"({report['first_camera']['camera_id']}) at {report['first_camera']['timestamp']}")
        print(f"Last seen             : {report['last_camera']['location_name']} "
              f"({report['last_camera']['camera_id']}) at {report['last_camera']['timestamp']}")
        print(f"Average speed         : {report['average_speed_kmh']} km/h"
              if report['average_speed_kmh'] else "Average speed         : N/A (single detection)")

        if report["blacklist_status"]:
            print(f"⚠ BLACKLISTED         : {report['blacklist_status']['reason']} "
                  f"(flagged {report['blacklist_status']['flagged_on']})")

        print("\nFull route:")
        for i, stop in enumerate(report["route"], 1):
            print(f"  {i}. {stop['timestamp']} | {stop['location_name']} "
                  f"({stop['camera_id']}) | visibility={stop['visibility_state']} "
                  f"| confidence={stop['confidence_score']}")

        if report["hops"]:
            print("\nSpeed between cameras:")
            for hop in report["hops"]:
                print(f"  {hop['from_location']} -> {hop['to_location']}: "
                      f"{hop['distance_km']} km in {hop['time_elapsed_minutes']} min "
                      f"= {hop['estimated_speed_kmh']} km/h")

        return report


# ---------------------------------------------------------------------
# 4. MACRO TRAFFIC ANALYTICS  (Traffic Analytics Dashboard module)
# ---------------------------------------------------------------------

def get_traffic_density_by_camera(conn, start_time=None, end_time=None):
    """Vehicle count per camera — feeds the heatmap layer."""
    query = """
        SELECT c.camera_id, c.location_name, c.latitude, c.longitude,
               COUNT(d.detection_id) AS vehicle_count
        FROM detections d
        JOIN cameras c ON d.camera_id = c.camera_id
        WHERE 1=1
    """
    params = []
    if start_time:
        query += " AND d.timestamp >= ?"
        params.append(start_time)
    if end_time:
        query += " AND d.timestamp <= ?"
        params.append(end_time)

    query += " GROUP BY c.camera_id ORDER BY vehicle_count DESC"

    cur = conn.cursor()
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def get_hourly_traffic_trend(conn, camera_id=None):
    """Vehicle count bucketed by hour — for flow-over-time trend charts."""
    query = """
        SELECT strftime('%Y-%m-%d %H:00', timestamp) AS hour_bucket,
               COUNT(*) AS vehicle_count
        FROM detections
        WHERE 1=1
    """
    params = []
    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)

    query += " GROUP BY hour_bucket ORDER BY hour_bucket ASC"

    cur = conn.cursor()
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def get_origin_destination_pairs(conn, plate_number=None):
    """
    Approximates origin-destination flow by looking at consecutive
    camera-to-camera hops per vehicle (first camera -> next camera).
    """
    query = """
        SELECT plate_number, camera_id, timestamp
        FROM detections
    """
    params = []
    if plate_number:
        query += " WHERE plate_number = ?"
        params.append(plate_number)
    query += " ORDER BY plate_number, timestamp ASC"

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()

    od_pairs = []
    prev_plate, prev_camera = None, None
    for row in rows:
        if row["plate_number"] == prev_plate and prev_camera is not None:
            od_pairs.append({
                "plate_number": row["plate_number"],
                "origin_camera": prev_camera,
                "destination_camera": row["camera_id"],
                "arrival_time": row["timestamp"]
            })
        prev_plate, prev_camera = row["plate_number"], row["camera_id"]

    return od_pairs


def get_active_blacklist_alerts(conn):
    """Any recent detection of a blacklisted plate — for the alert system."""
    query = """
        SELECT b.plate_number, b.reason, b.flagged_on,
               d.timestamp AS last_detected, c.location_name
        FROM blacklist b
        JOIN detections d ON b.plate_number = d.plate_number
        JOIN cameras c ON d.camera_id = c.camera_id
        WHERE b.status = 'active'
        ORDER BY d.timestamp DESC
    """
    cur = conn.cursor()
    cur.execute(query)
    return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------
# 5. DEMO / SAMPLE USAGE
# ---------------------------------------------------------------------

if __name__ == "__main__":
    conn = get_connection()
    create_schema(conn)

    # --- Sample cameras ---
    add_camera(conn, "CAM001", "MG Road Junction", 13.0068, 80.2496, "MG Road", "North", "Sector 1")
    add_camera(conn, "CAM002", "Anna Salai Signal", 13.0524, 80.2508, "Anna Salai", "South", "Sector 2")
    add_camera(conn, "CAM003", "OMR Toll Gate", 12.8996, 80.2274, "OMR", "East", "Sector 3")

    # --- Sample detections (would normally come from your friend's OCR pipeline) ---
    add_detection(conn, "TN01AB1234", "TN01AB1234", "CAM001",
                  "2026-09-14 08:15:00", 0.96, "clear")
    add_detection(conn, "TN01AB1234", "TN01AB1234", "CAM002",
                  "2026-09-14 08:32:00", 0.89, "angled")
    add_detection(conn, "TN01AB1234", "TN0lAB1234", "CAM003",   # noisy OCR read example
                  "2026-09-14 08:50:00", 0.71, "blurred")
    add_detection(conn, "TN22CD5678", "TN22CD5678", "CAM001",
                  "2026-09-14 08:20:00", 0.94, "clear")

    add_to_blacklist(conn, "TN01AB1234", "Reported stolen")

    # --- Sample queries ---
    print("\n--- Trajectory for TN01AB1234 ---")
    for stop in get_plate_trajectory(conn, "TN01AB1234"):
        print(stop)

    print("\n--- Traffic density by camera ---")
    for row in get_traffic_density_by_camera(conn):
        print(row)

    print("\n--- Hourly traffic trend ---")
    for row in get_hourly_traffic_trend(conn):
        print(row)

    print("\n--- Active blacklist alerts ---")
    for row in get_active_blacklist_alerts(conn):
        print(row)

    # --- Plate Query Engine demo ---
    engine = PlateQueryEngine(conn)
    engine.print_report("TN01AB1234")
    engine.print_report("TN99ZZ0000")  # non-existent plate, to show the "not found" case

    conn.close()