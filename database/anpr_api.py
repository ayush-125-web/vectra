"""
ANPR API Server
===============
Connects the existing ANPR system to the dashboard — REST for the
initial load, WebSocket (Socket.IO) for live updates after that.

Flow:
    Dashboard (React)
          |  REST  (GET /api/dashboard)      -> first paint
          |  WS    (event: "dashboard_update") -> keeps updating
          v
      this Flask/Socket.IO API
          v
      ANPRSystem
      /        \
  queries      density
      v            v
        SQLite DB

Still does not modify (per the original design):
    plateDetection.py
    anpr_db.py
    anpr_query.py
    den_monitor.py
    ANPR design.html

All new "dashboard aggregation" SQL lives HERE, in the API file only —
anpr_query.py stays a per-plate query engine, untouched.

New deps for this file specifically:
    pip install flask-socketio
"""

from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from database.anpr_system import ANPRSystem


BASE_DIR = Path(__file__).resolve().parent.parent
HTML_FILE = BASE_DIR / "anpr_design_connected.html"

# A camera counts as "active" if it has logged a detection in the last
# N minutes. Tune this to however chatty your camera feeds actually are.
ACTIVE_WINDOW_MINUTES = 5

# How often the background thread pushes a fresh dashboard snapshot to
# every connected browser.
DASHBOARD_PUSH_INTERVAL_SECONDS = 4

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5001"
            ]
        }
    }
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
)

# One coordinator for the complete ANPR system.
system = ANPRSystem(
    db_name="anpr_system.db",
    model_path="ai/models/best.pt",
    frequency_threshold=5,
)


# -------------------------------------------------------------------
# FRONTEND
# -------------------------------------------------------------------

@app.route("/")
def home():
    """Open the existing dashboard HTML."""
    return send_from_directory(BASE_DIR, "anpr_design_connected.html")


# -------------------------------------------------------------------
# DASHBOARD AGGREGATION (all new SQL lives here, not in anpr_query.py)
# -------------------------------------------------------------------

def _camera_status():
    """Every registered camera, with an `active` flag based on recent detections."""
    cur = system.db.conn.cursor()
    cur.execute("SELECT camera_id, location_name, road_name FROM cameras ORDER BY camera_id")
    cameras = [dict(row) for row in cur.fetchall()]

    cutoff = (datetime.now() - timedelta(minutes=ACTIVE_WINDOW_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT DISTINCT camera_id FROM detections WHERE timestamp >= ?", (cutoff,))
    active_ids = {row["camera_id"] for row in cur.fetchall()}

    for cam in cameras:
        cam["active"] = cam["camera_id"] in active_ids
    return cameras


def _vehicles_today():
    """Distinct plates seen since local midnight."""
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    cur = system.db.conn.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT plate_number) AS c FROM detections WHERE timestamp >= ?",
        (today_start,),
    )
    return cur.fetchone()["c"]


def _recent_detections(limit=6):
    cur = system.db.conn.cursor()
    cur.execute("""
        SELECT d.plate_number, d.timestamp, d.confidence_score,
               c.camera_id, c.location_name
        FROM detections d
        JOIN cameras c ON d.camera_id = c.camera_id
        ORDER BY d.timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    for r in rows:
        # "2026-09-15 10:27:45" -> "10:27:45", matches what the UI showed before
        r["time"] = r["timestamp"].split(" ")[-1]
    return rows


def _density_by_node():
    """
    Live traffic density per camera.

    Density = number of unique vehicles detected by that camera
              during the last 60 seconds.

    This reads directly from the detections table, so it also works
    when ANPR processing is running in another Python process.
    """

    cutoff = (
        datetime.now() - timedelta(seconds=60)
    ).strftime("%Y-%m-%d %H:%M:%S")

    cur = system.db.conn.cursor()

    # Count unique plates detected by each camera
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
        (cutoff,)
    )

    density_counts = {
        row["camera_id"]: row["vehicle_count"]
        for row in cur.fetchall()
    }

    # Get all registered cameras so cameras with no
    # detections still appear as 0/min.
    cur.execute(
        "SELECT camera_id FROM cameras ORDER BY camera_id"
    )

    all_camera_ids = [
        row["camera_id"]
        for row in cur.fetchall()
    ]

    return [
        {
            "camera": camera_id,
            "density": density_counts.get(camera_id, 0)
        }
        for camera_id in all_camera_ids
    ]


def _hourly_traffic():
    """
    Traffic volume for the last 12 hours.

    Counts unique vehicles detected in each hour
    from the detections table.
    """

    now = datetime.now()

    # Start of current hour
    current_hour = now.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    # Last 12 hours including current hour
    start_hour = current_hour - timedelta(hours=11)

    cur = system.db.conn.cursor()

    cur.execute(
        """
        SELECT
            strftime('%Y-%m-%d %H:00:00', timestamp) AS hour_bucket,
            COUNT(DISTINCT plate_number) AS vehicle_count
        FROM detections
        WHERE timestamp >= ?
        GROUP BY hour_bucket
        ORDER BY hour_bucket
        """,
        (start_hour.strftime("%Y-%m-%d %H:%M:%S"),)
    )

    rows = cur.fetchall()

    # Convert DB result into a dictionary
    db_data = {
        row["hour_bucket"]: row["vehicle_count"]
        for row in rows
    }

    result = []

    # Always return all 12 hours,
    # even if some hours have zero detections.
    for i in range(12):
        hour = start_hour + timedelta(hours=i)

        key = hour.strftime("%Y-%m-%d %H:00:00")

        result.append({
            "hour": hour.strftime("%H:%M"),
            "vehicles": db_data.get(key, 0)
        })

    return result


def _build_dashboard_payload():
    cameras = _camera_status()

    return {
        "active_cameras": sum(1 for c in cameras if c["active"]),
        "total_cameras": len(cameras),
        "cameras": cameras,

        "vehicles_today": _vehicles_today(),

        "recent_detections": _recent_detections(6),

        # Live density from last 60 seconds
        "density_by_node": _density_by_node(),

        # Real hourly traffic from database
        "hourly_traffic": _hourly_traffic(),

        # Speed is not implemented yet
        "avg_speed": None,
    }


# -------------------------------------------------------------------
# DASHBOARD / QUERY APIs (REST - used for first paint, before the
# socket connects)
# -------------------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    return jsonify(_build_dashboard_payload())


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "message": "ANPR API is running"
    })


@app.route("/api/vehicle/<plate_number>")
def vehicle(plate_number):
    """Return the complete report for one vehicle."""
    result = system.get_vehicle(plate_number)

    if result is None:
        return jsonify({
            "found": False,
            "plate_number": plate_number
        }), 404

    return jsonify({
        "found": True,
        "data": result
    })


@app.route("/api/trajectory/<plate_number>")
def trajectory(plate_number):
    """Return a vehicle's camera trajectory."""
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = system.get_trajectory(
        plate_number,
        start_time,
        end_time
    )

    return jsonify({
        "plate_number": plate_number,
        "trajectory": result
    })


@app.route("/api/last-location/<plate_number>")
def last_location(plate_number):
    """Return the last known camera/location of a vehicle."""
    result = system.get_last_location(plate_number)

    if result is None:
        return jsonify({
            "found": False,
            "plate_number": plate_number
        }), 404

    return jsonify({
        "found": True,
        "data": result
    })


@app.route("/api/density")
def density():
    """Return the flushed (10-min bucket) traffic-density records."""
    camera_id = request.args.get("camera_id")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    result = system.get_density(
        camera_id,
        start_time,
        end_time
    )

    return jsonify({
        "density": result
    })


# -------------------------------------------------------------------
# CAMERA PROCESSING
# -------------------------------------------------------------------

@app.route("/api/process-camera", methods=["POST"])
def process_camera():
    """
    Process one camera video.

    JSON body:
    {
        "camera_id": "CAM-01",
        "video_path": "videos/cam1.mp4"
    }
    """
    data = request.get_json(silent=True) or {}

    camera_id = data.get("camera_id")
    video_path = data.get("video_path")

    if not camera_id or not video_path:
        return jsonify({
            "error": "camera_id and video_path are required"
        }), 400

    try:
        result = system.process_camera(
            camera_id=camera_id,
            video_path=video_path
        )

        # Push a fresh snapshot immediately instead of waiting for the
        # next poll tick, so a manual/API-triggered run shows up right away.
        socketio.emit("dashboard_update", _build_dashboard_payload())

        return jsonify({
            "success": True,
            "camera_id": camera_id,
            "detections": result
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


# -------------------------------------------------------------------
# WEBSOCKET (Socket.IO)
# -------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    # Give the newly-connected client an immediate snapshot instead of
    # making it wait for the next broadcast tick.
    emit("dashboard_update", _build_dashboard_payload())


def _dashboard_broadcaster():
    """Background task: pushes a fresh dashboard snapshot to every
    connected client every DASHBOARD_PUSH_INTERVAL_SECONDS."""
    while True:
        socketio.sleep(DASHBOARD_PUSH_INTERVAL_SECONDS)
        try:
            socketio.emit("dashboard_update", _build_dashboard_payload())
        except Exception as exc:
            print(f"[dashboard_broadcaster] {type(exc).__name__}: {exc}")


# -------------------------------------------------------------------
# START SERVER
# -------------------------------------------------------------------

if __name__ == "__main__":
    # Start traffic-density monitoring.
    system.start()
    socketio.start_background_task(_dashboard_broadcaster)

    try:
        print("ANPR API running at http://127.0.0.1:5001")
        socketio.run(app, host="0.0.0.0", port=5001, debug=False)
    finally:
        system.stop()