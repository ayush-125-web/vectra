import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar,
} from 'recharts'
import { cameraLoad, hourlyTraffic, odMatrix } from '../data/mockData'

const tooltipStyle = {
  background: '#12161F',
  border: '1px solid #232A38',
  borderRadius: 6,
  fontSize: 12,
  color: '#E8EAED',
}

export default function Analytics() {
  const maxDensity = Math.max(...cameraLoad.map(c => c.density))

  return (
    <div className="p-8 space-y-6">
      <header>
        <h1 className="text-lg font-semibold text-ink-100">Traffic Analytics</h1>
        <p className="text-sm text-ink-500 mt-1">City-level patterns aggregated from every detection event</p>
      </header>

      <div className="grid grid-cols-2 gap-4">
        <div className="border border-base-500 bg-base-800 rounded p-5">
          <h2 className="text-sm font-medium text-ink-300 mb-4">Density heatmap by node</h2>
          <div className="space-y-3">
            {cameraLoad.map(c => (
              <div key={c.camera} className="flex items-center gap-3">
                <span className="font-mono text-[11px] text-ink-500 w-16">{c.camera}</span>
                <div className="flex-1 h-3 bg-base-600 rounded overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-signal-blue to-signal-red"
                    style={{ width: `${(c.density / maxDensity) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-[11px] text-ink-500 w-20 text-right">{c.density} veh/min</span>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-base-500 bg-base-800 rounded p-5">
          <h2 className="text-sm font-medium text-ink-300 mb-4">Average speed by node</h2>
          <div className="space-y-3">
            {cameraLoad.map(c => (
              <div key={c.camera} className="flex items-center justify-between text-sm">
                <span className="font-mono text-ink-500">{c.camera}</span>
                <span className={`font-mono ${c.speed < 20 ? 'text-signal-red' : 'text-ink-100'}`}>
                  {c.speed} km/h {c.speed < 20 && '⚠'}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-base-600 text-[11px] text-ink-700">
            Congestion rule: density &gt; 70 veh/min AND speed &lt; 20 km/h
          </div>
        </div>
      </div>

      <div className="border border-base-500 bg-base-800 rounded p-5">
        <h2 className="text-sm font-medium text-ink-300 mb-4">Hourly traffic volume</h2>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hourlyTraffic}>
              <CartesianGrid stroke="#1A202C" vertical={false} />
              <XAxis dataKey="hour" stroke="#5B6376" fontSize={11} tickLine={false} axisLine={{ stroke: '#232A38' }} />
              <YAxis stroke="#5B6376" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#8B93A6' }} />
              <Line type="monotone" dataKey="vehicles" stroke="#4C8DFF" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="border border-base-500 bg-base-800 rounded p-5">
        <h2 className="text-sm font-medium text-ink-300 mb-4">Origin → Destination flow</h2>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={odMatrix} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke="#1A202C" horizontal={false} />
              <XAxis type="number" stroke="#5B6376" fontSize={11} tickLine={false} axisLine={{ stroke: '#232A38' }} />
              <YAxis dataKey="pair" type="category" stroke="#8B93A6" fontSize={11} tickLine={false} axisLine={false} width={140} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#8B93A6' }} />
              <Bar dataKey="vehicles" fill="#4C8DFF" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
