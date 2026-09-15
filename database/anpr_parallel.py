"""
VECTRA ANPR - Parallel camera processing
========================================
Runs several camera videos at the same time and feeds every result back
into the existing ANPRSystem / ANPRDatabase.

The rule that keeps this simple and crash-free:

    detection  -> happens in workers (threads or processes)
    DB writes  -> happen ONLY in the main thread, as results come back

So SQLite is never touched by two workers at once, and there is no
cross-process database plumbing to get wrong.

MODES
-----
mode="thread"  (default)
    Each thread builds its own PlateDetector. YOLO and Paddle release
    the GIL during inference, so you do get real overlap. Cheapest to
    set up, easiest to debug, best choice on a Mac or a single GPU.

mode="process"
    Each worker process builds its own PlateDetector. True CPU
    parallelism, but every process loads the models again (roughly
    1-2 GB each), so keep `workers` small. On macOS the start method is
    "spawn", so the script you launch MUST be guarded with
    `if __name__ == "__main__":` or you get infinite respawning.

Goes to: database/anpr_parallel.py
"""

import os
import threading
import time
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)


# ---------------------------------------------------------------------
# THREAD MODE - one detector per thread
# ---------------------------------------------------------------------

_thread_state = threading.local()


def _get_thread_detector(model_path, frequency_threshold):
    """Build (once) and reuse a PlateDetector that belongs to this thread."""
    detector = getattr(_thread_state, "detector", None)

    if detector is None:
        from ai.detection.plateDetection import PlateDetector

        detector = PlateDetector(
            model_path=model_path,
            frequency_threshold=frequency_threshold,
            show=False,
        )
        _thread_state.detector = detector

    return detector


def _thread_job(camera_id, video_path, model_path, frequency_threshold, frame_skip):
    detector = _get_thread_detector(model_path, frequency_threshold)

    started = time.time()
    vector = detector.process_video(
        video_path,
        show=False,
        frame_skip=frame_skip,
        tag=camera_id,
        verbose=False,
    )
    return camera_id, vector, time.time() - started


# ---------------------------------------------------------------------
# PROCESS MODE - one detector per worker process
# ---------------------------------------------------------------------

_process_state = {}


def _process_init(model_path, frequency_threshold, threads_per_worker):
    """
    Runs once per worker process, before any job.

    The env vars have to be set before torch/paddle get imported,
    otherwise every worker grabs all the cores and they fight each
    other - which is why PlateDetector is imported inside this function
    and not at the top of the file.
    """
    os.environ["OMP_NUM_THREADS"] = str(threads_per_worker)
    os.environ["MKL_NUM_THREADS"] = str(threads_per_worker)

    from ai.detection.plateDetection import PlateDetector

    try:
        import torch

        torch.set_num_threads(threads_per_worker)
    except Exception:
        pass

    _process_state["detector"] = PlateDetector(
        model_path=model_path,
        frequency_threshold=frequency_threshold,
        show=False,
    )


def _process_job(camera_id, video_path, frame_skip):
    detector = _process_state["detector"]

    started = time.time()
    vector = detector.process_video(
        video_path,
        show=False,
        frame_skip=frame_skip,
        tag=camera_id,
        verbose=False,
    )
    return camera_id, vector, time.time() - started


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------

def run_cameras_parallel(
    system,
    cameras,
    workers=2,
    mode="thread",
    frame_skip=1,
    threads_per_worker=1,
):
    """
    cameras: {"CAM-01": "data/videos/cam1.mp4", "CAM-02": ...}

    Returns {camera_id: final_vector}. Every vector is written to the
    DB by this (main) thread as soon as its camera finishes, so a slow
    camera never blocks the fast ones from being stored.
    """
    if not cameras:
        return {}

    workers = max(1, min(int(workers), len(cameras)))
    results = {}
    started = time.time()

    print(f"\n{'=' * 60}")
    print(
        f"PARALLEL RUN | cameras={len(cameras)} | "
        f"workers={workers} | mode={mode} | frame_skip={frame_skip}"
    )
    print(f"{'=' * 60}")

    if mode == "process":
        executor = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_process_init,
            initargs=(
                system.model_path,
                system.frequency_threshold,
                threads_per_worker,
            ),
        )
    elif mode == "thread":
        executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="anpr"
        )
    else:
        raise ValueError("mode must be 'thread' or 'process'")

    with executor:
        futures = {}

        for camera_id, video_path in cameras.items():
            if mode == "process":
                future = executor.submit(
                    _process_job, camera_id, video_path, frame_skip
                )
            else:
                future = executor.submit(
                    _thread_job,
                    camera_id,
                    video_path,
                    system.model_path,
                    system.frequency_threshold,
                    frame_skip,
                )

            futures[future] = camera_id

        for future in as_completed(futures):
            camera_id = futures[future]

            try:
                camera_id, vector, elapsed = future.result()
            except Exception as exc:
                # One bad video must not kill the whole run.
                print(f"[{camera_id}] FAILED: {type(exc).__name__}: {exc}")
                results[camera_id] = []
                continue

            print(
                f"[{camera_id}] finished in {elapsed:.1f}s | "
                f"{len(vector)} verified plate(s)"
            )

            # Main thread only - this is the single DB writer.
            system.store_vector(camera_id, vector)
            results[camera_id] = vector

    print(f"\nAll cameras done in {time.time() - started:.1f}s")
    return results