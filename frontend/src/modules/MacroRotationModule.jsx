import React, { useEffect, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react'
import { api, formatPct, formatPrice, formatTimestamp } from '../services/api'
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
      <polyline
        fill="none"
        stroke={positive ? '#10b981' : '#ef4444'}
        strokeWidth="1.8"
        points={pts}
      />
    </svg>
  )
}

export function MacroRotationModule({ onOpenXRay }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
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
        <p className="text-sm text-slate-300">A carregar índices macro e rotação setorial (SPY, QQQ, BTC, VIX, TNX, DXY + ETFs)...</p>
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
  const rotation = marketView === 'us' ? data?.us_rotation : data?.crypto_rotation
  const retField = tf === '1w' ? 'return_1w' : tf === '3m' ? 'return_3m' : 'return_1m'
  const rsField = tf === '1w' ? 'rs_1w' : tf === '3m' ? 'rs_3m' : 'rs_1m'

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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white">Ambiente de Mercado & Rotação de Capital</h2>
          <p className="text-xs text-slate-400">
            Semáforo macro de exposição + mapa de fluxo de capital ("Onde está o dinheiro?") • Atualizado: {formatTimestamp(data?.updated_at)}
          </p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-200 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-cyan-400' : ''}`} />
          Atualizar Dados
        </button>
      </div>

      <WarningBanner warnings={data?.warnings} />

      {/* Semáforo Macro */}
      <section className={`rounded-xl border ${theme.border} bg-gradient-to-r ${theme.bg} p-5`}>
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          {/* Traffic Light Widget */}
          <div className="flex md:flex-col items-center gap-2.5 bg-[#070b14] border border-terminal-border rounded-2xl p-3 shrink-0 self-start">
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'green'
                  ? 'bg-emerald-400 border-emerald-300 shadow-[0_0_18px_rgba(16,185,129,0.8)]'
                  : 'bg-emerald-950/50 border-emerald-900/50'
              }`}
              title="Risk-On"
            />
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'yellow'
                  ? 'bg-amber-400 border-amber-300 shadow-[0_0_18px_rgba(245,158,11,0.8)]'
                  : 'bg-amber-950/50 border-amber-900/50'
              }`}
              title="Cautela / Neutro"
            />
            <div
              className={`w-7 h-7 rounded-full border transition ${
                macro?.color === 'red'
                  ? 'bg-rose-500 border-rose-300 shadow-[0_0_18px_rgba(239,68,68,0.8)]'
                  : 'bg-rose-950/50 border-rose-900/50'
              }`}
              title="Risk-Off"
            />
          </div>

          <div className="flex-1 space-y-2.5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs uppercase tracking-wider font-mono text-slate-400">Semáforo Macro</span>
              <StatusBadge variant={macro?.color}>{macro?.regime?.replace('_', '-')}</StatusBadge>
              <span className="text-xs font-mono text-slate-300">
                Score Macro: <strong className={theme.text}>{macro?.score}/100</strong>
              </span>
            </div>
            <h3 className={`text-2xl font-bold ${theme.text}`}>{macro?.label}</h3>
            <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">{macro?.guidance}</p>

            {/* Factor breakdown pills */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2 pt-2">
              {(macro?.factors || []).map((f, idx) => (
                <div key={idx} className="bg-[#090f1d]/90 border border-terminal-border rounded-lg px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="font-semibold text-slate-200">{f.name}</span>
                    <StatusBadge
                      variant={f.status === 'positivo' ? 'green' : f.status === 'negativo' ? 'red' : 'yellow'}
                    >
                      {f.points} pts
                    </StatusBadge>
                  </div>
                  <p className="text-[11px] text-slate-400">{f.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

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
                clickable ? 'cursor-pointer hover:border-cyan-500/50 transition' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-1">
                <div>
                  <div className="text-[11px] text-slate-400">{b.label}</div>
                  <div className="font-mono font-bold text-sm text-slate-100">{b.ticker}</div>
                </div>
                <span
                  className={`font-mono text-xs font-semibold ${
                    isPositive ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
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

      {/* Mapa de Rotação Setorial */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white">Mapa de Rotação Setorial — Onde está o dinheiro?</h3>
            <p className="text-xs text-slate-400">
              Performance e Força Relativa (RS) face a{' '}
              <span className="font-mono text-cyan-300">{rotation?.benchmark}</span> (
              1S: {formatPct(rotation?.benchmark_returns?.['1w'])} | 1M:{' '}
              {formatPct(rotation?.benchmark_returns?.['1m'])} | 3M:{' '}
              {formatPct(rotation?.benchmark_returns?.['3m'])})
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg bg-terminal-panel border border-terminal-border p-0.5 text-xs">
              <button
                onClick={() => setMarketView('us')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  marketView === 'us' ? 'bg-cyan-500/20 text-cyan-300' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                11 Setores EUA (ETFs)
              </button>
              <button
                onClick={() => setMarketView('crypto')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  marketView === 'crypto' ? 'bg-cyan-500/20 text-cyan-300' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Setores Cripto
              </button>
            </div>

            <div className="inline-flex rounded-lg bg-terminal-panel border border-terminal-border p-0.5 text-xs font-mono">
              {[
                { k: '1w', l: '1S' },
                { k: '1m', l: '1M' },
                { k: '3m', l: '3M' },
              ].map((t) => (
                <button
                  key={t.k}
                  onClick={() => setTf(t.k)}
                  className={`px-2.5 py-1 rounded-md transition ${
                    tf === t.k ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {t.l}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Two Visual Lists: Inflow Leaders vs Outflow Laggards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Leaders */}
          <div className="terminal-card p-4 border-emerald-500/30">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-400">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-emerald-400">Onde o capital está a entrar (Líderes)</h4>
                  <p className="text-[11px] text-slate-400">Maior Força Relativa (RS) e momentum institucional</p>
                </div>
              </div>
              <StatusBadge variant="green">INFLOW</StatusBadge>
            </div>
            <div className="space-y-2.5">
              {(rotation?.leaders || []).map((s) => {
                const rsVal = s[rsField] ?? s.composite_rs
                const retVal = s[retField]
                return (
                  <div
                    key={s.ticker || s.id}
                    onClick={() => s.ticker && onOpenXRay(s.ticker)}
                    className={`rounded-lg bg-emerald-500/5 border border-emerald-500/20 px-3.5 py-2.5 flex items-center justify-between gap-3 ${
                      s.ticker ? 'cursor-pointer hover:border-emerald-400/50 transition' : ''
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">{s.ticker || s.id}</span>
                        <span className="text-xs text-slate-300 font-medium">{s.name}</span>
                      </div>
                      {s.members && (
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">{s.members.join(' • ')}</div>
                      )}
                    </div>
                    <div className="text-right font-mono">
                      <div className="text-xs font-bold text-emerald-400 inline-flex items-center gap-0.5">
                        <ArrowUpRight className="w-3.5 h-3.5" />
                        RS {formatPct(rsVal)}
                      </div>
                      <div className="text-[11px] text-slate-400">Perf {tf.toUpperCase()}: {formatPct(retVal)}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Laggards */}
          <div className="terminal-card p-4 border-rose-500/30">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-rose-500/15 text-rose-400">
                  <TrendingDown className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-rose-400">De onde o capital está a sair (Atrasados)</h4>
                  <p className="text-[11px] text-slate-400">Menor Força Relativa — evitar breakouts contra a corrente</p>
                </div>
              </div>
              <StatusBadge variant="red">OUTFLOW</StatusBadge>
            </div>
            <div className="space-y-2.5">
              {(rotation?.laggards || []).map((s) => {
                const rsVal = s[rsField] ?? s.composite_rs
                const retVal = s[retField]
                return (
                  <div
                    key={s.ticker || s.id}
                    onClick={() => s.ticker && onOpenXRay(s.ticker)}
                    className={`rounded-lg bg-rose-500/5 border border-rose-500/20 px-3.5 py-2.5 flex items-center justify-between gap-3 ${
                      s.ticker ? 'cursor-pointer hover:border-rose-400/50 transition' : ''
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sm text-white">{s.ticker || s.id}</span>
                        <span className="text-xs text-slate-300 font-medium">{s.name}</span>
                      </div>
                      {s.members && (
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">{s.members.join(' • ')}</div>
                      )}
                    </div>
                    <div className="text-right font-mono">
                      <div className="text-xs font-bold text-rose-400 inline-flex items-center gap-0.5">
                        <ArrowDownRight className="w-3.5 h-3.5" />
                        RS {formatPct(rsVal)}
                      </div>
                      <div className="text-[11px] text-slate-400">Perf {tf.toUpperCase()}: {formatPct(retVal)}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Full Rotation Table */}
        <div className="terminal-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-terminal-card/70 text-[11px] uppercase font-mono text-slate-400 border-b border-terminal-border">
                <tr>
                  <th className="px-4 py-3">Setor</th>
                  <th className="px-3 py-3 text-right">1 Semana</th>
                  <th className="px-3 py-3 text-right">1 Mês</th>
                  <th className="px-3 py-3 text-right">3 Meses</th>
                  <th className="px-3 py-3 text-right">RS 1S</th>
                  <th className="px-3 py-3 text-right">RS 1M</th>
                  <th className="px-3 py-3 text-right">RS 3M</th>
                  <th className="px-4 py-3 text-right">Fluxo Composto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border/60 font-mono tabular-nums">
                {(rotation?.sectors || []).map((s) => (
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
                        variant={
                          s.flow_direction === 'INFLOW' ? 'green' : s.flow_direction === 'OUTFLOW' ? 'red' : 'slate'
                        }
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
    </div>
  )
}
