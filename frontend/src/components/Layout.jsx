import React, { useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  Camera,
  Command,
  Compass,
  Cpu,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  TrendingUp,
  User,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'macro', step: '01', label: 'Macro & Setores', sub: 'Semáforo e fluxo de capital', icon: Activity },
  { id: 'scanner', step: '02', label: 'Scanner', sub: 'Encontrar setups pela tua estratégia', icon: Radar },
  { id: 'xray', step: '03', label: 'Raio-X', sub: 'Gráfico e análise completa', icon: BarChart3 },
  { id: 'vision', step: '04', label: 'Visão IA', sub: 'Analisar print (Ctrl+V)', icon: Camera },
  { id: 'risk', step: '05', label: 'Risco & Paper', sub: 'Calculadora ≤ 6% e carteira', icon: ShieldCheck },
  { id: 'settings', step: '⚙', label: 'Definições', sub: 'Perfil, favoritos e admin', icon: Settings },
]

export function Layout({
  activeTab,
  onSelectTab,
  onQuickSearch,
  onOpenPalette,
  onOpenAlerts,
  onToggleGuide,
  guideOpen,
  userName,
  onSwitchUser,
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
      {/* Sidebar with clear numbered 01 -> 05 workflow */}
      <aside className="w-full lg:w-[272px] shrink-0 border-b lg:border-b-0 lg:border-r border-terminal-border bg-[#080e1b]/95 flex flex-col">
        <div className="px-4 py-4 border-b border-terminal-border flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/30 via-cyan-500/20 to-blue-500/20 border border-emerald-400/40 flex items-center justify-center shadow-lg">
            <TrendingUp className="w-5 h-5 text-emerald-300" />
          </div>
          <div>
            <h1 className="font-display text-base font-bold tracking-tight bg-gradient-to-r from-white via-cyan-100 to-emerald-300 bg-clip-text text-transparent">
              SEPA / VCP DESK
            </h1>
            <p className="text-[10px] text-slate-400 font-mono tracking-wider">MULTI-ESTRATÉGIA • 0€</p>
          </div>
        </div>

        <div className="hidden lg:block px-4 pt-3 pb-1 text-[10px] font-mono uppercase tracking-widest text-slate-500">
          Roteiro de Análise (1 → 5)
        </div>

        <nav className="p-2.5 flex lg:flex-col gap-1.5 overflow-x-auto lg:overflow-visible flex-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition shrink-0 lg:shrink ${
                  active
                    ? 'bg-gradient-to-r from-cyan-500/20 to-emerald-500/10 border border-cyan-400/45 text-white shadow-sm'
                    : 'border border-transparent text-slate-400 hover:bg-terminal-hover/80 hover:text-slate-100'
                }`}
              >
                <span
                  className={`w-6 h-6 rounded-lg font-mono text-[10px] font-bold flex items-center justify-center shrink-0 border ${
                    active
                      ? 'bg-cyan-400/20 border-cyan-400/50 text-cyan-200'
                      : 'bg-terminal-card border-terminal-border text-slate-400'
                  }`}
                >
                  {item.step}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-display text-[13px] font-semibold leading-tight flex items-center gap-1.5">
                    <Icon className={`w-3.5 h-3.5 shrink-0 ${active ? 'text-cyan-300' : 'text-slate-500'}`} />
                    <span className="truncate">{item.label}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 hidden lg:block truncate mt-0.5">{item.sub}</div>
                </div>
              </button>
            )
          })}
        </nav>

        <div className="hidden lg:block p-3.5 border-t border-terminal-border text-[11px] text-slate-400 space-y-1.5 bg-[#060a14]/70">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${health ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              Estado API
            </span>
            <span className="font-mono text-emerald-300 font-semibold">{health ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              {aiLabel}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Top Header */}
        <header className="sticky top-0 z-20 border-b border-terminal-border bg-[#060a13]/90 backdrop-blur-md px-4 lg:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <form onSubmit={handleSubmit} className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Pesquisar qualquer ticker (NVDA, AAPL, SOL-USD, BTC)..."
              className="w-full pl-9 pr-20 py-2 text-xs font-mono bg-terminal-panel border border-terminal-border rounded-xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-400/70"
            />
            <button
              type="submit"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 px-2.5 py-1 text-[11px] font-semibold bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-500/35 rounded-lg transition"
            >
              Raio-X
            </button>
          </form>

          <div className="flex items-center gap-2 shrink-0">
            <div className="hidden 2xl:flex items-center gap-1.5 text-[11px]">
              {['NVDA', 'AAPL', 'EDP.LS', 'BTC-USD', 'SOL-USD'].map((tk) => (
                <button
                  key={tk}
                  onClick={() => onQuickSearch(tk)}
                  className="px-2 py-1 rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-400/50 text-slate-300 hover:text-cyan-200 font-mono transition"
                >
                  {tk}
                </button>
              ))}
            </div>

            <button
              onClick={onSwitchUser}
              title="Trocar de perfil (Paper Trading & Diário)"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl bg-terminal-panel border border-terminal-border hover:border-emerald-400/50 text-emerald-300 transition"
            >
              <User className="w-3.5 h-3.5" />
              <span className="font-semibold text-[11px] max-w-[90px] truncate">{userName || 'Trader'}</span>
            </button>

            <button
              onClick={onToggleGuide}
              title="Mostrar/ocultar guia de primeiros passos"
              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl border transition ${
                guideOpen
                  ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-200'
                  : 'bg-terminal-panel border-terminal-border hover:border-cyan-400/50 text-slate-300'
              }`}
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline text-[11px] font-medium">Guia</span>
            </button>

            <button
              onClick={onOpenPalette}
              title="Pesquisa Rápida (Ctrl+K)"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl bg-terminal-panel border border-terminal-border hover:border-cyan-400/50 text-slate-300 transition"
            >
              <Command className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline font-mono text-[11px]">Ctrl+K</span>
            </button>

            <button
              onClick={onOpenAlerts}
              title="Central de Alertas (Telegram / Discord / Preço)"
              className="relative inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl bg-terminal-panel border border-terminal-border hover:border-amber-400/50 text-slate-200 transition"
            >
              <Bell className="w-4 h-4 text-amber-400" />
              <span className="hidden sm:inline text-[11px] font-medium">Alertas</span>
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
