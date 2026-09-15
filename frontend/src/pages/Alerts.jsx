import { useState } from 'react'
import CityMap from '../components/CityMap'
import { alerts, blacklist } from '../data/mockData'

const severityStyle = {
  HIGH:   'text-signal-red border-signal-red/40 bg-signal-red/10',
  MEDIUM: 'text-signal-amber border-signal-amber/40 bg-signal-amber/10',
  LOW:    'text-ink-500 border-base-500 bg-base-700',
}

export default function Alerts() {
  const [selected, setSelected] = useState(alerts[0])

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-ink-100">Alert Center</h1>
          <p className="text-sm text-ink-500 mt-1">Blacklist matches and route anomalies, newest first</p>
        </div>
        <span className="text-xs font-mono text-signal-red border border-signal-red/40 bg-signal-red/10 px-2.5 py-1 rounded">
          {alerts.length} ACTIVE
        </span>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-2.5">
          {alerts.map(a => (
            <button
              key={a.id}
              onClick={() => setSelected(a)}
              className={`w-full text-left border rounded p-4 flex items-start gap-4 transition-colors ${
                selected.id === a.id ? 'border-signal-blue bg-base-700' : 'border-base-500 bg-base-800 hover:bg-base-700'
              }`}
            >
              <span className={`shrink-0 text-[10px] font-mono px-2 py-1 rounded border ${severityStyle[a.severity]}`}>
                {a.severity}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-ink-100">{a.plate}</span>
                  <span className="text-[11px] font-mono text-ink-700">{a.time}</span>
                </div>
                <div className="text-xs text-ink-500 mt-1">{a.type === 'BLACKLIST' ? 'Blacklisted vehicle detected' : 'Suspicious route transition'} · {a.camera}</div>
                <div className="text-[11px] text-ink-700 mt-1">{a.note}</div>
              </div>
            </button>
          ))}
        </div>

        <div className="border border-base-500 bg-base-800 rounded p-5 h-fit">
          <h2 className="text-sm font-medium text-ink-300 mb-3">Location</h2>
          <div className="h-56 mb-4">
            <CityMap highlightCamera={selected.camera.split('→')[0]} />
          </div>
          <div className="space-y-2 text-sm">
            <Row label="Alert ID" value={selected.id} />
            <Row label="Plate" value={selected.plate} mono />
            <Row label="Camera" value={selected.camera} />
            <Row label="Time" value={selected.time} />
            <Row label="Type" value={selected.type.replace('_', ' ')} />
          </div>
        </div>
      </div>

      <div className="border border-base-500 bg-base-800 rounded p-5">
        <h2 className="text-sm font-medium text-ink-300 mb-4">Watch list</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-ink-700 border-b border-base-600">
              <th className="pb-2 font-normal">Plate</th>
              <th className="pb-2 font-normal">Reason</th>
              <th className="pb-2 font-normal">Priority</th>
            </tr>
          </thead>
          <tbody>
            {blacklist.map(b => (
              <tr key={b.plate} className="border-b border-base-600/60 last:border-0">
                <td className="py-2.5 font-mono text-ink-100">{b.plate}</td>
                <td className="py-2.5 text-ink-500">{b.reason}</td>
                <td className="py-2.5">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${severityStyle[b.priority] || severityStyle.LOW}`}>
                    {b.priority}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-700 text-xs">{label}</span>
      <span className={mono ? 'font-mono text-ink-100' : 'text-ink-300'}>{value}</span>
    </div>
  )
}
