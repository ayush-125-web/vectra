// Mock event-pipeline data — shaped exactly like what the FastAPI backend
// (POST /detections, GET /vehicles/{plate}/trajectory, GET /analytics, GET /alerts)
// is expected to return. Swap the fetch calls in src/api.js for a real API
// later without touching any component.

export const cameras = [
  { id: 'CAM-01', name: 'Anna Nagar',  road: 'Anna Nagar 2nd Ave',   x: 120, y: 90,  direction: 'NORTH' },
  { id: 'CAM-02', name: 'Kilpauk',     road: 'Poonamallee High Rd',  x: 260, y: 60,  direction: 'EAST'  },
  { id: 'CAM-03', name: 'Egmore',      road: 'Gandhi Irwin Rd',      x: 300, y: 190, direction: 'SOUTH' },
  { id: 'CAM-04', name: 'Guindy',      road: 'GST Road',             x: 210, y: 300, direction: 'SOUTH' },
  { id: 'CAM-05', name: 'T Nagar',     road: 'Usman Rd',             x: 100, y: 240, direction: 'WEST'  },
]

// The "golden vehicle" — appears deterministically across all five cameras
// so the trajectory + alert demo is reproducible every time.
export const goldenPlate = 'TN09AB1234'

export const detections = [
  { id: 1, plate: 'TN09AB1234', camera: 'CAM-01', time: '10:02:31', confidence: 0.94, vehicleType: 'Sedan', speed: 41 },
  { id: 2, plate: 'TN22CD5521', camera: 'CAM-02', time: '10:03:09', confidence: 0.88, vehicleType: 'Auto',  speed: 22 },
  { id: 3, plate: 'TN09AB1234', camera: 'CAM-02', time: '10:07:42', confidence: 0.91, vehicleType: 'Sedan', speed: 35 },
  { id: 4, plate: 'KA01ZZ8899', camera: 'CAM-03', time: '10:09:15', confidence: 0.79, vehicleType: 'SUV',   speed: 18 },
  { id: 5, plate: 'TN09AB1234', camera: 'CAM-03', time: '10:14:08', confidence: 0.96, vehicleType: 'Sedan', speed: 17 },
  { id: 6, plate: 'TN10XY4567', camera: 'CAM-04', time: '10:16:52', confidence: 0.85, vehicleType: 'Bike',  speed: 29 },
  { id: 7, plate: 'TN09AB1234', camera: 'CAM-04', time: '10:21:19', confidence: 0.90, vehicleType: 'Sedan', speed: 38 },
  { id: 8, plate: 'TN09AB1234', camera: 'CAM-05', time: '10:27:45', confidence: 0.93, vehicleType: 'Sedan', speed: 26 },
]

export const blacklist = [
  { plate: 'TN09AB1234', reason: 'Reported stolen — FIR #4471/2026', priority: 'HIGH' },
  { plate: 'TN10XY4567', reason: 'Pending e-challan, repeat offender', priority: 'MEDIUM' },
  { plate: 'KA01ZZ8899', reason: 'Flagged — interstate watch list', priority: 'HIGH' },
]

export const alerts = [
  { id: 'A-104', plate: 'TN09AB1234', camera: 'CAM-03', time: '10:14:08', type: 'BLACKLIST', severity: 'HIGH',   note: 'Reported stolen — FIR #4471/2026' },
  { id: 'A-103', plate: 'TN10XY4567', camera: 'CAM-04', time: '10:16:52', type: 'BLACKLIST', severity: 'MEDIUM', note: 'Pending e-challan, repeat offender' },
  { id: 'A-102', plate: 'KA01ZZ8899', camera: 'CAM-03', time: '10:09:15', type: 'BLACKLIST', severity: 'HIGH',   note: 'Flagged — interstate watch list' },
  { id: 'A-101', plate: 'TN22CD5521', camera: 'CAM-01→CAM-02', time: '10:03:09', type: 'ROUTE_ANOMALY', severity: 'LOW', note: 'Camera transition faster than minimum travel time' },
]

export const cameraLoad = [
  { camera: 'CAM-01', density: 42, speed: 42 },
  { camera: 'CAM-02', density: 65, speed: 35 },
  { camera: 'CAM-03', density: 87, speed: 17 },
  { camera: 'CAM-04', density: 51, speed: 38 },
  { camera: 'CAM-05', density: 34, speed: 26 },
]

export const hourlyTraffic = [
  { hour: '06:00', vehicles: 210 }, { hour: '07:00', vehicles: 480 },
  { hour: '08:00', vehicles: 910 }, { hour: '09:00', vehicles: 1120 },
  { hour: '10:00', vehicles: 1240 }, { hour: '11:00', vehicles: 980 },
  { hour: '12:00', vehicles: 860 }, { hour: '13:00', vehicles: 900 },
  { hour: '14:00', vehicles: 870 }, { hour: '15:00', vehicles: 940 },
  { hour: '16:00', vehicles: 1080 }, { hour: '17:00', vehicles: 1310 },
]

export const odMatrix = [
  { pair: 'CAM-01 → CAM-03', vehicles: 2341 },
  { pair: 'CAM-02 → CAM-05', vehicles: 1872 },
  { pair: 'CAM-03 → CAM-04', vehicles: 1420 },
  { pair: 'CAM-05 → CAM-01', vehicles: 968 },
]

export const summary = {
  activeCameras: cameras.length,
  vehiclesToday: 12452,
  avgSpeed: 32,
  activeAlerts: alerts.length,
}

// Camera-to-camera trajectory helper — sorts a plate's detections by time
// and resolves each detection's camera into map coordinates.
export function getTrajectory(plate) {
  const hits = detections
    .filter(d => d.plate === plate)
    .sort((a, b) => a.time.localeCompare(b.time))
  return hits.map(d => ({ ...d, node: cameras.find(c => c.id === d.camera) }))
}
