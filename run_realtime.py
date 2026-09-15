"""
VECTRA ANPR - realtime entry point
===================================
Runs every camera's video ONCE, in parallel, but stores each plate to
the DB the instant it crosses the frequency threshold - while the
video is still playing, not batched up and written only at the end.

    python run_realtime.py
    python run_realtime.py --frame-skip 2
    python run_realtime.py --cameras CAM-01 CAM-03
    python run_realtime.py --threshold 8

Goes to: vectra/run_realtime.py  (project root, next to run_anpr.py)
"""

import argparse

from database.anpr_system import ANPRSystem


# camera_id -> (location_name, road_name, video_path)
CAMERAS = {
    "CAM-01": ("Main Road Junction", "Road 1", "data/videos/cam1.mp4"),
    "CAM-02": ("Market Street",      "Road 2", "data/videos/cam2.mp4"),
    "CAM-03": ("Civic Center",       "Road 3", "data/videos/cam3.mp4"),
    "CAM-04": ("Ring Road Signal",   "Road 4", "data/videos/cam4.mp4"),
    "CAM-05": ("Bypass Toll",        "Road 5", "data/videos/cam5.mp4"),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process camera videos once, storing plates the instant they're verified"
    )
    parser.add_argument("--frame-skip", type=int, default=1,
                        help="process every Nth frame; 2 or 3 roughly halves runtime")
    parser.add_argument("--cameras", nargs="*", default=None,
                        help="only run these camera ids (default: all)")
    parser.add_argument("--db", default="anpr_system.db")
    parser.add_argument("--model", default="ai/models/best.pt")
    parser.add_argument("--threshold", type=int, default=5,
                        help="how many times a plate must be read before it's stored")
    return parser.parse_args()


def main():
    args = parse_args()

    selected = args.cameras or list(CAMERAS)
    unknown = [c for c in selected if c not in CAMERAS]
    if unknown:
        raise SystemExit(f"Unknown camera id(s): {', '.join(unknown)}")

    system = ANPRSystem(
        db_name=args.db,
        model_path=args.model,
        frequency_threshold=args.threshold,
    )

    # Register first - detections.camera_id is a foreign key.
    for camera_id in selected:
        location_name, road_name, _ = CAMERAS[camera_id]
        system.register_camera(camera_id, location_name, road_name)

    jobs = {cid: CAMERAS[cid][2] for cid in selected}

    # Blocks until every video finishes. system.start()/stop() handled inside.
    system.run_realtime(jobs, frame_skip=args.frame_skip)


if __name__ == "__main__":
    main()