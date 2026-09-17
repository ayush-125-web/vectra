# VECTRA — City-Wide ANPR & Traffic Intelligence System

VECTRA is an Automatic Number Plate Recognition (ANPR) pipeline that watches
multiple camera feeds at once, reads license plates with a YOLO + OCR
pipeline, stores verified detections in a SQLite database, and serves that
data to **ATLAS** — a live React dashboard for tracking vehicles, traffic
density, and camera status across a city-wide grid.

```
Camera videos ──▶ YOLO detector ──▶ PaddleOCR ──▶ frequency-verified plate
                                                          │
                                                          ▼
                                                   SQLite database
                                                    (WAL mode)
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                  Query engine     Density monitor   Flask API
                                  (trajectory,      (10-min bucket    (REST, polled
                                  last location,     vehicle counts)   by frontend)
                                  blacklist)                                │
                                                                            ▼
                                                                   ATLAS dashboard
                                                                     (React + Vite)
```

---

## Features

- **Multi-camera detection** — YOLO (Ultralytics) locates plates in each
  frame, PaddleOCR reads the text, and a plate only counts as "verified"
  once it's read the same way a configurable number of times
  (`frequency_threshold`), which filters out one-off OCR misreads.
- **Three ways to run detection**, all backed by the same detector class:
  | Mode | Script | Behaviour |
  |---|---|---|
  | Batch | `run_anpr_parallel.py` | Every camera's video runs once, in parallel; results are written to the DB after each video finishes. |
  | Realtime | `run_realtime.py` | Every camera's video runs once, in parallel; each plate is written to the DB the instant it's verified — while the video is still playing. |
  | Live | `run_live.py` | Every camera's video loops forever, simulating a permanent live feed. Runs until you press `Ctrl+C`. |
- **Thread-safe by design** — each worker (thread or process) builds its
  own `PlateDetector` (YOLO/PaddleOCR aren't thread-safe), while the
  SQLite database is written to from a single thread only, avoiding lock
  contention entirely.
- **City-wide vehicle tracking** — full trajectory per plate (which
  cameras, in what order, when), last known location, and a blacklist
  system for flagging plates of interest.
- **Traffic density monitoring** — a background thread buckets distinct
  vehicles seen per camera into 10-minute windows, deduplicated so a car
  idling at a signal isn't counted multiple times.
- **REST API + live dashboard** — a Flask API exposes vehicle lookups,
  trajectories, density, and dashboard summary data; the ATLAS frontend
  polls it to stay continuously up to date without a manual refresh.

---

## Project structure

```
vectra/
├── ai/
│   ├── detection/
│   │   └── plateDetection.py       # PlateDetector: YOLO + PaddleOCR, one video/camera per instance
│   ├── models/
│   │   └── best.pt                 # trained YOLO weights
│   ├── ocr/
│   ├── tracking/
│   └── pipeline.py
│
├── data/
│   ├── cameras/
│   ├── test/
│   └── videos/                     # sample footage: cam1.mp4 … cam5.mp4
│
├── database/
│   ├── anpr_db.py                  # schema + inserts (WAL mode, single write lock)
│   ├── anpr_query.py               # all read-only lookups (trajectory, dashboard stats, blacklist)
│   ├── den_monitor.py              # background 10-minute traffic-density buckets
│   ├── anpr_system.py              # coordinator: wires detector + DB + density + query layer together
│   ├── anpr_parallel.py            # thread/process pool for batch mode
│   ├── anpr_live.py                # shared engine behind realtime & live modes
│   ├── anpr_controller.py          # single entry point for write/read operations
│   ├── anpr_api.py                 # Flask REST API
│   ├── blacklist.py                # blacklist management
│   └── schema.sql
│
├── frontend/                       # ATLAS dashboard (React + Vite + Tailwind)
│   ├── public/cameras/             # CAM-01.mp4 … CAM-05.mp4 (frontend preview footage)
│   └── src/
│       ├── components/             # CityMap, Sidebar, StatReadout, ...
│       ├── data/                   # mock data (being phased out for live API data)
│       ├── hooks/
│       │   └── useDashboard.js     # polls the API and keeps dashboard state fresh
│       ├── pages/
│       │   ├── CommandCenter.jsx   # live overview: active cameras, vehicles today, density, recent hits
│       │   ├── VehicleTracking.jsx
│       │   ├── LiveCameras.jsx
│       │   ├── Analytics.jsx
│       │   └── Alerts.jsx
│       └── api.js                  # API base URL + fetch helpers
│
├── run_anpr_parallel.py            # entry point: batch mode
├── run_realtime.py                 # entry point: realtime mode
├── run_live.py                     # entry point: live/looping mode
└── anpr_system.db                  # SQLite database (created on first run)
```

---

## How detection works

1. `PlateDetector` reads a video frame by frame, runs YOLO to find plate
   bounding boxes, crops each one, and runs PaddleOCR on the crop.
2. OCR text is cleaned (uppercased, non-alphanumeric stripped) and rejected
   unless it's exactly 7 characters — a basic sanity filter for Indian
   plate formats.
3. Every time a plate is read, its frequency and running average
   confidence are updated. Once frequency crosses `frequency_threshold`
   (default `5`), the plate is considered **verified**.
4. In realtime/live mode, verification fires a callback immediately and
   resets that plate's counter — so the same plate can be logged again
   later (a real second pass, or the video looping back around).
5. Verified detections are written to `detections`, and the `vehicles`
   table's `first_seen` / `last_seen` / `last_camera_id` are kept current
   on every insert.

All detection workers run in parallel, but **only the main thread ever
writes to SQLite** — workers hand results back through a queue (or, in
batch mode, a return value), so there's never lock contention between
writers.

---

## Database schema (high level)

| Table | Purpose |
|---|---|
| `cameras` | Registered cameras — id, location, road name |
| `vehicles` | One row per plate ever seen — first/last seen, last camera |
| `detections` | One row per verified reading — plate, camera, timestamp, confidence |
| `blacklist` | Flagged plates with a reason and status |
| `traffic_density` | 10-minute bucketed distinct-vehicle counts per camera |

SQLite runs in **WAL mode** with a shared write lock, so reads (API
queries) are never blocked by the background density-flush thread or by
detection inserts. You'll see `anpr_system.db-wal` and `anpr_system.db-shm`
alongside the main `.db` file while it's running — that's expected, they
get checkpointed back into the main file on clean shutdown.

---

## Getting started

### Backend

```bash
cd vectra
source ai/.venv/bin/activate      # or create one: python -m venv ai/.venv

pip install ultralytics paddleocr opencv-python flask --break-system-packages
```

Run detection in whichever mode fits what you're testing:

```bash
# one pass per camera, saved at the end
python run_anpr_parallel.py --workers 3 --frame-skip 2

# one pass per camera, saved the instant a plate is verified
python run_realtime.py --frame-skip 2

# loops every camera forever — Ctrl+C to stop
python run_live.py --frame-skip 2
```

Start the API (serves data to the frontend):

```bash
python database/anpr_api.py
# → http://127.0.0.1:5001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

The dashboard polls the API on an interval (see `src/hooks/useDashboard.js`)
so Command Center stats, recent detections, and per-camera density stay
current without a manual refresh.

---

## Command-line options (detection scripts)

| Flag | Meaning | Default |
|---|---|---|
| `--workers` | how many cameras process at once (batch mode only) | `2` |
| `--frame-skip` | process every Nth frame — 2–3 roughly halves runtime | `1` (batch/realtime) / `2` (live) |
| `--cameras` | only run specific camera ids, e.g. `--cameras CAM-01 CAM-03` | all |
| `--threshold` | reads required before a plate counts as verified | `5` |
| `--mode` | `thread` or `process` (batch mode only) | `thread` |
| `--db` | SQLite file to use | `anpr_system.db` |
| `--model` | path to YOLO weights | `ai/models/best.pt` |

---

## Known limitations / next steps

- Detection timestamps use the machine's clock, not the video's internal
  timestamp — fine for live camera feeds, but means trajectory ordering
  across cameras isn't meaningful when replaying old recorded footage.
- OCR occasionally produces near-duplicate reads of the same plate
  (e.g. `0` vs `O`, `1` vs `I`) as separate verified entries — a
  similarity-merge step would clean this up.
- Live-feed updates on the frontend currently use polling rather than a
  push-based connection (e.g. WebSockets / Server-Sent Events); fine for
  a few cameras, worth revisiting if the camera count grows.
- Cameras don't store latitude/longitude — the city map in the dashboard
  uses fixed placement, not real coordinates.

---

## License

Internal prototype — license not yet decided.
