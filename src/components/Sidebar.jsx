import { NavLink } from 'react-router-dom'

const items = [
  { to: '/', label: 'Command Center', icon: RadarIcon },
  { to: '/tracking', label: 'Vehicle Tracking', icon: SearchIcon },
  { to: '/analytics', label: 'Analytics', icon: BarsIcon },
  { to: '/alerts', label: 'Alert Center', icon: BellIcon },
]

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-base-500 bg-base-800 flex flex-col">
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-base-500">
        <div className="w-2.5 h-2.5 rounded-full bg-signal-green live-dot" />
        <span className="font-mono text-sm tracking-tight text-ink-100">ATLAS</span>
        <span className="font-mono text-[10px] text-ink-700">v0.1</span>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded text-sm transition-colors ${
                isActive
                  ? 'bg-base-600 text-ink-100'
                  : 'text-ink-500 hover:text-ink-300 hover:bg-base-700'
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-base-500">
        <div className="text-[11px] text-ink-700 leading-relaxed font-mono">
          5 nodes simulated
          <br />
          Chennai grid, prototype build
        </div>
      </div>
    </aside>
  )
}

function RadarIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 3v9l6-3" />
    </svg>
  )
}
function SearchIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
    </svg>
  )
}
function BarsIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <path d="M4 20V10M12 20V4M20 20v-7" />
    </svg>
  )
}
function BellIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" {...props}>
      <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 01-3.4 0" />
    </svg>
  )
}
