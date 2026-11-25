import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  CornerDownLeft,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  Star,
} from 'lucide-react'
import { api } from '../services/api'

const MODULE_COMMANDS = [
  { id: 'mod-macro', label: 'Ambiente de Mercado & Rotação de Capital', group: 'Módulos', tab: 'macro', icon: Activity },
  { id: 'mod-scanner', label: 'Scanner Automático Minervini (SEPA + VCP)', group: 'Módulos', tab: 'scanner', icon: Radar },
  { id: 'mod-xray', label: 'Raio-X Instantâneo de Ativo', group: 'Módulos', tab: 'xray', icon: BarChart3 },
  { id: 'mod-vision', label: 'Analisador de Prints de Gráficos (Visão IA)', group: 'Módulos', tab: 'vision', icon: Camera },
  { id: 'mod-risk', label: 'Gestão de Risco 6% & Paper Trading + Diário', group: 'Módulos', tab: 'risk', icon: ShieldCheck },
  { id: 'mod-settings', label: 'Definições (IA Gemini/Ollama, Capital, Pacotes & Cache)', group: 'Módulos', tab: 'settings', icon: Settings },
  { id: 'act-alerts', label: 'Abrir Central de Alertas (Telegram / Discord / Preço)', group: 'Ações', action: 'alerts', icon: Bell },
]

export function CommandPalette({ open, onClose, onSelectTab, onOpenXRay, onOpenAlerts, favorites = [] }) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [tickers, setTickers] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setSelectedIdx(0)
    setTimeout(() => inputRef.current?.focus(), 20)
    api
      .getWatchlist()
      .then((res) => setTickers(res.items || []))
      .catch(() => {})
  }, [open])

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    const modHits = MODULE_COMMANDS.filter(
      (c) => !q || c.label.toLowerCase().includes(q) || c.group.toLowerCase().includes(q),
    )

    const favSet = new Set((favorites || []).map((t) => t.toUpperCase()))
    const favHits = (favorites || [])
      .filter((t) => !q || t.toLowerCase().includes(q))
      .slice(0, 6)
      .map((t) => ({
        id: `fav-${t}`,
        label: `★ ${t}`,
        sub: 'Favorito Pessoal • Abrir Raio-X',
        group: 'Favoritos',
        ticker: t,
        icon: Star,
      }))

    const tickerHits = tickers
      .filter((t) => !favSet.has(t.ticker.toUpperCase()) && (!q || t.ticker.toLowerCase().includes(q)))
      .slice(0, q ? 10 : 6)
      .map((t) => ({
        id: `tk-${t.ticker}`,
        label: t.ticker,
        sub: t.asset_type === 'crypto' ? 'Cripto • Abrir Raio-X' : 'Ação • Abrir Raio-X',
        group: 'Ativos',
        ticker: t.ticker,
        icon: BarChart3,
      }))

    const list = [...favHits, ...modHits, ...tickerHits]
    if (q && !tickerHits.some((x) => x.ticker.toLowerCase() === q) && !favHits.some((x) => x.ticker.toLowerCase() === q)) {
      list.unshift({
        id: `custom-${q}`,
        label: `Abrir Raio-X de "${query.trim().toUpperCase()}"`,
        sub: 'Pesquisa direta (qualquer ação, ETF ou cripto)',
        group: 'Pesquisa Direta',
        ticker: query.trim().toUpperCase(),
        icon: Search,
      })
    }
    return list
  }, [query, tickers, favorites])

  useEffect(() => {
    setSelectedIdx(0)
  }, [query])

  if (!open) return null

  const execute = (item) => {
    if (!item) return
    if (item.tab) onSelectTab(item.tab)
    else if (item.ticker) onOpenXRay(item.ticker)
    else if (item.action === 'alerts') onOpenAlerts()
    onClose()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx((prev) => Math.min(prev + 1, Math.max(results.length - 1, 0)))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx((prev) => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      execute(results[selectedIdx])
    }
  }

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl rounded-2xl border border-cyan-500/40 bg-[#0a1120] shadow-2xl overflow-hidden"
      >
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-terminal-border">
          <Search className="w-4 h-4 text-cyan-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Saltar para ticker (NVDA, BTC-USD, SPOT...) ou módulo..."
            className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none font-mono"
          />
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-terminal-card border border-terminal-border text-slate-400">
            ESC
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {results.map((item, idx) => {
            const Icon = item.icon
            const active = idx === selectedIdx
            return (
              <button
                key={item.id}
                onClick={() => execute(item)}
                onMouseEnter={() => setSelectedIdx(idx)}
                className={`w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-left transition ${
                  active ? 'bg-cyan-500/20 text-white border border-cyan-500/40' : 'text-slate-300 hover:bg-terminal-hover border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-cyan-300' : 'text-slate-500'}`} />
                  <div className="truncate">
                    <div className="text-xs font-semibold truncate">{item.label}</div>
                    {item.sub && <div className="text-[10px] text-slate-400 truncate">{item.sub}</div>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] font-mono text-slate-500">{item.group}</span>
                  {active && <CornerDownLeft className="w-3.5 h-3.5 text-cyan-300" />}
                </div>
              </button>
            )
          })}
        </div>

        <div className="px-4 py-2 border-t border-terminal-border bg-[#070b14] text-[10px] font-mono text-slate-500 flex items-center justify-between">
          <span>↑↓ Navegar • Enter Abrir</span>
          <span>Atalho global: Ctrl+K</span>
        </div>
      </div>
    </div>
  )
}
