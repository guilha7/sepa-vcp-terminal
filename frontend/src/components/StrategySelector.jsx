import React from 'react'
import { Compass } from 'lucide-react'
import { STRATEGIES, getStrategyMeta } from '../services/strategies'

const ACTIVE_STYLES = {
  emerald: 'bg-emerald-500/20 border-emerald-400/60 text-emerald-200 shadow-sm',
  cyan: 'bg-cyan-500/20 border-cyan-400/60 text-cyan-200 shadow-sm',
  purple: 'bg-purple-500/20 border-purple-400/60 text-purple-200 shadow-sm',
  amber: 'bg-amber-500/20 border-amber-400/60 text-amber-200 shadow-sm',
}

export function StrategySelector({ activeStrategy = 'minervini', onChange }) {
  const current = getStrategyMeta(activeStrategy)

  return (
    <div className="terminal-card p-3 flex flex-col lg:flex-row lg:items-center justify-between gap-2.5 border-cyan-500/25">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-slate-300 mr-1">
          <Compass className="w-3.5 h-3.5 text-cyan-400" />
          Estratégia:
        </span>
        <div className="inline-flex flex-wrap gap-1.5">
          {STRATEGIES.map((st) => {
            const active = st.id === activeStrategy
            return (
              <button
                key={st.id}
                type="button"
                onClick={() => onChange?.(st.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                  active
                    ? ACTIVE_STYLES[st.color] || ACTIVE_STYLES.emerald
                    : 'bg-[#070b14] border-terminal-border text-slate-400 hover:text-slate-100 hover:border-slate-600'
                }`}
              >
                {st.label}
              </button>
            )
          })}
        </div>
      </div>

      <span className="text-[11px] text-slate-400 lg:text-right">{current.tagline}</span>
    </div>
  )
}
