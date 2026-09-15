"""
VECTRA ANPR - parallel entry point
==================================
Processes several camera videos at the same time and stores everything
in anpr_system.db.

    python run_anpr_parallel.py
    python run_anpr_parallel.py --workers 3 --frame-skip 2
    python run_anpr_parallel.py --cameras CAM-01 CAM-03
    python run_anpr_parallel.py --mode process --workers 2

The `if __name__ == "__main__":` guard is REQUIRED. With
--mode process macOS spawns fresh interpreters that re-import this
file, and without the guard they respawn forever.

Goes to: vectra/run_anpr_parallel.py  (project root, next to run_anpr.py)
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
    parser = argparse.ArgumentParser(description="Run ANPR on several cameras at once")
    parser.add_argument("--workers", type=int, default=2,
                        help="how many videos run at the same time (2-3 is the sweet spot)")
    parser.add_argument("--mode", choices=["thread", "process"], default="thread",
                        help="thread = shared memory, process = separate interpreters")
    parser.add_argument("--frame-skip", type=int, default=1,
                        help="process every Nth frame; 2 or 3 roughly halves the runtime")
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

    try:
        # Register first - detections.camera_id is a foreign key.
        for camera_id in selected:
            location_name, road_name, _ = CAMERAS[camera_id]
            system.register_camera(camera_id, location_name, road_name)

        # Background 10-minute density buckets.
        system.start()

        jobs = {cid: CAMERAS[cid][2] for cid in selected}

        results = system.process_all_cameras_parallel(
            jobs,
            workers=args.workers,
            mode=args.mode,
            frame_skip=args.frame_skip,
        )

        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")

        total = 0
        for camera_id in selected:
            vector = results.get(camera_id, [])
            total += len(vector)
            plates = ", ".join(p for p, _, _ in vector) or "-"
            print(f"{camera_id}: {len(vector):>2} plate(s) | {plates}")

        print(f"\nTotal verified plates stored: {total}")

    finally:
        # stop() flushes the density bucket and closes the DB, so run
        # any queries BEFORE this line.
        system.stop()


if __name__ == "__main__":
    main()