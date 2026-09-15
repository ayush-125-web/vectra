import { useMemo, useState } from 'react'
import CityMap from '../components/CityMap'
import { getTrajectory, goldenPlate, blacklist } from '../data/mockData'

function timeDiffMinutes(a, b) {
  const [ah, am, as] = a.split(':').map(Number)
  const [bh, bm, bs] = b.split(':').map(Number)
  return Math.round(((bh * 3600 + bm * 60 + bs) - (ah * 3600 + am * 60 + as)) / 60)
}

export default function VehicleTracking() {
  const [query, setQuery] = useState(goldenPlate)
  const [searched, setSearched] = useState(goldenPlate)

  const route = useMemo(() => getTrajectory(searched), [searched])
  const isBlacklisted = blacklist.some(b => b.plate === searched)

  const journey = route.length > 1
    ? timeDiffMinutes(route[0].time, route[route.length - 1].time)
    : null

  function handleSearch(e) {
    e.preventDefault()
    setSearched(query.trim().toUpperCase())
  }

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-lg font-semibold text-ink-100">Vehicle Tracking</h1>
        <p className="text-sm text-ink-500 mt-1">Search a plate to reconstruct its cross-camera route</p>
      </header>

      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Enter vehicle number, e.g. TN09AB1234"
          className="flex-1 max-w-md bg-base-700 border border-base-500 rounded px-4 py-2.5 text-sm font-mono text-ink-100 placeholder:text-ink-700 focus:border-signal-blue outline-none"
        />
        <button
          type="submit"
          className="px-5 py-2.5 rounded bg-signal-blue text-base-900 text-sm font-medium hover:brightness-110 transition"
        >
          Search
        </button>
      </form>

      {route.length === 0 ? (
        <div className="border border-base-500 bg-base-800 rounded p-10 text-center text-ink-500 text-sm">
          No detections found for <span className="font-mono text-ink-300">{searched || '—'}</span>
        </div>
      ) : (
        <>
          {isBlacklisted && (
            <div className="border border-signal-red/40 bg-signal-red/10 rounded px-5 py-4 flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-signal-red live-dot shrink-0" />
              <div className="text-sm">
                <span className="font-mono text-signal-red font-medium">{searched}</span>
                <span className="text-ink-300"> is on the active watch list — </span>
                <span className="text-ink-500">{blacklist.find(b => b.plate === searched)?.reason}</span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-4 gap-4">
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">
              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">First seen</div>
              <div className="font-mono text-xl text-ink-100">{route[0].time}</div>
            </div>
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">
              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">Last seen</div>
              <div className="font-mono text-xl text-ink-100">{route[route.length - 1].time}</div>
            </div>
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">
              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">Cameras visited</div>
              <div className="font-mono text-xl text-ink-100">{route.length}</div>
            </div>
            <div className="border border-base-500 bg-base-800 rounded px-5 py-4">
              <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">Journey duration</div>
              <div className="font-mono text-xl text-ink-100">{journey !== null ? `${journey} min` : '—'}</div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 border border-base-500 bg-base-800 rounded p-5">
              <h2 className="text-sm font-medium text-ink-300 mb-3">Reconstructed route</h2>
              <div className="h-80">
                <CityMap route={route} />
              </div>
            </div>

            <div className="border border-base-500 bg-base-800 rounded p-5">
              <h2 className="text-sm font-medium text-ink-300 mb-3">Timeline</h2>
              <div className="space-y-0">
                {route.map((r, i) => (
                  <div key={r.id} className="relative pl-6 pb-5 last:pb-0">
                    {i < route.length - 1 && (
                      <div className="absolute left-[7px] top-3 bottom-0 w-px bg-base-500" />
                    )}
                    <div className="absolute left-0 top-1 w-3.5 h-3.5 rounded-full bg-base-700 border-2 border-signal-blue" />
                    <div className="font-mono text-sm text-ink-100">{r.time}</div>
                    <div className="text-xs text-ink-500">{r.camera} · {r.node?.name}</div>
                    <div className="text-[11px] text-ink-700 mt-0.5">{r.node?.direction} · {r.confidence * 100 | 0}% confidence</div>
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
