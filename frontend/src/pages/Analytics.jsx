import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
} from 'recharts'

import { odMatrix } from '../data/mockData'
import useDashboard from '../hooks/useDashboard'

const tooltipStyle = {
  background: '#12161F',
  border: '1px solid #232A38',
  borderRadius: 6,
  fontSize: 12,
  color: '#E8EAED',
}

export default function Analytics() {
  // --------------------------------------------------
  // LIVE DATA FROM FLASK + SOCKET.IO
  // --------------------------------------------------

  const {
    densityByNode,
    hourlyTraffic,
  } = useDashboard()

  // Find highest density for the heatmap bar.
  // Minimum 1 prevents division by zero.
  const maxDensity = Math.max(
    ...densityByNode.map((camera) => camera.density),
    1
  )

  return (
    <div className="p-8 space-y-6">

      {/* ==================================================
          HEADER
      ================================================== */}

      <header>
        <h1 className="text-lg font-semibold text-ink-100">
          Traffic Analytics
        </h1>

        <p className="text-sm text-ink-500 mt-1">
          City-level patterns aggregated from every detection event
        </p>
      </header>


      {/* ==================================================
          TOP SECTION
          Density + Average Speed
      ================================================== */}

      <div className="grid grid-cols-2 gap-4">

        {/* ==================================================
            DENSITY HEATMAP BY NODE
        ================================================== */}

        <div className="border border-base-500 bg-base-800 rounded p-5">

          <h2 className="text-sm font-medium text-ink-300 mb-4">
            Density heatmap by node
          </h2>

          <div className="space-y-3">

            {densityByNode.length === 0 ? (

              <div className="text-xs text-ink-500">
                Waiting for traffic data...
              </div>

            ) : (

              densityByNode.map((camera) => (

                <div
                  key={camera.camera}
                  className="flex items-center gap-3"
                >

                  {/* Camera name */}

                  <span className="font-mono text-[11px] text-ink-500 w-16">
                    {camera.camera}
                  </span>


                  {/* Density bar */}

                  <div className="flex-1 h-3 bg-base-600 rounded overflow-hidden">

                    <div
                      className="h-full bg-gradient-to-r from-signal-blue to-signal-red"
                      style={{
                        width: `${Math.min(
                          (camera.density / maxDensity) * 100,
                          100
                        )}%`,
                      }}
                    />

                  </div>


                  {/* Density value */}

                  <span className="font-mono text-[11px] text-ink-500 w-20 text-right">
                    {camera.density} veh/min
                  </span>

                </div>

              ))

            )}

          </div>

        </div>


        {/* ==================================================
            AVERAGE SPEED BY NODE

            Still mock for now.
        ================================================== */}

        <div className="border border-base-500 bg-base-800 rounded p-5">

          <h2 className="text-sm font-medium text-ink-300 mb-4">
            Average speed by node
          </h2>

          <div className="space-y-3">

            {[
              { camera: 'CAM-01', speed: 42 },
              { camera: 'CAM-02', speed: 35 },
              { camera: 'CAM-03', speed: 17 },
              { camera: 'CAM-04', speed: 38 },
              { camera: 'CAM-05', speed: 26 },
            ].map((camera) => (

              <div
                key={camera.camera}
                className="flex items-center justify-between text-sm"
              >

                <span className="font-mono text-ink-500">
                  {camera.camera}
                </span>

                <span
                  className={`font-mono ${
                    camera.speed < 20
                      ? 'text-signal-red'
                      : 'text-ink-100'
                  }`}
                >
                  {camera.speed} km/h{' '}
                  {camera.speed < 20 && '⚠'}
                </span>

              </div>

            ))}

          </div>


          <div className="mt-4 pt-4 border-t border-base-600 text-[11px] text-ink-700">
            Congestion rule: density &gt; 70 veh/min AND speed &lt; 20 km/h
          </div>

        </div>

      </div>


      {/* ==================================================
          HOURLY TRAFFIC VOLUME
          REAL DATABASE DATA
      ================================================== */}

      <div className="border border-base-500 bg-base-800 rounded p-5">

        <h2 className="text-sm font-medium text-ink-300 mb-4">
          Hourly traffic volume
        </h2>

        <div className="h-64">

          {hourlyTraffic.length === 0 ? (

            <div className="h-full flex items-center justify-center text-xs text-ink-500">
              Waiting for traffic data...
            </div>

          ) : (

            <ResponsiveContainer
              width="100%"
              height="100%"
            >

              <LineChart data={hourlyTraffic}>

                <CartesianGrid
                  stroke="#1A202C"
                  vertical={false}
                />

                <XAxis
                  dataKey="hour"
                  stroke="#5B6376"
                  fontSize={11}
                  tickLine={false}
                  axisLine={{
                    stroke: '#232A38',
                  }}
                />

                <YAxis
                  stroke="#5B6376"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />

                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{
                    color: '#8B93A6',
                  }}
                />

                <Line
                  type="monotone"
                  dataKey="vehicles"
                  stroke="#4C8DFF"
                  strokeWidth={2}
                  dot={false}
                />

              </LineChart>

            </ResponsiveContainer>

          )}

        </div>

      </div>
    </div>
  )
}