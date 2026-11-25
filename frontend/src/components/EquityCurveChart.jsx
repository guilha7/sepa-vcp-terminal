import React from 'react'

export function EquityCurveChart({ points = [] }) {
  if (!points || points.length < 2) {
    return (
      <div className="h-44 flex items-center justify-center text-xs text-slate-500 border border-dashed border-terminal-border rounded-lg">
        Abre ou fecha trades no simulador para visualizar a curva de capital (Equity Curve).
      </div>
    )
  }

  const values = points.map((p) => Number(p.equity || 0))
  const minVal = Math.min(...values)
  const maxVal = Math.max(...values)
  const pad = Math.max((maxVal - minVal) * 0.15, 2)
  const low = minVal - pad
  const high = maxVal + pad
  const span = high - low || 1

  const W = 600
  const H = 160
  const coords = points.map((p, idx) => {
    const x = (idx / (points.length - 1)) * (W - 36) + 18
    const y = H - 22 - ((Number(p.equity) - low) / span) * (H - 36)
    return { x, y, ...p }
  })

  const pathD = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(' ')
  const areaD = `${pathD} L ${coords[coords.length - 1].x.toFixed(1)} ${H - 18} L ${coords[0].x.toFixed(1)} ${H - 18} Z`
  const isUp = values[values.length - 1] >= values[0]
  const strokeColor = isUp ? '#10b981' : '#ef4444'

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-44">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity="0.32" />
            <stop offset="100%" stopColor={strokeColor} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#eqGrad)" />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinejoin="round" />
        {coords.map((c, idx) => (
          <g key={idx}>
            <circle cx={c.x} cy={c.y} r="3.5" fill={strokeColor} />
            <title>{`${c.label}: ${Number(c.equity).toFixed(2)}€`}</title>
          </g>
        ))}
        <text x="18" y="14" fill="#94a3b8" fontSize="10" fontFamily="JetBrains Mono">
          Máx: {maxVal.toFixed(2)}€
        </text>
        <text x="18" y={H - 4} fill="#94a3b8" fontSize="10" fontFamily="JetBrains Mono">
          Mín: {minVal.toFixed(2)}€
        </text>
        <text x={W - 18} y="14" textAnchor="end" fill={strokeColor} fontSize="11" fontWeight="600" fontFamily="JetBrains Mono">
          Atual: {values[values.length - 1].toFixed(2)}€
        </text>
      </svg>
    </div>
  )
}
