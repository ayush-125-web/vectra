// A schematic node graph, not a geo-accurate map.
// Camera positions are still taken from mockData, but
// active/inactive status comes live from the backend.

import { cameras as cameraPositions } from '../data/mockData'

export default function CityMap({
  cameras = [],
  route = [],
  highlightCamera = null,
  showAllNodes = true,
}) {
  const routeNodes = route.map(r => r.node).filter(Boolean)

  return (
    <svg viewBox="0 0 380 360" className="w-full h-full">
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path
            d="M20 0H0V20"
            fill="none"
            stroke="#1A202C"
            strokeWidth="1"
          />
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
      {showAllNodes &&
        cameraPositions.map(position => {
          // Find live backend information for this camera
          const liveCamera = cameras.find(
            cam => cam.camera_id === position.id
          )

          const isActive = liveCamera?.active === true

          const onRoute = routeNodes.some(
            n => n.id === position.id
          )

          const isHighlight = highlightCamera === position.id

          return (
            <g
              key={position.id}
              transform={`translate(${position.x},${position.y})`}
            >
              {/* Highlight */}
              {isHighlight && (
                <circle
                  r="14"
                  fill="#EF4444"
                  opacity="0.18"
                />
              )}

              {/* Active camera glow */}
              {isActive && !isHighlight && (
                <circle
                  r="9"
                  fill="#4ADE80"
                  opacity="0.12"
                  className="live-dot"
                />
              )}

              {/* Camera dot */}
              <circle
                r={onRoute ? 6 : 4.5}
                fill={
                  isHighlight
                    ? '#EF4444'
                    : isActive
                      ? '#4ADE80'
                      : onRoute
                        ? '#4C8DFF'
                        : '#3A4256'
                }
                stroke="#0A0E14"
                strokeWidth="2"
              />

              {/* Camera ID */}
              <text
                x="10"
                y="4"
                className="font-mono"
                fontSize="9"
                fill="#8B93A6"
              >
                {position.id}
              </text>

              {/* Camera location */}
              <text
                x="10"
                y="15"
                fontSize="8"
                fill="#5B6376"
              >
                {liveCamera?.location_name || position.name}
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