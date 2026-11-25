import React, { useEffect, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Flame,
  Gauge,
  Layers,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import { api, formatCompactNumber, formatPct, formatPrice, formatTimestamp } from '../services/api'
import { StatusBadge } from '../components/StatusBadge'
import { WarningBanner } from '../components/WarningBanner'

function MiniSparkline({ data = [], positive = true }) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 90
      const y = 24 - ((v - min) / span) * 20
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg width="90" height="28" className="overflow-visible">
      <polyline fill="none" stroke={positive ? '#10b981' : '#ef4444'} strokeWidth="1.8" points={pts} />
    </svg>
  )
}

export function MacroRotationModule({ onOpenXRay }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [sectionTab, setSectionTab] = useState('pulse') // pulse | rotation | crypto_derivs
  const [marketView, setMarketView] = useState('us') // us | crypto
  const [tf, setTf] = useState('1m') // 1w | 1m | 3m

  const load = async (force = false) => {
    try {
      if (force) setRefreshing(true)
      else setLoading(true)
      setError(null)
      const res = await api.getMacroOverview(force)
      setData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load(false)
  }, [])

  if (loading && !data) {
    return (
      <div className="terminal-card p-10 text-center space-y-3">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-slate-300">
          A carregar Semáforo Macro, IBD Distribution Days, Stockbee Breadth, Rotação Setorial e Derivados Cripto...
        </p>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="terminal-card p-6 border-rose-500/40 text-rose-300 space-y-3">
        <p className="font-semibold">Erro ao carregar ambiente macro: {error}</p>
        <button onClick={() => load(true)} className="px-3 py-1.5 text-xs bg-rose-500/20 rounded-lg border border-rose-500/40">
          Tentar novamente
        </button>
      </div>
    )
  }

  const macro = data?.macro_traffic_light
  const ibd = data?.ibd_timing
  const breadth = data?.market_breadth
  const cryptoDerivs = data?.crypto_derivatives
  const rotation = marketView === 'us' ? data?.us_rotation : data?.crypto_rotation
  const retField = tf === '1w' ? 'return_1w' : tf === '3m' ? 'return_3m' : 'return_1m'
  const rsField = tf === '1w' ? 'rs_1w' : tf === '3m' ? 'rs_3m' : tf === 'comp' ? 'composite_rs' : 'rs_1m'
  const tfLabel = tf === '1w' ? '1S' : tf === '3m' ? '3M' : tf === 'comp' ? 'Composto' : '1M'

  // Dynamically re-sort ALL sectors whenever user switches 1S / 1M / 3M / Composto
  const sortedSectors = [...(rotation?.sectors || [])].sort(
    (a, b) => (Number(b[rsField] ?? b.composite_rs ?? -999) - Number(a[rsField] ?? a.composite_rs ?? -999)),
  )
  const topCount = marketView === 'us' ? 4 : 3
  const dynamicLeaders = sortedSectors.slice(0, topCount)
  const dynamicLaggards = [...sortedSectors].reverse().slice(0, topCount)

  const lightColors = {
    green: {
      border: 'border-emerald-500/40',
      bg: 'from-emerald-500/15 via-terminal-panel to-terminal-panel',
      text: 'text-emerald-400',
    },
    yellow: {
      border: 'border-amber-500/40',
      bg: 'from-amber-500/15 via-terminal-panel to-terminal-panel',
      text: 'text-amber-400',
    },
    red: {
      border: 'border-rose-500/40',
      bg: 'from-rose-500/15 via-terminal-panel to-terminal-panel',
      text: 'text-rose-400',
    },
  }
  const theme = lightColors[macro?.color] || lightColors.yellow

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="heading-hero">Passo 1 • Ambiente de Mercado &amp; Fluxo de Capital</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Primeiro vê se o mercado está favorável (Semáforo + IBD + Breadth) e depois descobre onde o dinheiro está a entrar • Atualizado: {formatTimestamp(data?.updated_at)}
          </p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-terminal-panel border border-terminal-border hover:border-cyan-400/50 text-slate-200 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
          Atualizar Dados
        </button>
      </div>

      <WarningBanner warnings={data?.warnings} />

      {/* Hero Semáforo Macro (Always Visible at Top) */}
      <section className={`rounded-2xl border ${theme.border} bg-gradient-to-r ${theme.bg} p-5 shadow-lg`}>
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex md:flex-col items-center gap-2.5 bg-[#060a13] border border-terminal-border rounded-2xl p-3 shrink-0 self-start">
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'green'
                  ? 'bg-emerald-400 border-emerald-300 shadow-[0_0_18px_rgba(16,185,129,0.85)]'
                  : 'bg-emerald-950/50 border-emerald-900/50'
              }`}
              title="Risk-On"
            />
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'yellow'
                  ? 'bg-amber-400 border-amber-300 shadow-[0_0_18px_rgba(245,158,11,0.85)]'
                  : 'bg-amber-950/50 border-amber-900/50'
              }`}
              title="Cautela / Neutro"
            />
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'red'
                  ? 'bg-rose-500 border-rose-300 shadow-[0_0_18px_rgba(239,68,68,0.85)]'
                  : 'bg-rose-950/50 border-rose-950/50'
              }`}
              title="Risk-Off"
            />
          </div>

          <div className="flex-1 space-y-2.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-[11px] uppercase tracking-widest font-mono text-slate-400">Semáforo Macro</span>
              <StatusBadge variant={macro?.color}>{macro?.regime?.replace('_', '-')}</StatusBadge>
              <span className="text-xs font-mono text-slate-300">
                Score: <strong className={theme.text}>{macro?.score}/100</strong>
              </span>
              {ibd?.any_ftd && (
                <StatusBadge variant="green">🚀 FOLLOW-THROUGH DAY ATIVO</StatusBadge>
              )}
              {ibd && (
                <StatusBadge variant={ibd.max_distribution_days >= 5 ? 'red' : ibd.max_distribution_days >= 3 ? 'yellow' : 'slate'}>
                  IBD Dist: SPY {ibd.spy?.distribution_days ?? 0} • QQQ {ibd.qqq?.distribution_days ?? 0}
                </StatusBadge>
              )}
              {breadth && (
                <StatusBadge variant={breadth.pct_above_sma50 >= 55 ? 'green' : breadth.pct_above_sma50 <= 35 ? 'red' : 'yellow'}>
                  Breadth: {breadth.pct_above_sma50}% &gt; SMA50
                </StatusBadge>
              )}
            </div>
            <h3 className={`font-display text-2xl font-bold ${theme.text}`}>{macro?.label}</h3>
            <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">{macro?.guidance}</p>
          </div>
        </div>
      </section>

      {/* Clean 3-Tab Sub-Navigation (Zero Clutter!) */}
      <div className="flex flex-wrap items-center gap-2 border-b border-terminal-border pb-3">
        {[
          { id: 'pulse', label: '1. Pulso Macro, IBD & Breadth', icon: Gauge },
          { id: 'rotation', label: '2. Onde Está o Dinheiro? (Rotação Setorial)', icon: Layers },
          { id: 'crypto_derivs', label: '3. Derivados Cripto & Altseason (Binance 0€)', icon: Flame },
        ].map((t) => {
          const Icon = t.icon
          const active = sectionTab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setSectionTab(t.id)}
              className={`inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl border transition ${
                active
                  ? 'bg-cyan-500/20 border-cyan-400/50 text-white shadow-sm'
                  : 'bg-terminal-panel border-terminal-border text-slate-400 hover:text-slate-200 hover:border-slate-600'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${active ? 'text-cyan-300' : 'text-slate-500'}`} />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* TAB 1: Macro Benchmarks + IBD Market Timing + Stockbee Breadth */}
      {sectionTab === 'pulse' && (
        <div className="space-y-5">
          {/* 6 Macro Indicators Cards */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
            {(macro?.benchmarks || []).map((b) => {
              const isPositive = (b.daily_change_pct || 0) >= 0
              const clickable = ['SPY', 'QQQ', 'BTC-USD'].includes(b.ticker)
              return (
                <div
                  key={b.ticker}
                  onClick={() => clickable && onOpenXRay(b.ticker)}
                  className={`terminal-card p-3.5 flex flex-col justify-between gap-2 ${
                    clickable ? 'cursor-pointer hover:border-cyan-400/60 transition' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div>
                      <div className="text-[11px] text-slate-400">{b.label}</div>
                      <div className="font-mono font-bold text-sm text-slate-100">{b.ticker}</div>
                    </div>
                    <span className={`font-mono text-xs font-semibold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {formatPct(b.daily_change_pct)}
                    </span>
                  </div>

                  <div className="flex items-end justify-between">
                    <div className="font-mono text-lg font-bold text-white tabular-nums">
                      {formatPrice(b.price)}
                      {b.ticker === '^TNX' ? '%' : ''}
                    </div>
                    <MiniSparkline data={b.sparkline} positive={(b.return_1m || 0) >= 0} />
                  </div>

                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 border-t border-terminal-border/70 pt-2">
                    <span>
                      50D:{' '}
                      <strong className={b.above_sma50 ? 'text-emerald-400' : 'text-rose-400'}>
                        {b.above_sma50 === null ? '—' : b.above_sma50 ? 'ACIMA' : 'ABAIXO'}
                      </strong>
                    </span>
                    <span>
                      200D:{' '}
                      <strong className={b.above_sma200 ? 'text-emerald-400' : 'text-rose-400'}>
                        {b.above_sma200 === null ? '—' : b.above_sma200 ? 'ACIMA' : 'ABAIXO'}
                      </strong>
                    </span>
                  </div>
                </div>
              )
            })}
          </section>

          {/* Institutional Timing Grid: IBD Distribution/FTD + Stockbee Breadth */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* IBD Market Timing (William O'Neil) */}
            <div className="terminal-card p-5 space-y-3.5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    Market Timing Institucional (William O&apos;Neil / IBD)
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Dias de Distribuição (vendas institucionais em 25 pregões) + Follow-Through Day (confirmação de fundo).
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[ibd?.spy, ibd?.qqq].filter(Boolean).map((idxItem) => (
                  <div key={idxItem.ticker} className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white text-sm">{idxItem.ticker}</span>
                      <StatusBadge
                        variant={
                          idxItem.distribution_days >= 5
                            ? 'red'
                            : idxItem.distribution_days >= 3
                              ? 'yellow'
                              : 'green'
                        }
                      >
                        {idxItem.distribution_days} Dist. Days
                      </StatusBadge>
                    </div>
                    <div className="text-xs font-medium text-slate-200">{idxItem.label}</div>
                    <div className="text-[11px] text-slate-400">
                      Follow-Through Day:{' '}
                      <strong className={idxItem.follow_through_day ? 'text-emerald-400' : 'text-slate-500'}>
                        {idxItem.follow_through_day ? `SIM (${idxItem.ftd_date})` : 'Não recente'}
                      </strong>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 bg-[#080e1c] border border-terminal-border rounded-lg px-3 py-2">
                💡 <strong>Como ler:</strong> 0–3 dias de distribuição = saudável; 4–5 dias = mercado sob pressão; ≥ 6 dias = risco elevado de correção (reduzir posições).
              </p>
            </div>

            {/* Stockbee Market Breadth */}
            <div className="terminal-card p-5 space-y-3.5">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-emerald-400" />
                    Largura de Mercado — Stockbee Market Monitor
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Mede a saúde interna em {breadth?.universe_size ?? 0} ações/ETFs para saber se os breakouts estão a funcionar.
                  </p>
                </div>
                <StatusBadge
                  variant={
                    breadth?.state === 'AGRESSIVO_LONG'
                      ? 'green'
                      : breadth?.state === 'DEFENSIVO_CAIXA'
                        ? 'red'
                        : 'yellow'
                  }
                >
                  {breadth?.label}
                </StatusBadge>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                  <div className="text-[10px] font-sans text-slate-400">% &gt; SMA 50</div>
                  <div className="text-lg font-bold text-cyan-300 mt-0.5">{breadth?.pct_above_sma50 ?? 0}%</div>
                </div>
                <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                  <div className="text-[10px] font-sans text-slate-400">% &gt; SMA 200</div>
                  <div className="text-lg font-bold text-purple-300 mt-0.5">{breadth?.pct_above_sma200 ?? 0}%</div>
                </div>
                <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                  <div className="text-[10px] font-sans text-slate-400">4% Up / Down (Hoje)</div>
                  <div className="text-base font-bold mt-0.5">
                    <span className="text-emerald-400">{breadth?.up_4pct_today ?? 0}</span>
                    <span className="text-slate-500"> / </span>
                    <span className="text-rose-400">{breadth?.down_4pct_today ?? 0}</span>
                  </div>
                </div>
                <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                  <div className="text-[10px] font-sans text-slate-400">Rácio 4% (5 Dias)</div>
                  <div
                    className={`text-lg font-bold mt-0.5 ${
                      (breadth?.ratio_5d || 0) >= 1.3
                        ? 'text-emerald-400'
                        : (breadth?.ratio_5d || 0) < 0.7
                          ? 'text-rose-400'
                          : 'text-amber-300'
                    }`}
                  >
                    {breadth?.ratio_5d ?? 0}x
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-300 bg-[#080e1c] border border-terminal-border rounded-lg px-3 py-2">
                💡 {breadth?.guidance}
              </p>
            </div>
          </div>

          {/* Factor Breakdown */}
          <div className="terminal-card p-4">
            <div className="text-xs font-bold text-slate-300 mb-2.5">Detalhe dos 6 Fatores do Semáforo Macro</div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2.5">
              {(macro?.factors || []).map((f, idx) => (
                <div key={idx} className="bg-[#080e1c] border border-terminal-border rounded-xl px-3.5 py-2.5 text-xs">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="font-semibold text-slate-200">{f.name}</span>
                    <StatusBadge variant={f.status === 'positivo' ? 'green' : f.status === 'negativo' ? 'red' : 'yellow'}>
                      {f.points} pts
                    </StatusBadge>
                  </div>
                  <p className="text-[11px] text-slate-400">{f.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Sector Rotation */}
      {sectionTab === 'rotation' && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold text-white">Mapa de Rotação Setorial — Onde está o dinheiro?</h3>
              <p className="text-xs text-slate-400">
                Performance e Força Relativa (RS) face a <span className="font-mono text-cyan-300">{rotation?.benchmark}</span> (
                1S: {formatPct(rotation?.benchmark_returns?.['1w'])} | 1M: {formatPct(rotation?.benchmark_returns?.['1m'])} | 3M:{' '}
                {formatPct(rotation?.benchmark_returns?.['3m'])})
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-xl bg-terminal-panel border border-terminal-border p-0.5 text-xs">
                <button
                  onClick={() => setMarketView('us')}
                  className={`px-3 py-1 rounded-lg font-medium transition ${
                    marketView === 'us' ? 'bg-cyan-500/20 text-cyan-200' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  11 Setores EUA (ETFs)
                </button>
                <button
                  onClick={() => setMarketView('crypto')}
                  className={`px-3 py-1 rounded-lg font-medium transition ${
                    marketView === 'crypto' ? 'bg-cyan-500/20 text-cyan-200' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Setores Cripto
                </button>
              </div>

              <div className="inline-flex rounded-xl bg-terminal-panel border border-terminal-border p-0.5 text-xs font-mono">
                {[
                  { k: '1w', l: '1S' },
                  { k: '1m', l: '1M' },
                  { k: '3m', l: '3M' },
                  { k: 'comp', l: 'Composto' },
                ].map((t) => (
                  <button
                    key={t.k}
                    onClick={() => setTf(t.k)}
                    className={`px-2.5 py-1 rounded-lg transition ${
                      tf === t.k ? 'bg-emerald-500/20 text-emerald-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {t.l}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="terminal-card p-4 border-emerald-500/30">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-400">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-emerald-400">Onde o capital está a entrar (Top {topCount} • {tfLabel})</h4>
                    <p className="text-[11px] text-slate-400">Ordenado entre todos os {sortedSectors.length} setores pelo RS de {tfLabel}</p>
                  </div>
                </div>
                <StatusBadge variant="green">INFLOW</StatusBadge>
              </div>
              <div className="space-y-2">
                {dynamicLeaders.map((s) => (
                  <div
                    key={s.ticker || s.id}
                    onClick={() => s.ticker && onOpenXRay(s.ticker)}
                    className={`rounded-xl bg-emerald-500/5 border border-emerald-500/20 px-3.5 py-2.5 flex items-center justify-between gap-3 ${
                      s.ticker ? 'cursor-pointer hover:border-emerald-400/50 transition' : ''
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">{s.ticker || s.id}</span>
                        <span className="text-xs text-slate-300 font-medium">{s.name}</span>
                      </div>
                      {s.members && <div className="text-[10px] font-mono text-slate-500 mt-0.5">{s.members.join(' • ')}</div>}
                    </div>
                    <div className="text-right font-mono">
                      <div className="text-xs font-bold text-emerald-400 inline-flex items-center gap-0.5">
                        <ArrowUpRight className="w-3.5 h-3.5" />
                        RS {formatPct(s[rsField] ?? s.composite_rs)}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {tf === 'comp' ? `Perf 1M: ${formatPct(s.return_1m)}` : `Perf ${tfLabel}: ${formatPct(s[retField])}`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="terminal-card p-4 border-rose-500/30">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-rose-500/15 text-rose-400">
                    <TrendingDown className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-rose-400">De onde o capital está a sair (Piores {topCount} • {tfLabel})</h4>
                    <p className="text-[11px] text-slate-400">Evita comprar breakouts contra a corrente</p>
                  </div>
                </div>
                <StatusBadge variant="red">OUTFLOW</StatusBadge>
              </div>
              <div className="space-y-2">
                {dynamicLaggards.map((s) => (
                  <div
                    key={s.ticker || s.id}
                    onClick={() => s.ticker && onOpenXRay(s.ticker)}
                    className={`rounded-xl bg-rose-500/5 border border-rose-500/20 px-3.5 py-2.5 flex items-center justify-between gap-3 ${
                      s.ticker ? 'cursor-pointer hover:border-rose-400/50 transition' : ''
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">{s.ticker || s.id}</span>
                        <span className="text-xs text-slate-300 font-medium">{s.name}</span>
                      </div>
                      {s.members && <div className="text-[10px] font-mono text-slate-500 mt-0.5">{s.members.join(' • ')}</div>}
                    </div>
                    <div className="text-right font-mono">
                      <div
                        className={`text-xs font-bold inline-flex items-center gap-0.5 ${
                          (s[rsField] ?? s.composite_rs ?? 0) >= 0 ? 'text-amber-300' : 'text-rose-400'
                        }`}
                      >
                        <ArrowDownRight className="w-3.5 h-3.5" />
                        RS {formatPct(s[rsField] ?? s.composite_rs)}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {tf === 'comp' ? `Perf 1M: ${formatPct(s.return_1m)}` : `Perf ${tfLabel}: ${formatPct(s[retField])}`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="terminal-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-terminal-card/70 text-[11px] uppercase font-mono text-slate-400 border-b border-terminal-border">
                  <tr>
                    <th className="px-4 py-3">Setor</th>
                    <th className="px-3 py-3 text-right">1 Semana</th>
                    <th className="px-3 py-3 text-right">1 Mês</th>
                    <th className="px-3 py-3 text-right">3 Meses</th>
                    <th className={`px-3 py-3 text-right ${tf === '1w' ? 'text-emerald-300 font-bold' : ''}`}>
                      RS 1S {tf === '1w' ? '▼' : ''}
                    </th>
                    <th className={`px-3 py-3 text-right ${tf === '1m' ? 'text-emerald-300 font-bold' : ''}`}>
                      RS 1M {tf === '1m' ? '▼' : ''}
                    </th>
                    <th className={`px-3 py-3 text-right ${tf === '3m' ? 'text-emerald-300 font-bold' : ''}`}>
                      RS 3M {tf === '3m' ? '▼' : ''}
                    </th>
                    <th className={`px-4 py-3 text-right ${tf === 'comp' ? 'text-emerald-300 font-bold' : ''}`}>
                      Fluxo Composto {tf === 'comp' ? '▼' : ''}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-terminal-border/60 font-mono tabular-nums">
                  {sortedSectors.map((s) => (
                    <tr
                      key={s.ticker || s.id}
                      onClick={() => s.ticker && onOpenXRay(s.ticker)}
                      className={`hover:bg-terminal-hover/70 transition ${s.ticker ? 'cursor-pointer' : ''}`}
                    >
                      <td className="px-4 py-2.5 font-sans">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-cyan-300">{s.ticker || s.id}</span>
                          <span className="text-slate-200 font-medium">{s.name}</span>
                        </div>
                      </td>
                      {[s.return_1w, s.return_1m, s.return_3m, s.rs_1w, s.rs_1m, s.rs_3m].map((val, idx) => (
                        <td
                          key={idx}
                          className={`px-3 py-2.5 text-right ${
                            val > 0 ? 'text-emerald-400' : val < 0 ? 'text-rose-400' : 'text-slate-400'
                          }`}
                        >
                          {formatPct(val)}
                        </td>
                      ))}
                      <td className="px-4 py-2.5 text-right">
                        <StatusBadge
                          variant={s.flow_direction === 'INFLOW' ? 'green' : s.flow_direction === 'OUTFLOW' ? 'red' : 'slate'}
                        >
                          {formatPct(s.composite_rs)}
                        </StatusBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* TAB 3: Free Crypto Futures Derivatives Radar (Binance Public API) & Altseason Gauge */}
      {sectionTab === 'crypto_derivs' && (
        <section className="space-y-4">
          {/* Altseason Gauge Hero */}
          <div className="terminal-card p-5 border-purple-500/35 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-mono uppercase tracking-wider text-purple-300">Termómetro Altseason</span>
                <StatusBadge
                  variant={
                    cryptoDerivs?.altseason?.regime === 'ALTSEASON'
                      ? 'green'
                      : cryptoDerivs?.altseason?.regime === 'BITCOIN_SEASON'
                        ? 'yellow'
                        : 'cyan'
                  }
                >
                  {cryptoDerivs?.altseason?.regime || 'N/D'}
                </StatusBadge>
              </div>
              <h3 className="text-lg font-bold text-white">{cryptoDerivs?.altseason?.label || 'Indisponível'}</h3>
              <p className="text-xs text-slate-400">
                ETH/BTC: <strong className="font-mono text-white">{cryptoDerivs?.altseason?.eth_btc_ratio ?? '—'}</strong> (
                {cryptoDerivs?.altseason?.eth_btc_above_sma50 ? 'acima da SMA 50 ✓' : 'abaixo da SMA 50'}) •{' '}
                <strong className="font-mono text-cyan-300">{cryptoDerivs?.altseason?.alts_beating_btc_pct ?? '—'}%</strong> das altcoins a bater o BTC nos últimos 30 dias.
              </p>
            </div>
            <div className="w-full md:w-64 space-y-1.5">
              <div className="flex justify-between text-[11px] font-mono">
                <span className="text-amber-300">Bitcoin</span>
                <span className="font-bold text-white">{cryptoDerivs?.altseason?.altseason_index ?? 50}/100</span>
                <span className="text-emerald-400">Altseason</span>
              </div>
              <div className="h-2.5 rounded-full bg-[#060a13] border border-terminal-border overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-400 via-cyan-400 to-emerald-400"
                  style={{ width: `${Math.min(Math.max(cryptoDerivs?.altseason?.altseason_index ?? 50, 4), 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Derivatives Table */}
          <div className="terminal-card overflow-hidden">
            <div className="px-5 py-3.5 border-b border-terminal-border flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-white">Derivados Cripto em Tempo Real — Funding Rate, Open Interest &amp; Baleias</h3>
                <p className="text-[11px] text-slate-400">
                  Fonte: {cryptoDerivs?.source} • Funding muito positivo (&gt; +0.05%) = risco de queda; negativo (&lt; -0.02%) = potencial short squeeze.
                </p>
              </div>
              {typeof cryptoDerivs?.avg_funding_rate_pct === 'number' && (
                <StatusBadge variant="cyan">Funding Médio: {cryptoDerivs.avg_funding_rate_pct >= 0 ? '+' : ''}{cryptoDerivs.avg_funding_rate_pct}%</StatusBadge>
              )}
            </div>

            {!cryptoDerivs?.available ? (
              <div className="p-8 text-center text-xs text-slate-400">
                API pública Binance Futures temporariamente indisponível nesta rede. Os preços Spot continuam ativos normalmente.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-terminal-card/70 text-[11px] uppercase font-mono text-slate-400 border-b border-terminal-border">
                    <tr>
                      <th className="px-4 py-3">Ativo</th>
                      <th className="px-3 py-3 text-right">Funding (8h)</th>
                      <th className="px-3 py-3 text-right">Anualizado</th>
                      <th className="px-3 py-3">Sinal Funding</th>
                      <th className="px-3 py-3 text-right">Open Interest</th>
                      <th className="px-3 py-3 text-right">OI 24h</th>
                      <th className="px-3 py-3">Fluxo OI + Preço</th>
                      <th className="px-4 py-3 text-right">Baleias L/S</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-terminal-border/60 font-mono tabular-nums">
                    {(cryptoDerivs.assets || []).map((a) => (
                      <tr
                        key={a.ticker}
                        onClick={() => onOpenXRay(a.ticker)}
                        className="hover:bg-terminal-hover/70 cursor-pointer transition"
                      >
                        <td className="px-4 py-2.5 font-bold text-white">{a.ticker}</td>
                        <td
                          className={`px-3 py-2.5 text-right font-bold ${
                            a.funding_rate_pct >= 0.05
                              ? 'text-rose-400'
                              : a.funding_rate_pct <= -0.02
                                ? 'text-emerald-400'
                                : 'text-slate-200'
                          }`}
                        >
                          {a.funding_rate_pct >= 0 ? '+' : ''}
                          {a.funding_rate_pct?.toFixed(4)}%
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-400">{a.funding_annualized_pct}%</td>
                        <td className="px-3 py-2.5 font-sans">
                          <StatusBadge
                            variant={
                              a.funding_signal?.code === 'EUFORIA'
                                ? 'red'
                                : a.funding_signal?.code === 'SHORT_SQUEEZE'
                                  ? 'green'
                                  : 'slate'
                            }
                          >
                            {a.funding_signal?.label}
                          </StatusBadge>
                        </td>
                        <td className="px-3 py-2.5 text-right text-slate-200">{formatCompactNumber(a.open_interest_usd)}</td>
                        <td
                          className={`px-3 py-2.5 text-right ${
                            (a.oi_change_24h_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {formatPct(a.oi_change_24h_pct)}
                        </td>
                        <td className="px-3 py-2.5 font-sans">
                          <StatusBadge
                            variant={
                              a.oi_flow?.code === 'DINHEIRO_NOVO_BULL'
                                ? 'green'
                                : a.oi_flow?.code === 'SHORTING_AGRESSIVO'
                                  ? 'red'
                                  : 'slate'
                            }
                          >
                            {a.oi_flow?.label}
                          </StatusBadge>
                        </td>
                        <td className="px-4 py-2.5 text-right text-cyan-300">
                          {a.top_traders_ls_ratio ? `${a.top_traders_ls_ratio} (${a.top_long_pct}%L)` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
