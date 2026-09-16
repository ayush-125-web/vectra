"""
VECTRA ANPR - Realtime + live simulation
=========================================
Two modes, one shared engine underneath:

    run_realtime(system, cameras, frame_skip)
        Each video plays through ONCE. A plate is written to the DB the
        INSTANT it crosses frequency_threshold - not batched up and
        written only after the whole video finishes. Returns when every
        camera's video has ended.

    run_live(system, cameras, frame_skip)
        Same real-time storage, but every video LOOPS forever, so it
        behaves like a permanent camera feed. Runs until Ctrl+C.

Both share the same rule as the parallel runner: detection happens in
background threads (one PlateDetector per thread - YOLO/PaddleOCR
aren't thread-safe, never share one). Each worker fires a callback the
instant it verifies a plate; the callback just drops the result on a
queue. The MAIN thread drains that queue and does the actual DB insert,
so SQLite only ever sees one writer no matter how many cameras run.

Goes to: database/anpr_live.py
"""

import queue
import signal
import threading


def _camera_worker(
    camera_id,
    video_path,
    model_path,
    frequency_threshold,
    frame_skip,
    loop,
    result_queue,
    stop_event,
    done_event,
):
    """Runs in its own thread. Builds its OWN PlateDetector - never share
    one across threads, YOLO/PaddleOCR aren't thread-safe."""
    from ai.detection.plateDetection import PlateDetector

    def on_verified(tag, plate, frequency, avg_confidence):
        # Cheap and thread-safe - just hands the result to the main
        # thread. No DB access happens here, on purpose.
        result_queue.put((tag or camera_id, plate, frequency, avg_confidence))

    detector = PlateDetector(
        model_path=model_path,
        frequency_threshold=frequency_threshold,
        show=False,
        on_verified=on_verified,
    )

    try:
        detector.process_video(
            video_path,
            show=False,
            frame_skip=frame_skip,
            tag=camera_id,
            verbose=False,
            loop=loop,
            stop_event=stop_event,
        )
    except Exception as exc:
        print(f"[{camera_id}] WORKER FAILED: {type(exc).__name__}: {exc}")
    finally:
        # Lets the main loop know THIS camera is done, independent of
        # the others - important in non-loop mode where videos finish
        # at different times.
        done_event.set()


def _run(system, cameras, frame_skip, loop, mode_label):
    """Shared engine for both run_realtime() and run_live()."""
    if not cameras:
        print("No cameras given.")
        return {}

    stop_event = threading.Event()
    result_queue = queue.Queue()
    done_events = {camera_id: threading.Event() for camera_id in cameras}
    counts = {camera_id: 0 for camera_id in cameras}

    def handle_sigint(signum, frame):
        if not stop_event.is_set():
            print("\nStopping... (finishing in-flight frames)")
            stop_event.set()

    previous_handler = signal.signal(signal.SIGINT, handle_sigint)

    threads = [
        threading.Thread(
            target=_camera_worker,
            args=(
                camera_id,
                video_path,
                system.model_path,
                system.frequency_threshold,
                frame_skip,
                loop,
                result_queue,
                stop_event,
                done_events[camera_id],
            ),
            daemon=True,
            name=f"anpr-{camera_id}",
        )
        for camera_id, video_path in cameras.items()
    ]

    system.start()  # background 10-minute density monitor

    for t in threads:
        t.start()

    print(f"\n{'=' * 60}")
    stop_hint = "Ctrl+C to stop" if loop else "stops automatically when videos end"
    print(f"{mode_label} | {len(threads)} camera(s) | {stop_hint}")
    print(f"{'=' * 60}\n")

    total_hits = 0

    try:
        while True:
            try:
                camera_id, plate, frequency, avg_confidence = result_queue.get(
                    timeout=0.5
                )
                # Only NOW - the instant the threshold was crossed - does
                # this plate reach the database. Main thread only.
                system.store_single_detection(camera_id, plate, avg_confidence)
                total_hits += 1
                counts[camera_id] += 1

                print(
                    f"[{camera_id}] STORED #{total_hits}: {plate} "
                    f"| freq={frequency} | conf={avg_confidence:.2f}"
                )
            except queue.Empty:
                pass

            all_done = all(ev.is_set() for ev in done_events.values())

            if all_done and result_queue.empty():
                # Non-loop mode: every video reached its end naturally.
                break

            if stop_event.is_set() and all(not t.is_alive() for t in threads) and result_queue.empty():
                # Loop mode: Ctrl+C was pressed and everyone has exited.
                break

    finally:
        stop_event.set()

        for t in threads:
            t.join(timeout=5)

        system.stop()
        signal.signal(signal.SIGINT, previous_handler)

        print(f"\n{'=' * 60}")
        print(f"{mode_label} STOPPED | {total_hits} total detection(s) stored")
        for camera_id, count in counts.items():
            print(f"  {camera_id}: {count}")
        print(f"{'=' * 60}")

    return counts


def run_realtime(system, cameras, frame_skip=1):
    """
    Each video plays through ONCE. Plates are written to the DB the
    instant they cross frequency_threshold, while the video is still
    playing - not batched and written only at the end.

    cameras: {"CAM-01": "data/videos/cam1.mp4", ...}
    Returns {camera_id: number_of_plates_stored}.
    """
    return _run(system, cameras, frame_skip, loop=False, mode_label="REALTIME MODE")


def run_live(system, cameras, frame_skip=2):
    """
    Same real-time storage as run_realtime(), but every video loops
    forever - acts like a permanent live feed. Blocks until Ctrl+C.

    cameras: {"CAM-01": "data/videos/cam1.mp4", ...}
    """
    return _run(system, cameras, frame_skip, loop=True, mode_label="LIVE MODE")