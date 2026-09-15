export default function StatReadout({ label, value, unit, tone = 'default' }) {
  const toneClass = {
    default: 'text-ink-100',
    green: 'text-signal-green',
    amber: 'text-signal-amber',
    red: 'text-signal-red',
  }[tone]

  return (
    <div className="border border-base-500 bg-base-800 rounded px-5 py-4">
      <div className="text-[11px] uppercase tracking-wider text-ink-700 mb-2">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className={`font-mono text-3xl font-semibold ${toneClass}`}>{value}</span>
        {unit && <span className="text-xs text-ink-500">{unit}</span>}
      </div>
    </div>
  )
}
