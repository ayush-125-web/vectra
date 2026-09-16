import StatReadout from '../components/StatReadout'
import CityMap from '../components/CityMap'
import { summary, alerts } from '../data/mockData'
import useDashboard from '../hooks/useDashboard'

export default function CommandCenter() {
  const {
    activeCameras,
    totalCameras,
    cameras,
    vehiclesToday,
    recentDetections,
    densityByNode,
    avgSpeed,
    connected,
  } = useDashboard()

  const recent = recentDetections.slice(0, 6)
  // Priority alerts: left on mock data for now, as requested.
  const topAlerts = alerts.slice(0, 3)

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-ink-100">Command Center</h1>
          <p className="text-sm text-ink-500 mt-1">Five-node ANPR network — Chennai prototype grid</p>
        </div>
        <div className={`flex items-center gap-2 text-xs font-mono ${connected ? 'text-signal-green' : 'text-ink-700'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-signal-green live-dot' : 'bg-ink-700'}`} />
          {connected ? 'LIVE' : 'CONNECTING'}
        </div>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <StatReadout label="Active cameras" value={`${activeCameras}/${totalCameras}`} />
        <StatReadout label="Vehicles today" value={vehiclesToday.toLocaleString()} />
        <StatReadout label="Avg. speed" value={avgSpeed ?? '—'} unit="km/h" />
        {/* Active alerts stat kept on mock data too, same as the Priority alerts panel below */}
        <StatReadout label="Active alerts" value={summary.activeAlerts} tone="red" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 border border-base-500 bg-base-800 rounded p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-ink-300">Camera network</h2>
            <span className="text-[11px] font-mono text-ink-700">{cameras.length} nodes</span>
          </div>
          <div className="h-80">
            {/* CityMap needs a small update to read cam.active and color
               the dot green/gray - see chat notes, file wasn't shared. */}
            <CityMap cameras={cameras} />
          </div>
        </div>

        <div className="border border-base-500 bg-base-800 rounded p-5">
          <h2 className="text-sm font-medium text-ink-300 mb-3">Recent detections</h2>
          <div className="space-y-2.5">
            {recent.map(d => (
              <div key={d.id} className="flex items-center justify-between text-sm border-b border-base-600 pb-2.5 last:border-0 last:pb-0">
                <div>
                  <div className="font-mono text-ink-100">{d.plate}</div>
                  <div className="text-[11px] text-ink-700">{d.camera} · {d.time}</div>
                </div>
                <span className="font-mono text-[11px] text-ink-500">{Math.round(d.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="border border-base-500 bg-base-800 rounded p-5">
          <h2 className="text-sm font-medium text-ink-300 mb-4">Density by node</h2>
          <div className="space-y-3">
            {densityByNode.map(c => (
              <div key={c.camera} className="flex items-center gap-3">
                <span className="font-mono text-[11px] text-ink-500 w-16">{c.camera}</span>
                <div className="flex-1 h-2 bg-base-600 rounded overflow-hidden">
                  <div
                    className={`h-full ${c.density > 75 ? 'bg-signal-red' : c.density > 55 ? 'bg-signal-amber' : 'bg-signal-blue'}`}
                    style={{ width: `${Math.min(c.density, 100)}%` }}
                  />
                </div>
                <span className="font-mono text-[11px] text-ink-500 w-16 text-right">{c.density}/min</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}