"""
VECTRA ANPR - live simulation entry point
==========================================
Loops the camera videos forever so they act like a real live feed.
Verified plates stream into anpr_system.db as they're detected.
Press Ctrl+C to stop.

    python run_live.py
    python run_live.py --frame-skip 2
    python run_live.py --cameras CAM-01 CAM-03

Goes to: vectra/run_live.py  (project root, next to run_anpr.py)
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
    parser = argparse.ArgumentParser(description="Simulate a live ANPR feed by looping camera videos")
    parser.add_argument("--frame-skip", type=int, default=2,
                        help="process every Nth frame; keeps live mode light on CPU")
    parser.add_argument("--cameras", nargs="*", default=None,
                        help="only run these camera ids (default: all)")
    parser.add_argument("--db", default="anpr_system.db")
    parser.add_argument("--model", default="ai/models/best.pt")
    parser.add_argument("--threshold", type=int, default=5,
                        help="how many times a plate must be read before it counts")
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

    # Blocks here until Ctrl+C. system.start()/stop() are handled inside.
    system.run_live(jobs, frame_skip=args.frame_skip)


if __name__ == "__main__":
    main()