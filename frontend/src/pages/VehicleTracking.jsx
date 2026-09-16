import { useState } from 'react'
import CityMap2 from '../components/CityMap2'
import { getTrajectory, getVehicle } from '../api'
import { blacklist } from '../data/mockData'

function timeDiffMinutes(a, b) {
  if (!a || !b) return null

  const dateA = new Date(a.replace(' ', 'T'))
  const dateB = new Date(b.replace(' ', 'T'))

  if (isNaN(dateA.getTime()) || isNaN(dateB.getTime())) {
    return null
  }

  return Math.round((dateB - dateA) / 60000)
}

export default function VehicleTracking() {
  const [query, setQuery] = useState('')
  const [searched, setSearched] = useState('')
  const [route, setRoute] = useState([])
  const [vehicle, setVehicle] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch(e) {
    e.preventDefault()

    const plate = query.trim().toUpperCase()

    if (!plate) return

    setSearched(plate)
    setLoading(true)
    setError('')
    setRoute([])
    setVehicle(null)

    try {
      const [vehicleData, trajectoryData] = await Promise.all([
        getVehicle(plate),
        getTrajectory(plate)
      ])

      setVehicle(vehicleData)
      setRoute(trajectoryData || [])
    } catch (err) {
      console.error('API error:', err)
      setError(err.message || 'Failed to fetch vehicle data')
    } finally {
      setLoading(false)
    }
  }

  const blacklistEntry = blacklist.find(
    b => b.plate === searched
  )

  const isBlacklisted = Boolean(blacklistEntry)

  const journey =
    route.length > 1
      ? timeDiffMinutes(
          route[0].timestamp,
          route[route.length - 1].timestamp
        )
      : null

  return (
    <div className="p-8 space-y-6">

      {/* HEADER */}
      <header>
        <h1 className="text-lg font-semibold text-ink-100">
          Vehicle Tracking
        </h1>

        <p className="text-sm text-ink-500 mt-1">
          Search a plate to reconstruct its cross-camera route
        </p>
      </header>

      {/* SEARCH */}
      <form
        onSubmit={handleSearch}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Enter vehicle number, e.g. LM07MKD"
          className="flex-1 max-w-md bg-base-700 border border-base-500 rounded px-4 py-2.5 text-sm font-mono text-ink-100 placeholder:text-ink-700 focus:border-signal-blue outline-none"
        />

        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2.5 rounded bg-signal-blue text-base-900 text-sm font-medium hover:brightness-110 transition disabled:opacity-50"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {/* ERROR */}
      {error && (
        <div className="border border-signal-red/40 bg-signal-red/10 rounded px-5 py-4 text-sm text-signal-red">
          {error}
        </div>
      )}

      {/* LOADING */}
      {loading && (
        <div className="border border-base-500 bg-base-800 rounded p-10 text-center text-ink-500 text-sm">
          Searching database for{' '}
          <span className="font-mono text-ink-300">
            {searched}
          </span>
          ...
        </div>
      )}

      {/* NO RESULTS */}
      {!loading &&
        searched &&
        route.length === 0 &&
        !error && (
          <div className="border border-base-500 bg-base-800 rounded p-10 text-center text-ink-500 text-sm">
            No detections found for{' '}
            <span className="font-mono text-ink-300">
              {searched}
            </span>
          </div>
        )}

      {/* RESULTS */}
      {!loading && route.length > 0 && (
        <>

          {/* BLACKLIST WARNING */}
          {isBlacklisted && (
            <div className="border border-signal-red/40 bg-signal-red/10 rounded px-5 py-4 flex items-center gap-3">

              <span className="w-2 h-2 rounded-full bg-signal-red live-dot shrink-0" />

              <div className="text-sm">

                <span className="font-mono text-signal-red font-medium">
                  {searched}
                </span>

                <span className="text-ink-300">
                  {' '}is on the active watch list —{' '}
                </span>

                <span className="text-ink-500">
                  {blacklistEntry?.reason}
                </span>

              </div>
            </div>
          )}

          {/* SUMMARY CARDS */}
          <div className="grid grid-cols-4 gap-4">

            {/* FIRST SEEN */}
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">

              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">
                First seen
              </div>

              <div className="font-mono text-xl text-ink-100">
                {route[0].timestamp || '—'}
              </div>

            </div>

            {/* LAST SEEN */}
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">

              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">
                Last seen
              </div>

              <div className="font-mono text-xl text-ink-100">
                {route[route.length - 1].timestamp || '—'}
              </div>

            </div>

            {/* CAMERAS */}
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">

              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">
                Cameras visited
              </div>

              <div className="font-mono text-xl text-ink-100">
                {route.length}
              </div>

            </div>

            {/* JOURNEY */}
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">

              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">
                Journey duration
              </div>

              <div className="font-mono text-xl text-ink-100">
                {journey !== null
                  ? `${journey} min`
                  : '—'}
              </div>

            </div>

          </div>

          {/* ROUTE + TIMELINE */}
          <div className="grid grid-cols-3 gap-4">

            {/* MAP */}
            <div className="col-span-2 border border-base-500 bg-base-800 rounded p-5">

              <h2 className="text-sm font-medium text-ink-300 mb-3">
                Reconstructed route
              </h2>

              <div className="h-80">
                <CityMap2
  route={route}
  showAllNodes={false}
 />
              </div>

            </div>

            {/* TIMELINE */}
            <div className="border border-base-500 bg-base-800 rounded p-5">

              <h2 className="text-sm font-medium text-ink-300 mb-3">
                Timeline
              </h2>

              <div className="space-y-0">

                {route.map((r, i) => (

                  <div
                    key={`${r.camera_id}-${r.timestamp}-${i}`}
                    className="relative pl-6 pb-5 last:pb-0"
                  >

                    {/* TIMELINE LINE */}
                    {i < route.length - 1 && (
                      <div className="absolute left-[7px] top-3 bottom-0 w-px bg-base-500" />
                    )}

                    {/* DOT */}
                    <div className="absolute left-0 top-1 w-3.5 h-3.5 rounded-full bg-base-700 border-2 border-signal-blue" />

                    {/* TIME */}
                    <div className="font-mono text-sm text-ink-100">
                      {r.timestamp || '—'}
                    </div>

                    {/* CAMERA */}
                    <div className="text-xs text-ink-500">
                      {r.camera_id || 'Unknown camera'}
                      {' · '}
                      {r.location_name || ''}
                    </div>

                    {/* ROAD */}
                    <div className="text-[11px] text-ink-700 mt-0.5">
                      {r.road_name || 'Road unavailable'}
                      {' · '}
                      {r.confidence_score !== undefined
                        ? `${Math.round(r.confidence_score * 100)}% confidence`
                        : 'Confidence unavailable'}
                    </div>

                  </div>

                ))}

              </div>

            </div>

          </div>

        </>

      )}

    </div>
  )
}