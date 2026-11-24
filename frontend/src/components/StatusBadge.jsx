import React from 'react'

const VARIANTS = {
  green: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  yellow: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  red: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  purple: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  slate: 'bg-slate-700/40 text-slate-300 border-slate-600/50',
}

export function StatusBadge({ children, variant = 'slate', className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-md border whitespace-nowrap ${
        VARIANTS[variant] || VARIANTS.slate
      } ${className}`}
    >
      {children}
    </span>
  )
}

export function SetupStatusBadge({ status }) {
  switch (status) {
    case 'BREAKOUT':
      return <StatusBadge variant="green">BREAKOUT VCP</StatusBadge>
    case 'VCP_PRONTO':
      return <StatusBadge variant="cyan">VCP PRONTO (VDU)</StatusBadge>
    case 'VCP_FORMACAO':
      return <StatusBadge variant="purple">VCP EM FORMAÇÃO</StatusBadge>
    case 'STAGE_2':
      return <StatusBadge variant="green">STAGE 2 (8/8)</StatusBadge>
    case 'EM_OBSERVACAO':
      return <StatusBadge variant="yellow">OBSERVAÇÃO</StatusBadge>
    default:
      return <StatusBadge variant="slate">FORA STAGE 2</StatusBadge>
  }
}

export function SentimentBadge({ sentiment }) {
  const code = sentiment?.code || 'neutral'
  const label = sentiment?.label || 'Neutro'
  const score = sentiment?.score
  const variant = code === 'positive' ? 'green' : code === 'negative' ? 'red' : 'slate'
  return (
    <StatusBadge variant={variant}>
      {label}
      {typeof score === 'number' && (
        <span className="font-mono opacity-75">({score >= 0 ? '+' : ''}{score.toFixed(2)})</span>
      )}
    </StatusBadge>
  )
}
