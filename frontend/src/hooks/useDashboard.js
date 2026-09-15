import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

// Set VITE_ANPR_API_URL in your .env if the API isn't on localhost:5001
const API_BASE = import.meta.env?.VITE_ANPR_API_URL || 'http://127.0.0.1:5001'

const EMPTY_STATE = {
  activeCameras: 0,
  totalCameras: 0,
  cameras: [],
  vehiclesToday: 0,
  recentDetections: [],
  densityByNode: [],
  avgSpeed: null,
}

function mapPayload(payload) {
  return {
    activeCameras: payload.active_cameras,
    totalCameras: payload.total_cameras,
    cameras: payload.cameras, // [{ camera_id, location_name, road_name, active }]
    vehiclesToday: payload.vehicles_today,
    recentDetections: payload.recent_detections.map((d, i) => ({
      id: `${d.plate_number}-${d.timestamp}-${i}`,
      plate: d.plate_number,
      camera: d.camera_id,
      time: d.time,
      confidence: d.confidence_score,
    })),
    densityByNode: payload.density_by_node, // [{ camera, density }]
    avgSpeed: payload.avg_speed, // currently always null - see backend note
  }
}

/**
 * Live dashboard data: REST fetch on mount for the first paint, then a
 * Socket.IO connection ("dashboard_update" events) keeps it fresh.
 */
export default function useDashboard() {
  const [data, setData] = useState(EMPTY_STATE)
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    fetch(`${API_BASE}/api/dashboard`)
      .then((res) => res.json())
      .then((payload) => {
        if (!cancelled) setData(mapPayload(payload))
      })
      .catch((err) => console.error('dashboard: initial fetch failed', err))

    const socket = io(API_BASE, { transports: ['websocket'] })
    socketRef.current = socket

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))
    socket.on('dashboard_update', (payload) => setData(mapPayload(payload)))

    return () => {
      cancelled = true
      socket.disconnect()
    }
  }, [])

  return { ...data, connected }
}