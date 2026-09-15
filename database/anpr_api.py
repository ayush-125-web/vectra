"""
ANPR API Server
===============
Connects the existing ANPR system to the dashboard — REST for the
initial load, WebSocket (Socket.IO) for live updates after that.

Flow:

    Dashboard (React)
          |  REST  (GET /api/dashboard)       -> first paint
          |  WS    (event: "dashboard_update") -> live updates
          v
    Flask / Socket.IO API
          v
      ANPRSystem
          v
       SQLite DB
"""

from datetime import datetime, timedelta
import sqlite3

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from database.anpr_system import ANPRSystem


# ============================================================
# CONFIG
# ============================================================

# Camera is considered active if it has a detection
# within the last N minutes.
ACTIVE_WINDOW_MINUTES = 5

# How often dashboard data is pushed to connected React clients.
DASHBOARD_PUSH_INTERVAL_SECONDS = 4


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5001",
            ]
        }
    }
)


# ============================================================
# SOCKET.IO
# ============================================================

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
)


# ============================================================
# ANPR SYSTEM
# ============================================================

system = ANPRSystem(
    db_name="anpr_system.db",
    model_path="ai/models/best.pt",
    frequency_threshold=5,
)


# ============================================================
# DASHBOARD DATABASE CONNECTION
# ============================================================

def get_dashboard_db():
    """
    Create a separate SQLite connection for dashboard reads.

    IMPORTANT:
    Do NOT use system.db.conn here.

    The ANPR system and its background density monitor may use
    system.db.conn from another thread/process. Using a separate
    connection makes dashboard reads much safer.
    """

    conn = sqlite3.connect(
        system.db.db_name,
        timeout=5,
    )

    conn.row_factory = sqlite3.Row

    # Wait if another process/thread is temporarily writing.
    conn.execute("PRAGMA busy_timeout = 5000")

    # Safe concurrent read/write mode.
    conn.execute("PRAGMA journal_mode = WAL")

    return conn


# ============================================================
# DASHBOARD AGGREGATION
# ============================================================

def _camera_status():
    """
    Return every registered camera with its active status.

    A camera is active if it has at least one detection
    in the last ACTIVE_WINDOW_MINUTES.
    """

    conn = get_dashboard_db()

    try:
        cur = conn.cursor()

        # Get all registered cameras.
        cur.execute(
            """
            SELECT
                camera_id,
                location_name,
                road_name
            FROM cameras
            ORDER BY camera_id
            """
        )

        cameras = [dict(row) for row in cur.fetchall()]

        # Calculate active camera cutoff.
        cutoff = (
            datetime.now()
            - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
        ).strftime("%Y-%m-%d %H:%M:%S")

        # Find cameras with recent detections.
        cur.execute(
            """
            SELECT DISTINCT camera_id
            FROM detections
            WHERE timestamp >= ?
            """,
            (cutoff,),
        )

        active_ids = {
            row["camera_id"]
            for row in cur.fetchall()
        }

        # Add active=True/False.
        for cam in cameras:
            cam["active"] = cam["camera_id"] in active_ids

        return cameras

    finally:
        conn.close()


def _vehicles_today():
    """
    Count distinct vehicles detected since midnight.
    """

    conn = get_dashboard_db()

    try:
        today_start = datetime.now().strftime(
            "%Y-%m-%d 00:00:00"
        )

        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(DISTINCT plate_number) AS c
            FROM detections
            WHERE timestamp >= ?
            """,
            (today_start,),
        )

        return cur.fetchone()["c"]

    finally:
        conn.close()


def _recent_detections(limit=6):
    """
    Return the latest detections for the dashboard.
    """

    conn = get_dashboard_db()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                d.plate_number,
                d.timestamp,
                d.confidence_score,
                c.camera_id,
                c.location_name
            FROM detections d
            JOIN cameras c
                ON d.camera_id = c.camera_id
            ORDER BY d.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        rows = [dict(row) for row in cur.fetchall()]

        # Convert:
        # 2026-09-15 10:27:45
        #
        # into:
        # 10:27:45

        for row in rows:
            row["time"] = row["timestamp"].split(" ")[-1]

        return rows

    finally:
        conn.close()


def _density_by_node():
    """
    LIVE traffic density per camera.

    Density = number of UNIQUE vehicles detected
              by that camera during the LAST 60 SECONDS.

    Therefore:

        density = vehicles / minute

    Example:

        CAM-01 -> 8
        CAM-02 -> 3
        CAM-03 -> 0

    This reads directly from SQLite, so it also works if the
    ANPR processing is running in another Python process.
    """

    conn = get_dashboard_db()

    try:
        # Last 60 seconds.
        cutoff = (
            datetime.now()
            - timedelta(seconds=60)
        ).strftime("%Y-%m-%d %H:%M:%S")

        cur = conn.cursor()

        # Count unique plates for every camera
        # during the last 60 seconds.
        cur.execute(
            """
            SELECT
                camera_id,
                COUNT(DISTINCT plate_number) AS vehicle_count
            FROM detections
            WHERE timestamp >= ?
            GROUP BY camera_id
            """,
            (cutoff,),
        )

        density_counts = {
            row["camera_id"]: row["vehicle_count"]
            for row in cur.fetchall()
        }

        # Get every registered camera.
        cur.execute(
            """
            SELECT camera_id
            FROM cameras
            ORDER BY camera_id
            """
        )

        all_camera_ids = [
            row["camera_id"]
            for row in cur.fetchall()
        ]

        # Cameras without detections get 0.
        return [
            {
                "camera": camera_id,
                "density": density_counts.get(camera_id, 0),
            }
            for camera_id in all_camera_ids
        ]

    finally:
        conn.close()


def _hourly_traffic():
    """
    Traffic volume for the last 12 hours.

    Counts unique vehicles detected in every hour.
    """

    conn = get_dashboard_db()

    try:
        now = datetime.now()

        # Start of current hour.
        current_hour = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        # Last 12 hours including current hour.
        start_hour = current_hour - timedelta(hours=11)

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                strftime(
                    '%Y-%m-%d %H:00:00',
                    timestamp
                ) AS hour_bucket,

                COUNT(DISTINCT plate_number)
                    AS vehicle_count

            FROM detections

            WHERE timestamp >= ?

            GROUP BY hour_bucket

            ORDER BY hour_bucket
            """,
            (
                start_hour.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        )

        rows = cur.fetchall()

        db_data = {
            row["hour_bucket"]: row["vehicle_count"]
            for row in rows
        }

        result = []

        # Always return all 12 hours.
        for i in range(12):

            hour = start_hour + timedelta(hours=i)

            key = hour.strftime(
                "%Y-%m-%d %H:00:00"
            )

            result.append(
                {
                    "hour": hour.strftime("%H:%M"),
                    "vehicles": db_data.get(key, 0),
                }
            )

        return result

    finally:
        conn.close()


# ============================================================
# COMPLETE DASHBOARD PAYLOAD
# ============================================================

def _build_dashboard_payload():

    cameras = _camera_status()

    return {
        "active_cameras": sum(
            1 for camera in cameras
            if camera["active"]
        ),

        "total_cameras": len(cameras),

        "cameras": cameras,

        "vehicles_today": _vehicles_today(),

        "recent_detections": _recent_detections(6),

        # LIVE density:
        # unique vehicles in last 60 seconds.
        "density_by_node": _density_by_node(),

        # Last 12 hours.
        "hourly_traffic": _hourly_traffic(),

        # Speed is not implemented yet.
        "avg_speed": None,
    }


# ============================================================
# DASHBOARD API
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def dashboard():

    return jsonify(
        _build_dashboard_payload()
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health")
def health():

    return jsonify(
        {
            "status": "ok",
            "message": "ANPR API is running",
        }
    )


# ============================================================
# VEHICLE API
# ============================================================

@app.route("/api/vehicle/<plate_number>")
def vehicle(plate_number):

    result = system.get_vehicle(
        plate_number
    )

    if result is None:

        return jsonify(
            {
                "found": False,
                "plate_number": plate_number,
            }
        ), 404

    return jsonify(
        {
            "found": True,
            "data": result,
        }
    )


# ============================================================
# TRAJECTORY API
# ============================================================

@app.route("/api/trajectory/<plate_number>")
def trajectory(plate_number):
    """
    Return complete trajectory of a vehicle.

    Uses a fresh SQLite connection instead of the long-lived
    ANPRSystem query connection.
    """

    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    conn = get_dashboard_db()

    try:
        cur = conn.cursor()

        query = """
            SELECT
                d.timestamp,
                d.confidence_score,
                c.camera_id,
                c.location_name,
                c.road_name
            FROM detections d
            JOIN cameras c
                ON d.camera_id = c.camera_id
            WHERE d.plate_number = ?
        """

        params = [plate_number.strip().upper()]

        if start_time:
            query += " AND d.timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND d.timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY d.timestamp ASC"

        cur.execute(query, params)

        trajectory_data = [
            dict(row)
            for row in cur.fetchall()
        ]

        return jsonify(
            {
                "plate_number": plate_number.strip().upper(),
                "trajectory": trajectory_data,
            }
        )

    except Exception as exc:

        print(
            f"[trajectory] {type(exc).__name__}: {exc}"
        )

        return jsonify(
            {
                "plate_number": plate_number,
                "trajectory": [],
                "error": str(exc),
            }
        ), 500

    finally:
        conn.close()



# ============================================================
# LAST LOCATION API
# ============================================================

@app.route("/api/last-location/<plate_number>")
def last_location(plate_number):

    result = system.get_last_location(
        plate_number
    )

    if result is None:

        return jsonify(
            {
                "found": False,
                "plate_number": plate_number,
            }
        ), 404

    return jsonify(
        {
            "found": True,
            "data": result,
        }
    )


# ============================================================
# HISTORICAL DENSITY API
# ============================================================

@app.route("/api/density")
def density():

    camera_id = request.args.get(
        "camera_id"
    )

    start_time = request.args.get(
        "start_time"
    )

    end_time = request.args.get(
        "end_time"
    )

    result = system.get_density(
        camera_id,
        start_time,
        end_time,
    )

    return jsonify(
        {
            "density": result,
        }
    )


@app.route("/api/blacklist")
def blacklist():
    result = system.get_active_blacklist()

    return jsonify({
        "blacklist": result
    })



# ============================================================
# CAMERA PROCESSING API
# ============================================================

@app.route(
    "/api/process-camera",
    methods=["POST"],
)
def process_camera():

    """
    Process one camera video.

    JSON body:

    {
        "camera_id": "CAM-01",
        "video_path": "videos/cam1.mp4"
    }
    """

    data = request.get_json(
        silent=True
    ) or {}

    camera_id = data.get(
        "camera_id"
    )

    video_path = data.get(
        "video_path"
    )

    if not camera_id or not video_path:

        return jsonify(
            {
                "error":
                    "camera_id and video_path are required"
            }
        ), 400

    try:

        result = system.process_camera(
            camera_id=camera_id,
            video_path=video_path,
        )

        # Immediately update dashboard.
        socketio.emit(
            "dashboard_update",
            _build_dashboard_payload(),
        )

        return jsonify(
            {
                "success": True,
                "camera_id": camera_id,
                "detections": result,
            }
        )

    except Exception as exc:

        return jsonify(
            {
                "success": False,
                "error": str(exc),
            }
        ), 500


# ============================================================
# SOCKET.IO
# ============================================================

@socketio.on("connect")
def handle_connect():

    print("Dashboard Socket.IO client connected")

    # Send current dashboard data immediately.
    emit(
        "dashboard_update",
        _build_dashboard_payload(),
    )


@socketio.on("disconnect")
def handle_disconnect():

    print("Dashboard Socket.IO client disconnected")


# ============================================================
# DASHBOARD BROADCASTER
# ============================================================

def _dashboard_broadcaster():

    """
    Continuously send fresh dashboard data
    to connected React clients.
    """

    while True:

        socketio.sleep(
            DASHBOARD_PUSH_INTERVAL_SECONDS
        )

        try:

            payload = (
                _build_dashboard_payload()
            )

            socketio.emit(
                "dashboard_update",
                payload,
            )

        except Exception as exc:

            print(
                "[dashboard_broadcaster]",
                type(exc).__name__,
                ":",
                exc,
            )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "Starting ANPR system..."
    )

    # Start traffic-density monitoring.
    system.start()

    # Start dashboard broadcaster.
    socketio.start_background_task(
        _dashboard_broadcaster
    )

    try:

        print(
            "ANPR API running at "
            "http://127.0.0.1:5001"
        )

        socketio.run(
            app,
            host="0.0.0.0",
            port=5001,
            debug=False,
        )

    finally:

        system.stop()