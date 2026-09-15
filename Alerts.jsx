import { useEffect, useState } from 'react'
import CityMap from '../components/CityMap'
import {
  getBlacklist,
  getLastLocation,
  getTrajectory,
} from '../api'

export default function Alerts() {
  const [blacklist, setBlacklist] = useState([])
  const [selected, setSelected] = useState(null)

  const [lastLocation, setLastLocation] = useState(null)
  const [route, setRoute] = useState([])

  const [loading, setLoading] = useState(false)

  // =========================================================
  // LOAD BLACKLIST
  // Refresh every 10 seconds
  // =========================================================
  useEffect(() => {
    async function loadBlacklist() {
      try {
        const data = await getBlacklist()

        const vehicles = data.blacklist || []

        setBlacklist(vehicles)

        // Select first vehicle automatically
        // only if nothing is currently selected
        setSelected(prev => {
          if (prev) {
            // Keep currently selected vehicle if it still exists
            const stillExists = vehicles.some(
              v => v.plate_number === prev.plate_number
            )

            if (stillExists) {
              return prev
            }
          }

          return vehicles[0] || null
        })

      } catch (error) {
        console.error('Failed to load blacklist:', error)
      }
    }

    // Load immediately
    loadBlacklist()

    // Refresh every 10 seconds
    const interval = setInterval(loadBlacklist, 10000)

    // Stop polling when leaving page
    return () => clearInterval(interval)
  }, [])


  // =========================================================
  // LOAD SELECTED VEHICLE LOCATION + TRAJECTORY
  // Refresh every 10 seconds
  // =========================================================
  useEffect(() => {
    if (!selected?.plate_number) {
      setLastLocation(null)
      setRoute([])
      return
    }

    async function loadVehicle() {
      try {
        setLoading(true)

        const [locationData, trajectoryData] = await Promise.all([
          getLastLocation(selected.plate_number),
          getTrajectory(selected.plate_number),
        ])

        setLastLocation(locationData.data)
        setRoute(trajectoryData || [])

      } catch (error) {
        console.error(
          'Failed to load blacklist vehicle:',
          error
        )

        setLastLocation(null)
        setRoute([])

      } finally {
        setLoading(false)
      }
    }

    // Load immediately
    loadVehicle()

    // Refresh every 10 seconds
    const interval = setInterval(loadVehicle, 10000)

    // Stop polling when selected vehicle changes
    // or when leaving the page
    return () => clearInterval(interval)

  }, [selected])


  // =========================================================
  // CURRENT CAMERA
  // =========================================================

  const currentCamera =
    lastLocation?.camera_id ||
    route[route.length - 1]?.camera_id ||
    null


  // =========================================================
  // CURRENT LOCATION
  // =========================================================

  const currentLocation =
    lastLocation?.location_name ||
    route[route.length - 1]?.location_name ||
    'Unknown'


  // =========================================================
  // CURRENT ROAD
  // =========================================================

  const currentRoad =
    lastLocation?.road_name ||
    route[route.length - 1]?.road_name ||
    'Unknown'


  // =========================================================
  // LAST SEEN TIME
  // =========================================================

  const currentTime =
    lastLocation?.timestamp ||
    route[route.length - 1]?.timestamp ||
    'Unknown'


  return (
    <div className="p-8 space-y-6">

      {/* =====================================================
          HEADER
      ====================================================== */}

      <header className="flex items-center justify-between">

        <div>
          <h1 className="text-lg font-semibold text-ink-100">
            Alert Center
          </h1>

          <p className="text-sm text-ink-500 mt-1">
            Blacklisted vehicles and their current locations
          </p>
        </div>

        <span className="text-xs font-mono text-signal-red border border-signal-red/40 bg-signal-red/10 px-2.5 py-1 rounded">
          {blacklist.length} BLACKLISTED
        </span>

      </header>


      {/* =====================================================
          MAIN AREA
      ====================================================== */}

      <div className="grid grid-cols-3 gap-4">

        {/* ===================================================
            BLACKLISTED VEHICLES
        ==================================================== */}

        <div className="col-span-2 space-y-2.5">

          {blacklist.length === 0 ? (

            <div className="border border-base-500 bg-base-800 rounded p-5 text-sm text-ink-500">
              No active blacklisted vehicles.
            </div>

          ) : (

            blacklist.map(vehicle => (

              <button
                key={vehicle.plate_number}
                onClick={() => setSelected(vehicle)}
                className={`w-full text-left border rounded p-4 flex items-center gap-4 transition-colors ${
                  selected?.plate_number === vehicle.plate_number
                    ? 'border-signal-blue bg-base-700'
                    : 'border-base-500 bg-base-800 hover:bg-base-700'
                }`}
              >

                {/* STATUS INDICATOR */}

                <div className="w-2 h-2 rounded-full bg-signal-red shrink-0" />

                {/* PLATE */}

                <div className="flex-1">

                  <div className="font-mono text-sm text-ink-100">
                    {vehicle.plate_number}
                  </div>

                  <div className="text-xs text-ink-500 mt-1">
                    Blacklisted vehicle
                  </div>

                </div>

                {/* FLAGGED TIME */}

                {vehicle.flagged_on && (
                  <div className="text-[11px] font-mono text-ink-700">
                    {vehicle.flagged_on}
                  </div>
                )}

              </button>

            ))

          )}

        </div>


        {/* ===================================================
            LOCATION + MAP
        ==================================================== */}

        <div className="border border-base-500 bg-base-800 rounded p-5 h-fit">

          <h2 className="text-sm font-medium text-ink-300 mb-3">
            Current Location
          </h2>


          {loading ? (

            <div className="h-56 flex items-center justify-center text-sm text-ink-500">
              Loading vehicle...
            </div>

          ) : !selected ? (

            <div className="h-56 flex items-center justify-center text-sm text-ink-500">
              Select a blacklisted vehicle
            </div>

          ) : (

            <>

              {/* MAP */}

              <div className="h-56 mb-4">

                <CityMap
                  route={route}
                  highlightCamera={currentCamera}
                  showAllNodes={true}
                />

              </div>


              {/* VEHICLE INFORMATION */}

              <div className="space-y-2 text-sm">

                <Row
                  label="Plate"
                  value={selected.plate_number}
                  mono
                />

                <Row
                  label="Last Camera"
                  value={currentCamera || 'Unknown'}
                  mono
                />

                <Row
                  label="Location"
                  value={currentLocation}
                />

                <Row
                  label="Road"
                  value={currentRoad}
                />

                <Row
                  label="Last Seen"
                  value={currentTime}
                />

              </div>

            </>

          )}

        </div>

      </div>


      {/* =====================================================
          TRAJECTORY
      ====================================================== */}

      <div className="border border-base-500 bg-base-800 rounded p-5">

        <h2 className="text-sm font-medium text-ink-300 mb-4">
          Vehicle Trajectory
        </h2>


        {route.length === 0 ? (

          <div className="text-sm text-ink-500">
            No trajectory available.
          </div>

        ) : (

          <div className="flex items-center gap-3 flex-wrap">

            {route.map((point, index) => (

              <div
                key={`${point.camera_id}-${point.timestamp}-${index}`}
                className="flex items-center gap-3"
              >

                {/* CAMERA NODE */}

                <div
                  className={`border rounded px-3 py-2 ${
                    index === route.length - 1
                      ? 'border-signal-red bg-signal-red/10'
                      : 'border-base-500 bg-base-700'
                  }`}
                >

                  <div className="font-mono text-xs text-ink-100">
                    {point.camera_id}
                  </div>

                  <div className="text-[11px] text-ink-500 mt-1">
                    {point.location_name}
                  </div>

                  <div className="text-[10px] text-ink-700 mt-1">
                    {point.timestamp}
                  </div>

                </div>


                {/* ARROW */}

                {index < route.length - 1 && (
                  <span className="text-ink-700">
                    →
                  </span>
                )}

              </div>

            ))}

          </div>

        )}

      </div>

    </div>
  )
}


// =============================================================
// SMALL ROW COMPONENT
// =============================================================

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between gap-4">

      <span className="text-ink-700 text-xs">
        {label}
      </span>

      <span
        className={
          mono
            ? 'font-mono text-ink-100 text-right'
            : 'text-ink-300 text-right'
        }
      >
        {value}
      </span>

    </div>
  )
}