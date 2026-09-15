import { cameras } from '../data/mockData'

export default function CityMap({
  route = [],
  highlightCamera = null,
  showAllNodes = false
}) {
  /*
   * Real API gives:
   *
   * {
   *   camera_id: "CAM-01",
   *   timestamp: "...",
   *   location_name: "Main Road"
   * }
   *
   * Camera coordinates still come from mockData.js.
   * We use camera_id to connect the real API route
   * with those coordinates.
   */

  const routeNodes = route
    .map(r => cameras.find(cam => cam.id === r.camera_id))
    .filter(Boolean)

  /*
   * Remove consecutive duplicate cameras.
   *
   * Example:
   * CAM-01 → CAM-03 → CAM-03
   *
   * becomes:
   * CAM-01 → CAM-03
   */
  const uniqueRouteNodes = routeNodes.filter((node, index) => {
    if (index === 0) return true
    return node.id !== routeNodes[index - 1].id
  })

  return (
    <svg
      viewBox="0 0 380 360"
      className="w-full h-full"
    >

      {/* GRID */}
      <defs>
        <pattern
          id="grid"
          width="20"
          height="20"
          patternUnits="userSpaceOnUse"
        >
          <path
            d="M20 0H0V20"
            fill="none"
            stroke="#1A202C"
            strokeWidth="1"
          />
        </pattern>

        {/* Arrow head */}
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path
            d="M 0 0 L 10 5 L 0 10 z"
            fill="#4C8DFF"
          />
        </marker>
      </defs>

      <rect
        width="380"
        height="360"
        fill="url(#grid)"
      />

      {/* ALL CAMERA NODES */}
      {showAllNodes &&
        cameras.map(cam => {
          const onRoute = uniqueRouteNodes.some(
            n => n.id === cam.id
          )

          const isHighlight =
            highlightCamera === cam.id

          return (
            <g
              key={cam.id}
              transform={`translate(${cam.x},${cam.y})`}
            >

              {isHighlight && (
                <circle
                  r="14"
                  fill="#EF4444"
                  opacity="0.18"
                />
              )}

              <circle
                r={onRoute ? 6 : 4.5}
                fill={
                  isHighlight
                    ? '#EF4444'
                    : onRoute
                      ? '#4C8DFF'
                      : '#3A4256'
                }
                stroke="#0A0E14"
                strokeWidth="2"
              />

              <text
                x="10"
                y="4"
                className="font-mono"
                fontSize="9"
                fill="#8B93A6"
              >
                {cam.id}
              </text>

              <text
                x="10"
                y="15"
                fontSize="8"
                fill="#5B6376"
              >
                {cam.name}
              </text>

            </g>
          )
        })}

      {/* ROUTE LINE */}
      {uniqueRouteNodes.length > 1 && (
        <polyline
          points={uniqueRouteNodes
            .map(n => `${n.x},${n.y}`)
            .join(' ')}
          fill="none"
          stroke="#4C8DFF"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          markerEnd="url(#arrow)"
          className="route-flow"
        />
      )}

      {/* ROUTE CAMERA NODES */}
      {uniqueRouteNodes.map((node, index) => {

        const isFirst = index === 0
        const isLast =
          index === uniqueRouteNodes.length - 1

        return (
          <g key={`${node.id}-${index}`}>

            {/* Glow */}
            <circle
              cx={node.x}
              cy={node.y}
              r={isLast ? 12 : 9}
              fill="#4C8DFF"
              opacity="0.12"
            />

            {/* Camera */}
            <circle
              cx={node.x}
              cy={node.y}
              r="6"
              fill={
                highlightCamera === node.id
                  ? '#EF4444'
                  : '#4C8DFF'
              }
              stroke="#0A0E14"
              strokeWidth="2"
            />

            {/* Order number */}
            <circle
              cx={node.x - 10}
              cy={node.y - 10}
              r="8"
              fill="#0A0E14"
              stroke="#4ADE80"
              strokeWidth="1"
            />

            <text
              x={node.x - 10}
              y={node.y - 7}
              textAnchor="middle"
              fontSize="8"
              className="font-mono"
              fill="#4ADE80"
            >
              {index + 1}
            </text>

            {/* Camera ID */}
            <text
              x={node.x + 10}
              y={node.y + 3}
              className="font-mono"
              fontSize="9"
              fill="#8B93A6"
            >
              {node.id}
            </text>

            {/* Camera name */}
            <text
              x={node.x + 10}
              y={node.y + 14}
              fontSize="8"
              fill="#5B6376"
            >
              {node.name}
            </text>

            {/* FIRST / LAST label */}
            {isFirst && (
              <text
                x={node.x + 10}
                y={node.y - 8}
                fontSize="7"
                fill="#4ADE80"
              >
                START
              </text>
            )}

            {isLast && !isFirst && (
              <text
                x={node.x + 10}
                y={node.y - 8}
                fontSize="7"
                fill="#4ADE80"
              >
                CURRENT
              </text>
            )}

          </g>
        )
      })}

    </svg>
  )
}
