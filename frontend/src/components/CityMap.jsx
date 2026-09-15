import { cameras } from '../data/mockData'

// A schematic node graph, not a geo-accurate map — this is the same choice
// the plan calls for: represent 5 simulated camera nodes and let the route
// reconstruction be the visual story, without depending on live map tiles.
export default function CityMap({ route = [], highlightCamera = null, showAllNodes = true }) {
  const routeNodes = route.map(r => r.node).filter(Boolean)

  return (
    <svg viewBox="0 0 380 360" className="w-full h-full">
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0H0V20" fill="none" stroke="#1A202C" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="380" height="360" fill="url(#grid)" />

      {/* route path */}
      {routeNodes.length > 1 && (
        <polyline
          points={routeNodes.map(n => `${n.x},${n.y}`).join(' ')}
          fill="none"
          stroke="#4C8DFF"
          strokeWidth="2"
          className="route-flow"
        />
      )}

      {/* camera nodes */}
      {showAllNodes && cameras.map(cam => {
        const onRoute = routeNodes.some(n => n.id === cam.id)
        const isHighlight = highlightCamera === cam.id
        return (
          <g key={cam.id} transform={`translate(${cam.x},${cam.y})`}>
            {isHighlight && <circle r="14" fill="#EF4444" opacity="0.18" />}
            <circle
              r={onRoute ? 6 : 4.5}
              fill={isHighlight ? '#EF4444' : onRoute ? '#4C8DFF' : '#3A4256'}
              stroke="#0A0E14"
              strokeWidth="2"
            />
            <text x="10" y="4" className="font-mono" fontSize="9" fill="#8B93A6">
              {cam.id}
            </text>
            <text x="10" y="15" fontSize="8" fill="#5B6376">
              {cam.name}
            </text>
          </g>
        )
      })}

      {/* route order badges */}
      {routeNodes.map((n, i) => (
        <text
          key={i}
          x={n.x - 10}
          y={n.y - 10}
          fontSize="9"
          className="font-mono"
          fill="#4ADE80"
        >
          {i + 1}
        </text>
      ))}
    </svg>
  )
}
