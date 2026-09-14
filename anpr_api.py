"""
ANPR API Server
===============
New file only: connects the existing ANPR system to the HTML dashboard.

Flow:
    HTML dashboard
          ↓ HTTP
      this Flask API
          ↓
      ANPRSystem
      ↙       ↘
  queries    density
      ↓         ↓
        SQLite DB

This file does not modify:
    plateDetection.py
    anpr_db.py
    anpr_query.py
    den_monitor.py
    ANPR design.html
"""

from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from anpr_system import ANPRSystem


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "ANPR design.html"

app = Flask(__name__)

# One coordinator for the complete ANPR system.
system = ANPRSystem(
    db_name="anpr_system.db",
    model_path="models/best.pt",
    frequency_threshold=5,
)

# -------------------------------------------------------------------
# FRONTEND
# -------------------------------------------------------------------

@app.route("/")
def home():
    """Open the existing dashboard HTML."""
    return send_from_directory(BASE_DIR, "ANPR design.html")


# -------------------------------------------------------------------
# DASHBOARD / QUERY APIs
# -------------------------------------------------------------------

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
    """Return traffic-density records."""
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
# START SERVER
# -------------------------------------------------------------------

if __name__ == "__main__":
    # Start traffic-density monitoring.
    system.start()

    try:
        print("ANPR API running at http://127.0.0.1:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        system.stop()
