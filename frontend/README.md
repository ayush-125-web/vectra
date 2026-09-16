# ATLAS — City Traffic Intelligence (frontend prototype)

Frontend for the multi-camera ANPR + trajectory-tracking SIH project. Built with
React, Tailwind, React Router and Recharts. Runs entirely on mock data shaped
like the planned FastAPI responses, so it's demo-ready without a backend and
drops straight onto the real API later.

## Run it

```bash
npm install
npm run dev
```

Then open the printed local URL (usually http://localhost:5173).

## Structure

```
src/
  data/mockData.js     mock cameras, detections, alerts, analytics — this
                        mirrors the exact shape /detections, /vehicles/{plate}/
                        trajectory, /analytics and /alerts should return
  components/
    Sidebar.jsx         left nav
    StatReadout.jsx     the big-number stat blocks
    CityMap.jsx         schematic 5-node SVG map used on every page
  pages/
    CommandCenter.jsx   home / overview page
    VehicleTracking.jsx plate search + reconstructed route + timeline
    Analytics.jsx       density, speed, hourly volume, OD flow (recharts)
    Alerts.jsx          blacklist + route-anomaly alert feed + watch list
```

## Wiring up the real backend

Every page reads from `src/data/mockData.js`. To connect the FastAPI backend:

1. Replace the imports in each page with calls to your API
   (`GET /vehicles/{plate}/trajectory`, `GET /analytics`, `GET /alerts`, etc).
2. Keep the field names the same (`plate`, `camera`, `time`, `confidence`,
   `node.x` / `node.y` for map coordinates) and every component keeps working
   unchanged.
3. `getTrajectory(plate)` in `mockData.js` is the one function to swap for a
   real `fetch` — it's the only place trajectory logic lives.

## Notable choices

- The map is a schematic SVG node graph, not a tiled map — it demos the
  camera network and route reconstruction without depending on internet
  map tiles during a live demo.
- The "golden vehicle" `TN09AB1234` is pre-wired to appear across all 5
  cameras with a blacklist hit at CAM-03, for a deterministic demo flow.
- Dark, monospace-forward look intentionally reads as ops/telemetry
  software rather than a marketing dashboard.
