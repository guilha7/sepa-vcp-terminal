import React, { useEffect, useState } from 'react'
import {
  AlertOctagon,
  BarChart3,
  BellPlus,
  CheckCircle2,
  ExternalLink,
  Newspaper,
  RefreshCw,
  Sparkles,
  Star,
  TrendingUp,
  Users,
  XCircle,
  Zap,
} from 'lucide-react'
import { api, formatCompactNumber, formatPct, formatPrice } from '../services/api'
import { CandlestickChart } from '../components/CandlestickChart'
import { SentimentBadge, SetupStatusBadge, StatusBadge } from '../components/StatusBadge'
import { StrategySelector } from '../components/StrategySelector'
import { WarningBanner } from '../components/WarningBanner'

export function XRayModule({
  ticker,
  onChangeTicker,
  onSimulateTrade,
  onCreateAlert,
  favorites = [],
  onToggleFavorite,
  activeStrategy = 'minervini',
  onChangeStrategy,
  isAdmin = true,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [inputVal, setInputVal] = useState(ticker || 'NVDA')
  const [detailTab, setDetailTab] = useState('ai_news') // ai_news | fundamentals | backtest

  const loadXRay = async (tk, force = false) => {
    try {
      setLoading(true)
      setError(null)
      const res = await api.getXRay(tk, force)
      setData(res)
    } catch (err) {
      setError(err.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const active = ticker || 'NVDA'
    setInputVal(active)
    loadXRay(active, false)
  }, [ticker])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputVal.trim()) return
    onChangeTicker(inputVal.trim().toUpperCase())
  }

  if (loading && !data) {
    return (
      <div className="terminal-card p-10 text-center space-y-3">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-slate-200">
          A carregar Raio-X de <span className="font-mono font-bold text-cyan-300">{ticker}</span>...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="terminal-card p-6 border-rose-500/40 text-rose-300 space-y-4">
        <div>
          <p className="font-semibold">Não foi possível carregar o Raio-X de &quot;{ticker}&quot;: {error}</p>
          <p className="text-xs text-slate-400 mt-1">
            Verifica o ticker (ex.: EUA `NVDA`, Portugal `EDP.LS`, Europa `SAP.DE`, Cripto `BTC-USD`).
          </p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Escreve outro ticker..."
            className="w-48 px-3 py-2 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white focus:outline-none focus:border-cyan-400"
          />
          <button
            type="submit"
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200"
          >
            Pesquisar
          </button>
          {['NVDA', 'EDP.LS', 'BTC-USD'].map((tk) => (
            <button
              key={tk}
              type="button"
              onClick={() => onChangeTicker(tk)}
              className="px-2.5 py-1.5 text-xs font-mono rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/50 text-slate-300"
            >
              {tk}
            </button>
          ))}
        </form>
      </div>
    )
  }

  const sepa = data?.sepa || {}
  const tt = sepa.trend_template || {}
  const vcp = sepa.vcp || {}
  const plan = sepa.trade_plan || {}
  const q = sepa.quant || {}
  const fund = data?.fundamentals || {}
  const news = data?.news || {}
  const sentSummary = news.sentiment_summary || {}
  const briefing = data?.briefing || {}
  const volQ = data?.volume_quality || {}
  const inst = data?.institutional || {}
  const bt = data?.personality_backtest || {}

  const isFav = favorites.includes((data.ticker || '').toUpperCase())
  const isEurTicker = /\.(LS|DE|PA|AS|MC|MI)$/i.test(data.ticker || '')

  return (
    <div className="space-y-5">
      {/* Clean Hero Bar */}
      <div className="terminal-card p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-mono font-bold text-white">{data.ticker}</h2>
            <span className="text-sm text-slate-300 font-medium">{fund.name}</span>
            {fund.sector && <StatusBadge variant="slate">{fund.sector}</StatusBadge>}
          </div>

          <div className="flex flex-wrap items-baseline gap-4 font-mono">
            <span className="text-3xl font-bold text-white tabular-nums">
              {formatPrice(sepa.price)}
              <span className="ml-1.5 text-sm font-normal text-slate-400">{fund.currency || 'USD'}</span>
            </span>
            <span className={`text-sm font-semibold ${sepa.daily_change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {formatPct(sepa.daily_change_pct)} hoje
            </span>
          </div>

          {fund.earnings_within_14d && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-600/25 border border-rose-500 text-rose-200 text-xs font-bold">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              EARNINGS em {fund.days_to_earnings} dias ({fund.next_earnings_date}) — alto risco de gap!
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              className="w-28 px-2.5 py-1.5 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
            />
            <button
              type="submit"
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/50 text-slate-200"
            >
              Ir
            </button>
          </form>

          <button
            onClick={() => loadXRay(data.ticker, true)}
            className="p-2 rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/50 text-slate-300"
            title="Atualizar dados"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          <button
            onClick={() => onToggleFavorite?.(data.ticker)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition ${
              isFav
                ? 'bg-amber-500/20 border-amber-400/50 text-amber-200'
                : 'bg-terminal-card border-terminal-border hover:border-amber-400/40 text-slate-300 hover:text-amber-200'
            }`}
          >
            <Star className={`w-4 h-4 ${isFav ? 'fill-amber-400 text-amber-400' : ''}`} />
            {isFav ? 'Favorito' : 'Guardar'}
          </button>

          {isAdmin && (
            <button
              onClick={() =>
                onCreateAlert?.({
                  ticker: data.ticker,
                  condition: 'ABOVE',
                  target_price: plan.entry_pivot || sepa.price,
                  notes: `Alerta Pivô ${data.ticker}`,
                })
              }
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40 transition"
            >
              <BellPlus className="w-4 h-4" />
              Alerta
            </button>
          )}

          <button
            onClick={() =>
              onSimulateTrade({
                ticker: data.ticker,
                asset_type: data.asset_type,
                asset_currency: isEurTicker ? 'EUR' : 'USD',
                entry_price: sepa.price,
                stop_loss_pct: Math.min(plan.stop_loss_pct || 6.0, 6.0),
                setup_tag: activeStrategy === 'minervini' ? 'VCP' : activeStrategy.toUpperCase(),
                notes: `Raio-X ${data.ticker} (${activeStrategy})`,
              })
            }
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 transition"
          >
            <Zap className="w-4 h-4" />
            Simular Entrada
          </button>
        </div>
      </div>

      <WarningBanner warnings={data.warnings} />

      {/* Single Active Strategy Selector (Synced with Chart & Panel Below!) */}
      <StrategySelector activeStrategy={activeStrategy} onChange={onChangeStrategy} />

      {/* Candlestick Chart (Shows ONLY layers for the active strategy!) */}
      <CandlestickChart chartData={data.chart} ticker={data.ticker} strategy={activeStrategy} />

      {/* EXCLUSIVE ACTIVE STRATEGY PANEL — NOTHING FROM OTHER STRATEGIES APPEARS HERE! */}
      {activeStrategy === 'minervini' && (
        <div className="terminal-card p-5 space-y-4 border-emerald-500/25">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-bold text-white">Análise Minervini SEPA / VCP</h3>
              <SetupStatusBadge status={sepa.status} />
              <StatusBadge variant="cyan">Score {sepa.score}/100</StatusBadge>
              <StatusBadge variant={tt.passed ? 'green' : tt.passed_count >= 6 ? 'yellow' : 'red'}>
                {tt.passed_count}/8 Stage 2
              </StatusBadge>
              <StatusBadge variant="slate">RS {tt.relative_strength?.rs_rating ?? '—'}/99</StatusBadge>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="bg-[#080e1c] rounded-xl p-3 border border-terminal-border">
              <div className="text-[10px] text-slate-400 font-sans">Pivô Sugerido</div>
              <div className="text-base font-bold text-emerald-300 mt-0.5">{formatPrice(plan.entry_pivot)}</div>
            </div>
            <div className="bg-[#080e1c] rounded-xl p-3 border border-rose-500/30">
              <div className="text-[10px] text-slate-400 font-sans">Stop Técnico (-{plan.stop_loss_pct}%)</div>
              <div className="text-base font-bold text-rose-400 mt-0.5">{formatPrice(plan.stop_loss_price)}</div>
            </div>
            <div className="bg-[#080e1c] rounded-xl p-3 border border-terminal-border">
              <div className="text-[10px] text-slate-400 font-sans">Alvo 2R (+{plan.target_2r_pct}%)</div>
              <div className="text-base font-bold text-emerald-400 mt-0.5">{formatPrice(plan.target_2r)}</div>
            </div>
            <div className="bg-[#080e1c] rounded-xl p-3 border border-terminal-border">
              <div className="text-[10px] text-slate-400 font-sans">Alvo 3R (+{plan.target_3r_pct}%)</div>
              <div className="text-base font-bold text-cyan-300 mt-0.5">{formatPrice(plan.target_3r)}</div>
            </div>
          </div>

          <p className="text-xs text-slate-300 bg-[#070b14] border border-terminal-border rounded-lg px-3.5 py-2.5">
            {vcp.summary}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {(tt.rules || []).map((r) => (
              <div
                key={r.id}
                className={`flex items-start gap-2 px-3 py-2 rounded-lg border text-xs ${
                  r.passed ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-rose-500/5 border-rose-500/25'
                }`}
              >
                {r.passed ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                )}
                <div className="min-w-0">
                  <div className="font-semibold text-slate-100 truncate">
                    {r.id}. {r.title}
                  </div>
                  <div className="font-mono text-[10px] text-slate-400 truncate">{r.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeStrategy === 'qullamaggie' && (
        <div className="terminal-card p-5 space-y-4 border-cyan-500/25">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
            <h3 className="text-sm font-bold text-white">Análise Qullamaggie Momentum</h3>
            {bt.available && (
              <StatusBadge variant="cyan">Trailing Sugerido: {bt.best_trailing_ma}</StatusBadge>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">ADR% (20 dias)</div>
              <div className="text-lg font-bold text-cyan-300 mt-0.5">{q.adr_pct_20d ?? '—'}%/dia</div>
              <div className="text-[10px] font-sans text-slate-500">
                {q.adr_tier} • Stop = {q.stop_in_adr_multiples ?? '—'}x ADR
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Extensão vs SMA 50</div>
              <div className={`text-lg font-bold mt-0.5 ${q.is_atr_overextended ? 'text-rose-400' : 'text-emerald-400'}`}>
                {q.atr_extension_sma50 ?? '—'}x ATR
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                {q.is_atr_overextended ? 'Esticada (não perseguir)' : 'Zona controlada'}
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Episodic Pivot (EP)</div>
              <div className={`text-lg font-bold mt-0.5 ${q.episodic_pivot?.detected ? 'text-emerald-400' : 'text-slate-400'}`}>
                {q.episodic_pivot?.detected ? `SIM (+${q.episodic_pivot.gap_pct}%)` : 'Não'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                {q.episodic_pivot?.detected ? `Vol ${q.episodic_pivot.volume_ratio}x em ${q.episodic_pivot.date}` : 'Sem gap explosivo recente'}
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">High Tight Flag (HTF)</div>
              <div className={`text-lg font-bold mt-0.5 ${q.high_tight_flag?.detected ? 'text-cyan-300' : 'text-slate-400'}`}>
                {q.high_tight_flag?.detected ? 'ATIVO' : 'Não'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                {q.high_tight_flag?.detected
                  ? `Mastro +${q.high_tight_flag.pole_gain_pct}% • Bandeira ${q.high_tight_flag.flag_depth_pct}%`
                  : 'Sem bandeira explosiva'}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
            <div className="bg-[#070b14] rounded-lg p-3 border border-terminal-border">
              <span className="text-slate-400 font-sans">Entrada / Pivô:</span>{' '}
              <strong className="text-emerald-300">{formatPrice(plan.entry_pivot)}</strong>
            </div>
            <div className="bg-[#070b14] rounded-lg p-3 border border-rose-500/25">
              <span className="text-slate-400 font-sans">Stop Máx (≤ 6%):</span>{' '}
              <strong className="text-rose-400">{formatPrice(plan.stop_loss_price)} (-{plan.stop_loss_pct}%)</strong>
            </div>
            <div className="bg-[#070b14] rounded-lg p-3 border border-terminal-border">
              <span className="text-slate-400 font-sans">Trailing Ideal:</span>{' '}
              <strong className="text-cyan-300">{bt.best_trailing_ma || 'SMA21'}</strong>
            </div>
          </div>
        </div>
      )}

      {activeStrategy === 'institutional' && (
        <div className="terminal-card p-5 space-y-4 border-purple-500/25">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
            <h3 className="text-sm font-bold text-white">Análise Institucional (O&apos;Neil / CAN SLIM / Insiders)</h3>
            <div className="flex flex-wrap gap-2">
              {volQ.available && (
                <StatusBadge
                  variant={['A', 'B'].includes(volQ.acc_dist_grade) ? 'green' : ['D', 'E'].includes(volQ.acc_dist_grade) ? 'red' : 'yellow'}
                >
                  Volume Grau {volQ.acc_dist_grade} ({volQ.up_down_volume_ratio_50d}x)
                </StatusBadge>
              )}
              {inst.available && (
                <StatusBadge variant={inst.code_33_acceleration ? 'green' : 'slate'}>
                  {inst.code_33_acceleration ? 'CODE 33 ATIVO' : 'SEM CODE 33'}
                </StatusBadge>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400 flex items-center gap-1">
                <BarChart3 className="w-3 h-3 text-cyan-400" /> Volume Up/Down (50d)
              </div>
              <div className="text-lg font-bold text-white mt-0.5">
                {volQ.up_down_volume_ratio_50d ?? '—'}x ({volQ.acc_dist_grade || '—'})
              </div>
              <div className="text-[10px] font-sans text-slate-500">{volQ.acc_dist_label}</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Pocket Pivot (10d)</div>
              <div className={`text-lg font-bold mt-0.5 ${q.pocket_pivot?.detected ? 'text-emerald-400' : 'text-slate-400'}`}>
                {q.pocket_pivot?.detected ? `SIM (${q.pocket_pivot.vol_vs_max_down}x)` : 'Não'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                3 Weeks Tight: <strong>{q.three_weeks_tight?.detected ? 'SIM' : 'Não'}</strong>
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">CAN SLIM</div>
              <div className="text-lg font-bold text-purple-300 mt-0.5">
                {q.canslim?.score !== null && q.canslim?.score !== undefined ? `${q.canslim.grade} (${q.canslim.score})` : 'N/A'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">RS Rating: {tt.relative_strength?.rs_rating ?? '—'}/99</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400 flex items-center gap-1">
                <Users className="w-3 h-3 text-purple-400" /> Insiders &amp; Short
              </div>
              <div className="text-sm font-bold text-slate-100 mt-0.5">
                {inst.available ? inst.insiders?.signal?.replace('_', ' ') || 'NEUTRO' : 'N/A'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                Short: {inst.short_interest?.short_float_pct ?? '—'}% • Inst.: {inst.short_interest?.institutional_held_pct ?? '—'}%
              </div>
            </div>
          </div>

          {inst.available && ((inst.earnings_surprises || []).length > 0 || (inst.quarterly_financials || []).length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-1">
              {(inst.earnings_surprises || []).length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-semibold text-slate-300">
                    Surpresas de Earnings ({inst.beats_last_4}/{inst.earnings_surprises.length} superados)
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                    {inst.earnings_surprises.map((s) => (
                      <div
                        key={s.quarter}
                        className={`rounded-lg p-2 border ${
                          s.beat ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200' : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                        }`}
                      >
                        <div className="text-[9px] text-slate-400">{s.quarter}</div>
                        <div className="font-bold">
                          {s.surprise_pct !== null && s.surprise_pct !== undefined ? `${s.surprise_pct >= 0 ? '+' : ''}${s.surprise_pct}%` : s.beat ? 'Bateu' : 'Falhou'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(inst.quarterly_financials || []).length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px] font-mono">
                    <thead>
                      <tr className="text-slate-500 border-b border-terminal-border text-left">
                        <th className="py-1 font-sans">Trimestre</th>
                        <th className="py-1 text-right font-sans">Receita</th>
                        <th className="py-1 text-right font-sans">QoQ</th>
                        <th className="py-1 text-right font-sans">Lucro</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-terminal-border/50">
                      {inst.quarterly_financials.map((qr) => (
                        <tr key={qr.quarter}>
                          <td className="py-1 text-slate-300">{qr.quarter}</td>
                          <td className="py-1 text-right text-white font-semibold">{formatCompactNumber(qr.revenue, fund.currency)}</td>
                          <td className={`py-1 text-right ${(qr.rev_qoq_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {qr.rev_qoq_pct !== null && qr.rev_qoq_pct !== undefined ? formatPct(qr.rev_qoq_pct) : '—'}
                          </td>
                          <td className="py-1 text-right text-slate-200">{formatCompactNumber(qr.net_income, fund.currency)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeStrategy === 'weinstein_squeeze' && (
        <div className="terminal-card p-5 space-y-4 border-amber-500/25">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
            <h3 className="text-sm font-bold text-white">Análise Stan Weinstein, TTM Squeeze &amp; Anchored VWAP</h3>
            <StatusBadge variant={q.weinstein?.stage === 2 ? 'green' : q.weinstein?.stage === 4 ? 'red' : 'yellow'}>
              Stage {q.weinstein?.stage || '—'} — {q.weinstein?.label || '—'}
            </StatusBadge>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Fase Weinstein</div>
              <div className={`text-lg font-bold mt-0.5 ${q.weinstein?.stage === 2 ? 'text-emerald-400' : q.weinstein?.stage === 4 ? 'text-rose-400' : 'text-amber-300'}`}>
                Stage {q.weinstein?.stage || '—'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">{q.weinstein?.label}</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">TTM Squeeze</div>
              <div className={`text-lg font-bold mt-0.5 ${q.ttm_squeeze?.squeeze_fire_long ? 'text-emerald-400' : q.ttm_squeeze?.squeeze_on ? 'text-amber-300' : 'text-slate-400'}`}>
                {q.ttm_squeeze?.state?.replace('_', ' ') || 'NEUTRO'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                {q.ttm_squeeze?.squeeze_on ? `${q.ttm_squeeze.squeeze_bars} dias comprimido` : 'Sem compressão ativa'}
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Mansfield RS</div>
              <div className={`text-lg font-bold mt-0.5 ${(q.mansfield_rs || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {q.mansfield_rs !== null && q.mansfield_rs !== undefined ? `${q.mansfield_rs >= 0 ? '+' : ''}${q.mansfield_rs}` : '—'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">Acima de 0 = supera o índice</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3.5">
              <div className="text-[10px] font-sans text-slate-400">Anchored VWAP</div>
              <div className={`text-sm font-bold mt-1 ${data.chart?.avwap_meta?.above_avwap_swing ? 'text-emerald-400' : 'text-rose-400'}`}>
                {data.chart?.avwap_meta?.above_avwap_swing ? 'Acima AVWAP Low ✓' : 'Abaixo AVWAP Low'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                YTD: {data.chart?.avwap_meta?.above_avwap_ytd ? 'Acima ✓' : 'Abaixo'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Crypto Derivatives Strip (only for Crypto assets) */}
      {data.derivatives?.available && (
        <div className="rounded-xl bg-purple-500/10 border border-purple-500/30 p-3 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
          <span className="font-sans font-bold text-purple-200">Derivados Binance Futures:</span>
          <span>
            Funding:{' '}
            <strong className={data.derivatives.funding_rate_pct >= 0.05 ? 'text-rose-400' : 'text-emerald-300'}>
              {data.derivatives.funding_rate_pct >= 0 ? '+' : ''}
              {data.derivatives.funding_rate_pct}%
            </strong>
          </span>
          <span>
            OI: <strong className="text-white">{formatCompactNumber(data.derivatives.open_interest_usd)}</strong> (
            {formatPct(data.derivatives.oi_change_24h_pct)})
          </span>
          <span>
            Baleias L/S: <strong className="text-cyan-300">{data.derivatives.top_traders_ls_ratio}</strong>
          </span>
        </div>
      )}

      {/* Clean Bottom Tabs (1 Detail Section at a Time — Zero Page Bloat!) */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 border-b border-terminal-border pb-2.5">
          {[
            { id: 'ai_news', label: 'Briefing IA & Notícias' },
            { id: 'fundamentals', label: 'Fundamentais & Earnings' },
            { id: 'backtest', label: 'Backtest 2 Anos' },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setDetailTab(t.id)}
              className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl border transition ${
                detailTab === t.id
                  ? 'bg-cyan-500/20 border-cyan-400/50 text-white'
                  : 'bg-terminal-panel border-terminal-border text-slate-400 hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {detailTab === 'ai_news' && (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
            <div className="xl:col-span-5 terminal-card p-5 border-cyan-500/30 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">Briefing IA</h3>
                </div>
                <StatusBadge variant={briefing.ai_mode === 'fallback' ? 'yellow' : 'cyan'}>{briefing.provider}</StatusBadge>
              </div>
              <div className="rounded-lg bg-cyan-500/10 border border-cyan-500/30 p-3 text-xs">
                <p className="text-slate-100 leading-relaxed">{briefing.verdict}</p>
              </div>
              <div className="grid grid-cols-1 gap-2 text-xs">
                {(briefing.catalysts || []).slice(0, 3).map((c, idx) => (
                  <div key={idx} className="text-slate-200 bg-emerald-500/5 border border-emerald-500/15 rounded-md px-2.5 py-1.5">
                    + {c}
                  </div>
                ))}
                {(briefing.risks || []).slice(0, 3).map((r, idx) => (
                  <div key={idx} className="text-slate-200 bg-rose-500/5 border border-rose-500/15 rounded-md px-2.5 py-1.5">
                    − {r}
                  </div>
                ))}
              </div>
            </div>

            <div className="xl:col-span-7 terminal-card p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Newspaper className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">Notícias Recentes</h3>
                </div>
                <StatusBadge
                  variant={sentSummary.overall === 'Positivo' ? 'green' : sentSummary.overall === 'Negativo' ? 'red' : 'slate'}
                >
                  Sentimento: {sentSummary.overall || 'Neutro'}
                </StatusBadge>
              </div>

              {(news.items || []).length === 0 ? (
                <p className="text-xs text-slate-500 py-4">Sem notícias recentes disponíveis.</p>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {(news.items || []).slice(0, 8).map((it, idx) => (
                    <a
                      key={idx}
                      href={it.link}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-[#080e1c] border border-terminal-border hover:border-cyan-500/40 transition text-xs"
                    >
                      <div className="space-y-0.5 min-w-0">
                        <div className="text-slate-100 font-medium leading-snug">{it.title}</div>
                        <div className="text-[10px] text-slate-500">{it.source}</div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <SentimentBadge sentiment={it.sentiment} />
                        <ExternalLink className="w-3 h-3 text-slate-500" />
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {detailTab === 'fundamentals' && (
          <div className="terminal-card p-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              {[
                { label: 'Market Cap', value: formatCompactNumber(fund.market_cap, fund.currency) },
                {
                  label: 'Próximos Earnings',
                  value: fund.next_earnings_date
                    ? `${fund.next_earnings_date} (${fund.days_to_earnings}d)`
                    : data.asset_type === 'crypto'
                      ? 'N/A (Cripto)'
                      : 'N/D',
                  highlight: fund.earnings_within_14d ? 'text-rose-400 font-bold' : '',
                },
                {
                  label: 'Cresc. Receitas (YoY)',
                  value: fund.revenue_growth !== null && fund.revenue_growth !== undefined ? formatPct(fund.revenue_growth * 100) : '—',
                },
                {
                  label: 'Cresc. Lucros (YoY)',
                  value: fund.earnings_growth !== null && fund.earnings_growth !== undefined ? formatPct(fund.earnings_growth * 100) : '—',
                },
                { label: 'P/E (Trailing)', value: fund.trailing_pe ? fund.trailing_pe.toFixed(1) : '—' },
                { label: 'P/E (Forward)', value: fund.forward_pe ? fund.forward_pe.toFixed(1) : '—' },
                {
                  label: 'Margem Lucro',
                  value: fund.profit_margins !== null && fund.profit_margins !== undefined ? formatPct(fund.profit_margins * 100, false) : '—',
                },
                {
                  label: 'ROE',
                  value: fund.return_on_equity !== null && fund.return_on_equity !== undefined ? formatPct(fund.return_on_equity * 100, false) : '—',
                },
              ].map((m) => (
                <div key={m.label} className="bg-[#080e1c] border border-terminal-border rounded-xl p-3">
                  <div className="text-[10px] text-slate-400 font-sans">{m.label}</div>
                  <div className={`text-sm font-semibold mt-0.5 text-slate-100 ${m.highlight || ''}`}>{m.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {detailTab === 'backtest' && (
          <div className="terminal-card p-5 space-y-3">
            {bt.available ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-sm font-bold text-white">Personalidade do Ativo (Backtest 2 Anos)</h3>
                  </div>
                  <StatusBadge variant="cyan">Trailing Ideal: {bt.best_trailing_ma}</StatusBadge>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                  <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                    <div className="text-[10px] font-sans text-slate-400">Taxa de Acerto (+12% vs -6%)</div>
                    <div className="text-lg font-bold text-white mt-0.5">
                      {bt.win_rate_pct !== null && bt.win_rate_pct !== undefined ? `${bt.win_rate_pct}%` : '—'}
                    </div>
                  </div>
                  <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                    <div className="text-[10px] font-sans text-slate-400">Breakouts (2 Anos)</div>
                    <div className="text-lg font-bold text-emerald-400 mt-0.5">
                      {bt.wins_2r}W / <span className="text-rose-400">{bt.losses_stop}L</span>
                    </div>
                  </div>
                  <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                    <div className="text-[10px] font-sans text-slate-400">Taxa de Fakeout (5d)</div>
                    <div className="text-lg font-bold text-amber-300 mt-0.5">
                      {bt.fakeout_rate_pct !== null && bt.fakeout_rate_pct !== undefined ? `${bt.fakeout_rate_pct}%` : '—'}
                    </div>
                  </div>
                  <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
                    <div className="text-[10px] font-sans text-slate-400">Ganho Máx. Médio (20d)</div>
                    <div className="text-lg font-bold text-cyan-300 mt-0.5">
                      {bt.avg_max_gain_20d_pct !== null && bt.avg_max_gain_20d_pct !== undefined ? `+${bt.avg_max_gain_20d_pct}%` : '—'}
                    </div>
                  </div>
                </div>
                <p className="text-xs text-slate-300 bg-[#080e1c] border border-terminal-border rounded-lg px-3.5 py-2.5">
                  <strong>{bt.personality_label}.</strong> {bt.best_trailing_reason}
                </p>
              </>
            ) : (
              <p className="text-xs text-slate-400">Histórico insuficiente para backtest de 2 anos.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
