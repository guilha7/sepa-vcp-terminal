import React, { useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  Command,
  Cpu,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'macro', label: 'Macro & Rotação', sub: 'Onde está o dinheiro?', icon: Activity },
  { id: 'scanner', label: 'Scanner SEPA / VCP', sub: 'Split-Screen + Teclado', icon: Radar },
  { id: 'xray', label: 'Raio-X de Ativo', sub: 'Diário/Semanal + RS + IA', icon: BarChart3 },
  { id: 'vision', label: 'Visão IA Gráficos', sub: 'Colar Print (Ctrl+V)', icon: Camera },
  { id: 'risk', label: 'Risco 6% & Paper', sub: 'FX + 2R/BE + Diário', icon: ShieldCheck },
  { id: 'settings', label: 'Definições', sub: 'IA, Capital, Pacotes & Cache', icon: Settings },
]

export function Layout({
  activeTab,
  onSelectTab,
  onQuickSearch,
  onOpenPalette,
  onOpenAlerts,
  health,
  children,
}) {
  const [searchInput, setSearchInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const clean = searchInput.trim().toUpperCase()
    if (!clean) return
    onQuickSearch(clean)
    setSearchInput('')
  }

  const aiLabel =
    health?.ai_provider_active === 'gemini'
      ? 'IA: Gemini Free'
      : health?.ai_provider_active === 'ollama'
        ? 'IA: Ollama Local'
        : 'IA: Fallback Local'

  const unreadAlerts = health?.extra?.unread_alerts || 0

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-terminal-bg text-slate-100">
      {/* Sidebar */}
      <aside className="w-full lg:w-64 shrink-0 border-b lg:border-b-0 lg:border-r border-terminal-border bg-[#090f1d] flex flex-col">
        <div className="px-4 py-4 border-b border-terminal-border flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500/25 to-cyan-500/25 border border-emerald-500/40 flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-100">SEPA/VCP DESK</h1>
            <p className="text-[11px] text-slate-400 font-mono">MINERVINI LOCAL • 0€</p>
          </div>
        </div>

        <nav className="p-2.5 flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible flex-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition shrink-0 lg:shrink ${
                  active
                    ? 'bg-cyan-500/15 border border-cyan-500/40 text-cyan-200 shadow-sm'
                    : 'border border-transparent text-slate-400 hover:bg-terminal-hover hover:text-slate-100'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-cyan-400' : 'text-slate-400'}`} />
                <div>
                  <div className="text-xs font-semibold leading-tight">{item.label}</div>
                  <div className="text-[10px] text-slate-500 hidden lg:block">{item.sub}</div>
                </div>
              </button>
            )
          })}
        </nav>

        <div className="hidden lg:block p-3 border-t border-terminal-border text-[11px] text-slate-400 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${health ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              Backend Local
            </span>
            <span className="font-mono text-slate-300">{health ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              {aiLabel}
            </span>
          </div>
          {health?.watchlist_counts && (
            <div className="text-[10px] text-slate-500 font-mono">
              Universo: {health.watchlist_counts.stocks} Ações • {health.watchlist_counts.crypto} Cripto
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Top Header */}
        <header className="sticky top-0 z-20 border-b border-terminal-border bg-[#070b14]/90 backdrop-blur px-4 lg:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <form onSubmit={handleSubmit} className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Raio-X instantâneo (NVDA, AAPL, SOL-USD, BTC)..."
              className="w-full pl-9 pr-20 py-2 text-xs font-mono bg-terminal-panel border border-terminal-border rounded-lg text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/70"
            />
            <button
              type="submit"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 px-2.5 py-1 text-[11px] font-semibold bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 rounded-md transition"
            >
              Analisar
            </button>
          </form>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="hidden xl:flex items-center gap-1.5 text-[11px]">
              {['NVDA', 'AAPL', 'SPOT', 'BTC-USD', 'SOL-USD'].map((tk) => (
                <button
                  key={tk}
                  onClick={() => onQuickSearch(tk)}
                  className="px-2 py-1 rounded bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 font-mono transition"
                >
                  {tk}
                </button>
              ))}
            </div>

            <button
              onClick={onOpenPalette}
              title="Command Palette (Ctrl+K)"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-300 transition"
            >
              <Command className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline font-mono text-[11px]">Ctrl+K</span>
            </button>

            <button
              onClick={onOpenAlerts}
              title="Central de Alertas (Preço / Telegram / Discord)"
              className="relative inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-200 transition"
            >
              <Bell className="w-4 h-4 text-amber-400" />
              <span className="hidden sm:inline text-[11px]">Alertas</span>
              {unreadAlerts > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-mono font-bold">
                  {unreadAlerts > 99 ? '99+' : unreadAlerts}
                </span>
              )}
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-6 max-w-[1680px] w-full mx-auto">{children}</main>
      </div>
    </div>
  )
}
