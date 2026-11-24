import React from 'react'
import { AlertTriangle } from 'lucide-react'

export function WarningBanner({ warnings = [] }) {
  const clean = (warnings || []).filter(Boolean)
  if (clean.length === 0) return null

  return (
    <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200 flex items-start gap-2.5">
      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
      <div className="space-y-0.5">
        <p className="font-medium text-amber-300">Aviso de fontes de dados (modo tolerante a falhas):</p>
        <ul className="list-disc list-inside text-amber-200/90 space-y-0.5">
          {clean.slice(0, 4).map((w, idx) => (
            <li key={idx}>{w}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
