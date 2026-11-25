import React, { useEffect, useState } from 'react'
import {
  AlertOctagon,
  BellPlus,
  CheckCircle2,
  ExternalLink,
  Newspaper,
  RefreshCw,
  Sparkles,
  Star,
  XCircle,
  Zap,
} from 'lucide-react'
import { api, formatCompactNumber, formatPct, formatPrice } from '../services/api'
import { CandlestickChart } from '../components/CandlestickChart'
import { SentimentBadge, SetupStatusBadge, StatusBadge } from '../components/StatusBadge'
import { WarningBanner } from '../components/WarningBanner'

export function XRayModule({
  ticker,
  onChangeTicker,
  onSimulateTrade,
  onCreateAlert,
  favorites = [],
  onToggleFavorite,
  isAdmin = true,
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [inputVal, setInputVal] = useState(ticker || 'NVDA')

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
          A gerar Raio-X completo para <span className="font-mono font-bold text-cyan-300">{ticker}</span> (OHLCV, 8 Regras, Fundamentais, RSS + VADER, Briefing IA)...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="terminal-card p-6 border-rose-500/40 text-rose-300 space-y-3">
          <p className="font-semibold">Não foi possível carregar o Raio-X de "{ticker}": {error}</p>
          <p className="text-xs text-slate-400">Verifica o símbolo (ex: NVDA, AAPL, MSFT, BTC-USD, SOL-USD).</p>
        </div>
      </div>
    )
  }

  const sepa = data?.sepa || {}
  const tt = sepa.trend_template || {}
  const vcp = sepa.vcp || {}
  const plan = sepa.trade_plan || {}
  const fund = data?.fundamentals || {}
  const news = data?.news || {}
  const sentSummary = news.sentiment_summary || {}
  const briefing = data?.briefing || {}

  return (
    <div className="space-y-5">
      {/* Top Asset Hero Bar */}
      <div className="terminal-card p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-mono font-bold text-white">{data.ticker}</h2>
            <span className="text-sm text-slate-300 font-medium">{fund.name}</span>
            <SetupStatusBadge status={sepa.status} />
            <StatusBadge variant="cyan">Score {sepa.score}/100</StatusBadge>
            {tt.relative_strength?.rs_new_high_before_price && (
              <span className="px-2 py-0.5 rounded bg-blue-500/20 border border-blue-400/50 text-blue-300 font-mono text-xs font-bold">
                ● RS NEW HIGH BEFORE PRICE
              </span>
            )}
            <StatusBadge variant="slate">Fonte: {data.data_source}</StatusBadge>
          </div>

          <div className="flex flex-wrap items-baseline gap-4 font-mono">
            <span className="text-3xl font-bold text-white tabular-nums">{formatPrice(sepa.price)}</span>
            <span className={`text-sm font-semibold ${sepa.daily_change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {formatPct(sepa.daily_change_pct)} hoje
            </span>
            <span className="text-xs text-slate-400">
              RS Rating: <strong className="text-cyan-300">{tt.relative_strength?.rs_rating ?? '—'}/99</strong>
            </span>
            {fund.sector && <span className="text-xs text-slate-400 font-sans">{fund.sector} • {fund.industry}</span>}
          </div>

          {fund.earnings_within_14d && (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-600/25 border border-rose-500 text-rose-200 text-xs font-bold">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              ALERTA VERMELHO: Apresentação de Resultados (Earnings) em {fund.days_to_earnings} dias ({fund.next_earnings_date})!
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              className="w-32 px-2.5 py-1.5 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
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
            title="Forçar atualização"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          <button
            onClick={() => onToggleFavorite?.(data.ticker)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition ${
              favorites.includes((data.ticker || '').toUpperCase())
                ? 'bg-amber-500/20 border-amber-400/50 text-amber-200'
                : 'bg-terminal-card border-terminal-border hover:border-amber-400/40 text-slate-300 hover:text-amber-200'
            }`}
            title="Guardar ou remover dos teus Favoritos pessoais"
          >
            <Star
              className={`w-4 h-4 ${
                favorites.includes((data.ticker || '').toUpperCase()) ? 'fill-amber-400 text-amber-400' : ''
              }`}
            />
            {favorites.includes((data.ticker || '').toUpperCase()) ? 'Favorito' : 'Guardar ★'}
          </button>

          {isAdmin && (
            <button
              onClick={() =>
                onCreateAlert?.({
                  ticker: data.ticker,
                  condition: 'ABOVE',
                  target_price: plan.entry_pivot || sepa.price,
                  notes: `Alerta Pivô VCP ${data.ticker} (${formatPrice(plan.entry_pivot)})`,
                })
              }
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40 transition"
            >
              <BellPlus className="w-4 h-4" />
              Alerta Pivô
            </button>
          )}

          <button
            onClick={() =>
              onSimulateTrade({
                ticker: data.ticker,
                asset_type: data.asset_type,
                entry_price: sepa.price,
                stop_loss_pct: Math.min(plan.stop_loss_pct || 6.0, 6.0),
                setup_tag: sepa.status === 'BREAKOUT' ? 'BREAKOUT' : 'VCP',
                notes: `Raio-X ${sepa.status} | Score ${sepa.score}/100`,
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

      {/* Interactive TradingView Lightweight Candlestick Chart */}
      <CandlestickChart chartData={data.chart} ticker={data.ticker} />

      {/* Clean Multi-Strategy Quant Radar Strip (Weinstein, Qullamaggie, Morales, Carter, O'Neil) */}
      {sepa.quant && (
        <div className="terminal-card p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-white">Radar Multi-Estratégia (Além de Minervini)</h3>
            <span className="text-[11px] text-slate-400">
              Weinstein • Qullamaggie • Morales/Kacher • John Carter • O&apos;Neil CAN SLIM
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 text-xs font-mono">
            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">Fase Weinstein</div>
              <div
                className={`font-bold mt-0.5 ${
                  sepa.quant.weinstein?.stage === 2
                    ? 'text-emerald-400'
                    : sepa.quant.weinstein?.stage === 4
                      ? 'text-rose-400'
                      : 'text-amber-300'
                }`}
              >
                Stage {sepa.quant.weinstein?.stage || '—'}
              </div>
              <div className="text-[10px] font-sans text-slate-500 truncate">{sepa.quant.weinstein?.label}</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">ADR% (Qullamaggie)</div>
              <div className="font-bold text-cyan-300 mt-0.5">{sepa.quant.adr_pct_20d ?? '—'}%/dia</div>
              <div className="text-[10px] font-sans text-slate-500">
                {sepa.quant.adr_tier} • Stop {sepa.quant.stop_in_adr_multiples ?? '—'}x ADR
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">Mansfield RS / Ext. ATR</div>
              <div className={`font-bold mt-0.5 ${(sepa.quant.mansfield_rs || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                MRS {sepa.quant.mansfield_rs !== null && sepa.quant.mansfield_rs !== undefined ? `${sepa.quant.mansfield_rs >= 0 ? '+' : ''}${sepa.quant.mansfield_rs}` : '—'}
              </div>
              <div className={`text-[10px] ${sepa.quant.is_atr_overextended ? 'text-rose-400 font-bold' : 'text-slate-500'}`}>
                SMA50: {sepa.quant.atr_extension_sma50 ?? '—'}x ATR
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">Pocket Pivot (10d)</div>
              <div className={`font-bold mt-0.5 ${sepa.quant.pocket_pivot?.detected ? 'text-emerald-400' : 'text-slate-400'}`}>
                {sepa.quant.pocket_pivot?.detected ? `SIM (${sepa.quant.pocket_pivot.vol_vs_max_down}x)` : 'Não'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">Acumulação precoce</div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">TTM Squeeze (Carter)</div>
              <div
                className={`font-bold mt-0.5 ${
                  sepa.quant.ttm_squeeze?.squeeze_fire_long
                    ? 'text-emerald-400'
                    : sepa.quant.ttm_squeeze?.squeeze_on
                      ? 'text-amber-300'
                      : 'text-slate-400'
                }`}
              >
                {sepa.quant.ttm_squeeze?.state?.replace('_', ' ') || 'NEUTRO'}
              </div>
              <div className="text-[10px] font-sans text-slate-500">
                {sepa.quant.ttm_squeeze?.squeeze_on ? `${sepa.quant.ttm_squeeze.squeeze_bars} dias comprimido` : 'Bollinger vs Keltner'}
              </div>
            </div>

            <div className="rounded-xl bg-[#080e1c] border border-terminal-border p-3">
              <div className="text-[10px] font-sans text-slate-400">CAN SLIM / Padrões</div>
              <div className="font-bold text-purple-300 mt-0.5">
                {sepa.quant.canslim?.score !== null ? `${sepa.quant.canslim.grade} (${sepa.quant.canslim.score})` : 'N/A'}
              </div>
              <div className="text-[10px] font-sans text-slate-500 truncate">
                {[
                  sepa.quant.episodic_pivot?.detected ? 'EP' : null,
                  sepa.quant.high_tight_flag?.detected ? 'HTF' : null,
                  sepa.quant.three_weeks_tight?.detected ? '3WT' : null,
                ]
                  .filter(Boolean)
                  .join(' • ') || 'Sem EP/HTF/3WT'}
              </div>
            </div>
          </div>

          {/* Live Binance Futures Derivatives strip for Crypto assets */}
          {data.derivatives?.available && (
            <div className="rounded-xl bg-purple-500/10 border border-purple-500/30 p-3 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
              <span className="font-sans font-bold text-purple-200">Derivados Binance Futures (0€):</span>
              <span>
                Funding:{' '}
                <strong className={data.derivatives.funding_rate_pct >= 0.05 ? 'text-rose-400' : 'text-emerald-300'}>
                  {data.derivatives.funding_rate_pct >= 0 ? '+' : ''}
                  {data.derivatives.funding_rate_pct}% ({data.derivatives.funding_signal?.label})
                </strong>
              </span>
              <span>
                OI: <strong className="text-white">{formatCompactNumber(data.derivatives.open_interest_usd)}</strong> (
                {formatPct(data.derivatives.oi_change_24h_pct)})
              </span>
              <span>
                Baleias L/S:{' '}
                <strong className="text-cyan-300">
                  {data.derivatives.top_traders_ls_ratio} ({data.derivatives.top_long_pct}% Long)
                </strong>
              </span>
            </div>
          )}
        </div>
      )}

      {/* Middle 2-Column Analytical Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Left: 8 Minervini Rules + VCP Diagnostics (7 cols) */}
        <div className="xl:col-span-7 space-y-5">
          {/* 8 Rules Checklist */}
          <div className="terminal-card p-5">
            <div className="flex items-center justify-between mb-3.5">
              <div>
                <h3 className="text-sm font-bold text-white">Checklist Trend Template — Mark Minervini (8 Regras)</h3>
                <p className="text-xs text-slate-400">Validação objetiva de tendência institucional Stage 2</p>
              </div>
              <StatusBadge variant={tt.passed ? 'green' : tt.passed_count >= 6 ? 'yellow' : 'red'}>
                {tt.passed_count}/8 {tt.passed ? 'STAGE 2 PASSOU' : 'INCOMPLETO'}
              </StatusBadge>
            </div>

            <div className="space-y-2">
              {(tt.rules || []).map((r) => (
                <div
                  key={r.id}
                  className={`flex items-start justify-between gap-3 px-3.5 py-2.5 rounded-lg border text-xs ${
                    r.passed
                      ? 'bg-emerald-500/5 border-emerald-500/20'
                      : 'bg-rose-500/5 border-rose-500/25'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {r.passed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    )}
                    <div>
                      <div className="font-semibold text-slate-100">
                        {r.id}. {r.title}
                      </div>
                      <div className="font-mono text-[11px] text-slate-400 mt-0.5">{r.detail}</div>
                    </div>
                  </div>
                  <span
                    className={`font-mono text-[11px] font-bold shrink-0 ${
                      r.passed ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {r.passed ? 'PASSOU' : 'FALHOU'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* VCP & Trade Plan */}
          <div className="terminal-card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">Diagnóstico VCP & Plano de Risco (&lt;= 6%)</h3>
              <StatusBadge variant={vcp.detected ? 'cyan' : 'slate'}>
                {vcp.detected ? 'VCP DETETADO' : 'SEM VCP CLÁSSICO'}
              </StatusBadge>
            </div>
            <p className="text-xs text-slate-300 bg-[#070b14] border border-terminal-border rounded-lg p-3">
              {vcp.summary}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
              <div className="bg-terminal-card rounded-lg p-3 border border-terminal-border">
                <div className="text-[10px] text-slate-400 font-sans">Pivô Sugerido</div>
                <div className="text-base font-bold text-emerald-300 mt-0.5">{formatPrice(plan.entry_pivot)}</div>
              </div>
              <div className="bg-terminal-card rounded-lg p-3 border border-rose-500/30">
                <div className="text-[10px] text-slate-400 font-sans">Stop Técnico (-{plan.stop_loss_pct}%)</div>
                <div className="text-base font-bold text-rose-400 mt-0.5">{formatPrice(plan.stop_loss_price)}</div>
              </div>
              <div className="bg-terminal-card rounded-lg p-3 border border-terminal-border">
                <div className="text-[10px] text-slate-400 font-sans">Alvo 2R (+{plan.target_2r_pct}%)</div>
                <div className="text-base font-bold text-emerald-400 mt-0.5">{formatPrice(plan.target_2r)}</div>
              </div>
              <div className="bg-terminal-card rounded-lg p-3 border border-terminal-border">
                <div className="text-[10px] text-slate-400 font-sans">Alvo 3R (+{plan.target_3r_pct}%)</div>
                <div className="text-base font-bold text-cyan-300 mt-0.5">{formatPrice(plan.target_3r)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Fundamentals + AI Trader Briefing (5 cols) */}
        <div className="xl:col-span-5 space-y-5">
          {/* AI Trader Briefing */}
          <div className="terminal-card p-5 border-cyan-500/30 space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-white">Briefing de Trader (IA)</h3>
              </div>
              <StatusBadge variant={briefing.ai_mode === 'fallback' ? 'yellow' : 'cyan'}>
                {briefing.provider}
              </StatusBadge>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <h4 className="text-[11px] uppercase tracking-wider font-semibold text-emerald-400 mb-1.5">
                  Catalisadores Atuais
                </h4>
                <ul className="space-y-1.5">
                  {(briefing.catalysts || []).map((c, idx) => (
                    <li key={idx} className="text-slate-200 bg-emerald-500/5 border border-emerald-500/15 rounded-md px-2.5 py-1.5">
                      • {c}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-[11px] uppercase tracking-wider font-semibold text-rose-400 mb-1.5">
                  Principais Riscos
                </h4>
                <ul className="space-y-1.5">
                  {(briefing.risks || []).map((r, idx) => (
                    <li key={idx} className="text-slate-200 bg-rose-500/5 border border-rose-500/15 rounded-md px-2.5 py-1.5">
                      • {r}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-lg bg-cyan-500/10 border border-cyan-500/30 p-3">
                <div className="text-[11px] uppercase tracking-wider font-bold text-cyan-300 mb-1">Veredito Objetivo</div>
                <p className="text-slate-100 leading-relaxed">{briefing.verdict}</p>
              </div>

              {briefing.note && (
                <p className="text-[11px] text-slate-500 italic">{briefing.note}</p>
              )}
            </div>
          </div>

          {/* Fundamentals Card */}
          <div className="terminal-card p-5">
            <h3 className="text-sm font-bold text-white mb-3">Fundamentais & Earnings</h3>
            <div className="grid grid-cols-2 gap-2.5 text-xs font-mono">
              {[
                { label: 'Market Cap', value: formatCompactNumber(fund.market_cap) },
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
                {
                  label: 'P/E (Trailing)',
                  value: fund.trailing_pe ? fund.trailing_pe.toFixed(1) : '—',
                },
                {
                  label: 'P/E (Forward)',
                  value: fund.forward_pe ? fund.forward_pe.toFixed(1) : '—',
                },
                {
                  label: 'Margem Lucro',
                  value: fund.profit_margins !== null && fund.profit_margins !== undefined ? formatPct(fund.profit_margins * 100, false) : '—',
                },
                {
                  label: 'ROE',
                  value: fund.return_on_equity !== null && fund.return_on_equity !== undefined ? formatPct(fund.return_on_equity * 100, false) : '—',
                },
              ].map((m) => (
                <div key={m.label} className="bg-[#070b14] border border-terminal-border rounded-lg p-2.5">
                  <div className="text-[10px] text-slate-400 font-sans">{m.label}</div>
                  <div className={`text-sm font-semibold mt-0.5 text-slate-100 ${m.highlight || ''}`}>{m.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* News & Local Sentiment (VADER) */}
      <div className="terminal-card p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Newspaper className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white">Últimas Notícias & Sentimento Local (RSS + VADER)</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <StatusBadge
              variant={
                sentSummary.overall === 'Positivo'
                  ? 'green'
                  : sentSummary.overall === 'Negativo'
                    ? 'red'
                    : 'slate'
              }
            >
              Global: {sentSummary.overall || 'Neutro'} ({sentSummary.average_score >= 0 ? '+' : ''}
              {(sentSummary.average_score || 0).toFixed(2)})
            </StatusBadge>
            <span className="text-[11px] font-mono text-emerald-400">+{sentSummary.positive || 0} Pos</span>
            <span className="text-[11px] font-mono text-slate-400">{sentSummary.neutral || 0} Neu</span>
            <span className="text-[11px] font-mono text-rose-400">-{sentSummary.negative || 0} Neg</span>
          </div>
        </div>

        {(news.items || []).length === 0 ? (
          <p className="text-xs text-slate-400">Sem notícias recentes disponíveis nos feeds gratuitos para este ticker.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(news.items || []).map((n, idx) => (
              <a
                key={idx}
                href={n.link || '#'}
                target="_blank"
                rel="noreferrer"
                className="group block rounded-lg bg-[#090f1d] border border-terminal-border hover:border-cyan-500/40 p-3.5 transition"
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <span className="text-[11px] font-mono text-cyan-400">{n.source}</span>
                  <SentimentBadge sentiment={n.sentiment} />
                </div>
                <div className="text-xs font-semibold text-slate-100 group-hover:text-cyan-200 leading-snug flex items-start gap-1">
                  <span className="flex-1">{n.title}</span>
                  <ExternalLink className="w-3 h-3 text-slate-500 shrink-0 mt-0.5" />
                </div>
                {n.published && <div className="text-[10px] text-slate-500 mt-1.5 font-mono">{n.published}</div>}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
