import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

// Flask API
const API_BASE =
  import.meta.env?.VITE_ANPR_API_URL || 'http://127.0.0.1:5001'

const EMPTY_STATE = {
  activeCameras: 0,
  totalCameras: 0,
  cameras: [],
  vehiclesToday: 0,
  recentDetections: [],
  densityByNode: [],
  hourlyTraffic: [],
  avgSpeed: null,
}

function mapPayload(payload) {
  return {
    activeCameras: payload.active_cameras ?? 0,

    totalCameras: payload.total_cameras ?? 0,

    cameras: payload.cameras ?? [],

    vehiclesToday: payload.vehicles_today ?? 0,

    recentDetections: (payload.recent_detections ?? []).map(
      (d, i) => ({
        id: `${d.plate_number}-${d.timestamp}-${i}`,
        plate: d.plate_number,
        camera: d.camera_id,
        time: d.time,
        confidence: d.confidence_score,
      })
    ),

    // Command Center + Analytics density
    densityByNode: payload.density_by_node ?? [],

    // Analytics hourly graph
    hourlyTraffic: payload.hourly_traffic ?? [],

    // Currently not implemented in backend
    avgSpeed: payload.avg_speed ?? null,
  }
}

export default function useDashboard() {
  const [data, setData] = useState(EMPTY_STATE)
  const [connected, setConnected] = useState(false)

  const socketRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    // --------------------------------------------------
    // Initial REST request
    // --------------------------------------------------

    fetch(`${API_BASE}/api/dashboard`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(
            `Dashboard API returned ${res.status}`
          )
        }

        return res.json()
      })
      .then((payload) => {
        if (!cancelled) {
          setData(mapPayload(payload))
        }
      })
      .catch((err) => {
        console.error(
          'dashboard: initial fetch failed',
          err
        )
      })

    // --------------------------------------------------
    // Socket.IO connection
    // --------------------------------------------------

    const socket = io(API_BASE)

    socketRef.current = socket

    socket.on('connect', () => {
      console.log('Dashboard Socket.IO connected')
      setConnected(true)
    })

    socket.on('disconnect', () => {
      console.log('Dashboard Socket.IO disconnected')
      setConnected(false)
    })

    socket.on('dashboard_update', (payload) => {
      if (!cancelled) {
        setData(mapPayload(payload))
      }
    })

    // --------------------------------------------------
    // Cleanup
    // --------------------------------------------------

    return () => {
      cancelled = true
      socket.disconnect()
      socketRef.current = null
    }
  }, [])

  return {
    ...data,
    connected,
  }
}