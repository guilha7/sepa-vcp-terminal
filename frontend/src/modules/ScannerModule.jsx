import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertOctagon,
  BellPlus,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Columns2,
  ExternalLink,
  Keyboard,
  Plus,
  RefreshCw,
  Settings2,
  ShieldAlert,
  Trash2,
  Zap,
} from 'lucide-react'
import { api, formatPct, formatPrice, formatTimestamp } from '../services/api'
import { CandlestickChart } from '../components/CandlestickChart'
import { SetupStatusBadge, StatusBadge } from '../components/StatusBadge'
import { WarningBanner } from '../components/WarningBanner'

export function ScannerModule({ onOpenXRay, onSimulateTrade, onCreateAlert }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(null) // {pct, current, total, ticker, stage}
  const [error, setError] = useState(null)

  // Filters & Layout
  const [assetFilter, setAssetFilter] = useState('all') // all | stock | crypto
  const [stageFilter, setStageFilter] = useState('all') // all | stage2 | vcp | breakout | rs_nh
  const [minScore, setMinScore] = useState(0)
  const [query, setQuery] = useState('')
  const [splitMode, setSplitMode] = useState(true)
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [expanded, setExpanded] = useState({})

  // Quick Chart cache for instant split-screen navigation
  const [previewData, setPreviewData] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const chartCacheRef = useRef({})
  const sseCloseRef = useRef(null)

  // Watchlist modal
  const [showWatchlist, setShowWatchlist] = useState(false)
  const [watchlist, setWatchlist] = useState([])
  const [newTicker, setNewTicker] = useState('')
  const [newType, setNewType] = useState('stock')

  const loadCachedResults = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await api.getScannerResults()
      setData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const startStreamingScan = () => {
    if (sseCloseRef.current) sseCloseRef.current()
    setScanning(true)
    setError(null)
    setScanProgress({ pct: 2, current: 0, total: 90, ticker: 'A iniciar...', stage: 'A ligar ao servidor...' })
    sseCloseRef.current = api.streamScanner('', {
      onProgress: (p) => setScanProgress(p),
      onComplete: (res) => {
        chartCacheRef.current = {}
        setData(res)
        setScanning(false)
        setScanProgress(null)
      },
      onError: (err) => {
        setError(err.message)
        setScanning(false)
        setScanProgress(null)
      },
    })
  }

  useEffect(() => {
    loadCachedResults()
    return () => {
      if (sseCloseRef.current) sseCloseRef.current()
    }
  }, [])

  const loadWatchlist = async () => {
    try {
      const res = await api.getWatchlist()
      setWatchlist(res.items || [])
    } catch {
      // ignore
    }
  }

  const handleOpenWatchlist = () => {
    setShowWatchlist(true)
    loadWatchlist()
  }

  const handleAddTicker = async (e) => {
    e.preventDefault()
    if (!newTicker.trim()) return
    await api.addWatchlistTicker(newTicker.trim(), newType)
    setNewTicker('')
    loadWatchlist()
  }

  const handleRemoveTicker = async (tk) => {
    await api.removeWatchlistTicker(tk)
    loadWatchlist()
  }

  const filtered = useMemo(() => {
    const items = data?.opportunities || []
    return items.filter((item) => {
      if (assetFilter !== 'all' && item.asset_type !== assetFilter) return false
      if (stageFilter === 'stage2' && !item.trend_template?.passed) return false
      if (stageFilter === 'vcp' && !item.vcp?.detected && !item.vcp?.breakout_signal) return false
      if (stageFilter === 'breakout' && item.status !== 'BREAKOUT') return false
      if (stageFilter === 'rs_nh' && !item.trend_template?.relative_strength?.rs_new_high_before_price) return false
      if (item.score < minScore) return false
      if (query.trim()) {
        const q = query.trim().toLowerCase()
        if (
          !item.ticker.toLowerCase().includes(q) &&
          !(item.name || '').toLowerCase().includes(q) &&
          !(item.sector || '').toLowerCase().includes(q)
        ) {
          return false
        }
      }
      return true
    })
  }, [data, assetFilter, stageFilter, minScore, query])

  // Ensure a valid selected ticker in split-screen mode
  useEffect(() => {
    if (!filtered.length) {
      setSelectedTicker(null)
      return
    }
    if (!selectedTicker || !filtered.some((i) => i.ticker === selectedTicker)) {
      setSelectedTicker(filtered[0].ticker)
    }
  }, [filtered, selectedTicker])

  const selectedItem = useMemo(
    () => filtered.find((i) => i.ticker === selectedTicker) || filtered[0] || null,
    [filtered, selectedTicker],
  )

  // Keyboard navigation (ArrowUp / ArrowDown / Enter) for fast SEPA chart review
  useEffect(() => {
    const onKeyDown = (e) => {
      if (!filtered.length || showWatchlist) return
      const tag = (e.target?.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return

      const idx = filtered.findIndex((i) => i.ticker === selectedTicker)
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        const next = filtered[Math.min((idx < 0 ? 0 : idx) + 1, filtered.length - 1)]
        if (next) setSelectedTicker(next.ticker)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        const prev = filtered[Math.max((idx < 0 ? 0 : idx) - 1, 0)]
        if (prev) setSelectedTicker(prev.ticker)
      } else if (e.key === 'Enter' && selectedItem) {
        e.preventDefault()
        onOpenXRay(selectedItem.ticker)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [filtered, selectedTicker, selectedItem, showWatchlist, onOpenXRay])

  // Fetch fast cached chart preview whenever selectedTicker changes in split-screen
  useEffect(() => {
    if (!splitMode || !selectedTicker) return
    if (chartCacheRef.current[selectedTicker]) {
      setPreviewData(chartCacheRef.current[selectedTicker])
      return
    }
    let cancelled = false
    setPreviewLoading(true)
    api
      .getQuickChart(selectedTicker)
      .then((res) => {
        if (!cancelled) {
          chartCacheRef.current[selectedTicker] = res
          setPreviewData(res)
        }
      })
      .catch(() => {
        if (!cancelled) setPreviewData(null)
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedTicker, splitMode])

  const toggleExpand = (ticker) => {
    setExpanded((prev) => ({ ...prev, [ticker]: !prev[ticker] }))
  }

  if (loading && !data) {
    return (
      <div className="terminal-card p-10 text-center space-y-3">
        <div className="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-slate-200 font-medium">A carregar Scanner SEPA + VCP...</p>
      </div>
    )
  }

  const summary = data?.summary || {}

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white">Scanner Automático Minervini (SEPA + VCP)</h2>
          <p className="text-xs text-slate-400">
            8 Regras Stage 2 • VCP por Swings Reais • RS New High • Breakout ≥ 1.5x • Último scan:{' '}
            {formatTimestamp(data?.scanned_at)} {data?.from_cache ? '(SQLite Cache)' : '(Live)'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setSplitMode((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition ${
              splitMode
                ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-200'
                : 'bg-terminal-panel border-terminal-border text-slate-300 hover:border-cyan-500/40'
            }`}
          >
            <Columns2 className="w-3.5 h-3.5" />
            Split-Screen
          </button>
          <button
            onClick={handleOpenWatchlist}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-200 transition"
          >
            <Settings2 className="w-3.5 h-3.5 text-cyan-400" />
            Watchlist
          </button>
          <button
            onClick={startStreamingScan}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'A analisar...' : 'Novo Scan Completo'}
          </button>
        </div>
      </div>

      {/* Real-time SSE Progress Bar */}
      {scanning && scanProgress && (
        <div className="terminal-card p-3.5 border-cyan-500/40 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-cyan-300 font-semibold">
              {scanProgress.stage} • <strong className="text-white">{scanProgress.ticker}</strong>
            </span>
            <span className="text-emerald-400 font-bold">{scanProgress.pct}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-[#070b14] overflow-hidden border border-terminal-border">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-300"
              style={{ width: `${Math.max(scanProgress.pct, 3)}%` }}
            />
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-300">{error}</div>
      )}
      <WarningBanner warnings={data?.warnings} />

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {[
          { label: 'Ativos Líquidos', value: summary.liquid_count ?? 0, color: 'text-white' },
          { label: 'Stage 2 (8/8)', value: summary.stage2_count ?? 0, color: 'text-emerald-400' },
          { label: 'VCP (Swings)', value: summary.vcp_count ?? 0, color: 'text-cyan-400' },
          { label: 'Breakouts (≥1.5x)', value: summary.breakout_count ?? 0, color: 'text-emerald-300' },
          { label: 'RS New High ●', value: summary.rs_new_high_count ?? 0, color: 'text-blue-400' },
          { label: 'Alerta Earnings (<14d)', value: summary.earnings_warning_count ?? 0, color: 'text-rose-400' },
        ].map((kpi) => (
          <div key={kpi.label} className="terminal-card p-3">
            <div className="text-[11px] text-slate-400">{kpi.label}</div>
            <div className={`text-xl font-mono font-bold mt-0.5 tabular-nums ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Filters Bar */}
      <div className="terminal-card p-3 flex flex-wrap items-center gap-2.5">
        <div className="inline-flex rounded-lg bg-[#070b14] border border-terminal-border p-0.5 text-xs">
          {[
            { k: 'all', l: 'Todos' },
            { k: 'stock', l: 'Ações' },
            { k: 'crypto', l: 'Cripto' },
          ].map((o) => (
            <button
              key={o.k}
              onClick={() => setAssetFilter(o.k)}
              className={`px-2.5 py-1 rounded-md transition ${
                assetFilter === o.k ? 'bg-cyan-500/20 text-cyan-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>

        <div className="inline-flex flex-wrap rounded-lg bg-[#070b14] border border-terminal-border p-0.5 text-xs">
          {[
            { k: 'all', l: 'Todos' },
            { k: 'stage2', l: 'Stage 2 (8/8)' },
            { k: 'vcp', l: 'VCP / Breakout' },
            { k: 'breakout', l: 'Breakouts' },
            { k: 'rs_nh', l: 'RS New High' },
          ].map((o) => (
            <button
              key={o.k}
              onClick={() => setStageFilter(o.k)}
              className={`px-2.5 py-1 rounded-md transition ${
                stageFilter === o.k ? 'bg-emerald-500/20 text-emerald-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filtrar ticker ou setor..."
          className="px-3 py-1.5 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/60"
        />

        <label className="flex items-center gap-2 text-xs text-slate-400 ml-auto">
          <span>Score mín:</span>
          <input
            type="range"
            min="0"
            max="90"
            step="5"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-20 accent-cyan-400"
          />
          <span className="font-mono text-cyan-300 w-6">{minScore}</span>
        </label>

        {splitMode && (
          <span className="hidden lg:inline-flex items-center gap-1 text-[10px] font-mono text-slate-500">
            <Keyboard className="w-3.5 h-3.5 text-cyan-500" /> ↑↓ percorrer • Enter Raio-X
          </span>
        )}
      </div>

      {/* Main Content: Split-Screen (List + Instant Chart Preview) OR Full List */}
      {filtered.length === 0 ? (
        <div className="terminal-card p-8 text-center text-sm text-slate-400">
          Nenhum ativo corresponde aos filtros selecionados. Experimenta baixar o Score mínimo ou alterar o filtro.
        </div>
      ) : splitMode ? (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
          {/* Left Column: Compact Navigable Setup List (5 cols) */}
          <div className="xl:col-span-5 space-y-2 max-h-[74vh] overflow-y-auto pr-1">
            {filtered.map((item) => {
              const active = selectedItem?.ticker === item.ticker
              const vcp = item.vcp || {}
              const tt = item.trend_template || {}
              const rs = tt.relative_strength || {}
              const contractions = (vcp.contractions_pct || []).map((c) => `${c.toFixed(0)}%`).join('→')

              return (
                <div
                  key={item.ticker}
                  onClick={() => setSelectedTicker(item.ticker)}
                  className={`rounded-xl p-3 border cursor-pointer transition ${
                    active
                      ? 'bg-cyan-500/10 border-cyan-400/70 shadow-sm'
                      : item.earnings_within_14d
                        ? 'bg-terminal-panel border-rose-500/40 hover:border-rose-400'
                        : 'bg-terminal-panel border-terminal-border hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className={`w-10 h-10 rounded-lg flex flex-col items-center justify-center font-mono font-bold border shrink-0 text-xs ${
                          item.score >= 75
                            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                            : item.score >= 55
                              ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                              : 'bg-slate-800/70 border-slate-700 text-slate-400'
                        }`}
                      >
                        {Math.round(item.score)}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-mono font-bold text-sm text-white">{item.ticker}</span>
                          <SetupStatusBadge status={item.status} />
                          {rs.rs_new_high_before_price && (
                            <span className="px-1.5 py-0.5 rounded bg-blue-500/20 border border-blue-400/50 text-blue-300 font-mono text-[9px] font-bold">
                              ● RS NH
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {tt.passed_count}/8 • RS {rs.rs_rating ?? '—'} {contractions ? `• VCP ${contractions}` : ''}
                        </div>
                      </div>
                    </div>

                    <div className="text-right font-mono text-xs shrink-0">
                      <div className="font-bold text-white">{formatPrice(item.price)}</div>
                      <div className={item.daily_change_pct >= 0 ? 'text-emerald-400 text-[11px]' : 'text-rose-400 text-[11px]'}>
                        {formatPct(item.daily_change_pct)}
                      </div>
                    </div>
                  </div>

                  {item.earnings_within_14d && (
                    <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-600/25 border border-rose-500 text-rose-200 text-[10px] font-bold">
                      <AlertOctagon className="w-3 h-3" /> EARNINGS EM {item.days_to_earnings}D ({item.next_earnings_date})
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Right Column: Sticky Instant Chart Preview + Trade Plan + Study Card (7 cols) */}
          {selectedItem && (
            <div className="xl:col-span-7 xl:sticky xl:top-20 space-y-3">
              <div className="terminal-card p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-mono font-bold text-white">{selectedItem.ticker}</h3>
                      <span className="text-xs text-slate-400">{selectedItem.name}</span>
                      <SetupStatusBadge status={selectedItem.status} />
                      <StatusBadge variant="cyan">Score {selectedItem.score}/100</StatusBadge>
                    </div>
                    <div className="text-xs font-mono text-slate-400 mt-0.5">
                      Pivô <strong className="text-emerald-300">{formatPrice(selectedItem.trade_plan?.entry_pivot)}</strong> • Stop{' '}
                      <strong className="text-rose-400">
                        {formatPrice(selectedItem.trade_plan?.stop_loss_price)} (-{selectedItem.trade_plan?.stop_loss_pct}%)
                      </strong>{' '}
                      • 2R <strong className="text-emerald-400">{formatPrice(selectedItem.trade_plan?.target_2r)}</strong> • 3R{' '}
                      <strong className="text-cyan-300">{formatPrice(selectedItem.trade_plan?.target_3r)}</strong>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      onClick={() =>
                        onCreateAlert?.({
                          ticker: selectedItem.ticker,
                          condition: 'ABOVE',
                          target_price: selectedItem.trade_plan?.entry_pivot || selectedItem.price,
                          notes: `Pivô VCP ${selectedItem.ticker} (Score ${selectedItem.score})`,
                        })
                      }
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-medium"
                    >
                      <BellPlus className="w-3.5 h-3.5" />
                      Alerta Pivô
                    </button>
                    <button
                      onClick={() => onOpenXRay(selectedItem.ticker)}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/50 text-slate-200 font-medium"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
                      Raio-X
                    </button>
                    <button
                      onClick={() =>
                        onSimulateTrade({
                          ticker: selectedItem.ticker,
                          asset_type: selectedItem.asset_type,
                          entry_price: selectedItem.price,
                          stop_loss_pct: Math.min(selectedItem.trade_plan?.stop_loss_pct || 6.0, 6.0),
                          setup_tag: selectedItem.status === 'BREAKOUT' ? 'BREAKOUT' : 'VCP',
                          notes: `Setup ${selectedItem.status} (Score ${selectedItem.score}/100, Pivô ${selectedItem.trade_plan?.entry_pivot})`,
                        })
                      }
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      Simular
                    </button>
                  </div>
                </div>

                {/* Live Instant Candlestick Chart */}
                {previewLoading ? (
                  <div className="h-[340px] rounded-xl bg-[#0a101d] border border-terminal-border flex items-center justify-center text-xs text-slate-400">
                    A carregar gráfico de {selectedItem.ticker}...
                  </div>
                ) : previewData?.chart ? (
                  <CandlestickChart chartData={previewData.chart} ticker={selectedItem.ticker} compact />
                ) : (
                  <div className="h-[220px] rounded-xl bg-[#0a101d] border border-terminal-border flex items-center justify-center text-xs text-slate-500">
                    Pré-visualização indisponível para {selectedItem.ticker}.
                  </div>
                )}

                {/* 8 Rules Strip */}
                <div className="flex flex-wrap gap-1.5">
                  {(selectedItem.trend_template?.rules || []).map((r) => (
                    <span
                      key={r.id}
                      title={`${r.title}: ${r.detail}`}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                        r.passed
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                      }`}
                    >
                      R{r.id}: {r.passed ? 'OK' : 'FALHA'}
                    </span>
                  ))}
                </div>

                {/* Why is this an opportunity? */}
                <div className="space-y-2 pt-1">
                  <div className="text-xs font-bold text-cyan-300 inline-flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5" />
                    Porque é que isto é uma oportunidade?
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {(selectedItem.why_opportunity || []).map((w, idx) => (
                      <div
                        key={idx}
                        className={`rounded-lg p-2.5 border text-[11px] ${
                          w.tone === 'positive'
                            ? 'bg-emerald-500/5 border-emerald-500/25'
                            : w.tone === 'danger'
                              ? 'bg-rose-500/10 border-rose-500/40'
                              : w.tone === 'warning'
                                ? 'bg-amber-500/10 border-amber-500/30'
                                : 'bg-terminal-card border-terminal-border'
                        }`}
                      >
                        <div className="font-semibold text-slate-100 mb-0.5 flex items-center gap-1">
                          {w.tone === 'danger' && <ShieldAlert className="w-3 h-3 text-rose-400" />}
                          {w.topic}
                        </div>
                        <p className="text-slate-300 leading-relaxed">{w.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Classic Full-Width Cards List Mode */
        <div className="space-y-2.5">
          {filtered.map((item) => {
            const isOpen = !!expanded[item.ticker]
            const vcp = item.vcp || {}
            const plan = item.trade_plan || {}
            const tt = item.trend_template || {}
            const rs = tt.relative_strength || {}
            const contractions = (vcp.contractions_pct || []).map((c) => `${c.toFixed(0)}%`).join(' → ')

            return (
              <div
                key={item.ticker}
                className={`terminal-card transition ${
                  item.earnings_within_14d
                    ? 'border-rose-500/50'
                    : item.status === 'BREAKOUT'
                      ? 'border-emerald-500/45'
                      : 'hover:border-slate-600'
                }`}
              >
                <div className="p-4 flex flex-col xl:flex-row xl:items-center gap-4">
                  <div className="flex items-center gap-3.5 min-w-[230px]">
                    <div
                      className={`w-12 h-12 rounded-xl flex flex-col items-center justify-center font-mono font-bold border shrink-0 ${
                        item.score >= 75
                          ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                          : item.score >= 55
                            ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                            : 'bg-slate-800/70 border-slate-700 text-slate-400'
                      }`}
                    >
                      <span className="text-base leading-none">{Math.round(item.score)}</span>
                      <span className="text-[9px] opacity-70">/100</span>
                    </div>

                    <div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <button
                          onClick={() => onOpenXRay(item.ticker)}
                          className="font-mono font-bold text-base text-white hover:text-cyan-300 transition"
                        >
                          {item.ticker}
                        </button>
                        <StatusBadge variant={item.asset_type === 'crypto' ? 'purple' : 'slate'}>
                          {item.asset_type === 'crypto' ? 'CRIPTO' : 'AÇÃO'}
                        </StatusBadge>
                        <SetupStatusBadge status={item.status} />
                        {rs.rs_new_high_before_price && (
                          <span className="px-1.5 py-0.5 rounded bg-blue-500/20 border border-blue-400/50 text-blue-300 font-mono text-[10px] font-bold">
                            ● RS NEW HIGH
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate max-w-[260px]">
                        {item.name} {item.sector ? `• ${item.sector}` : ''}
                      </div>

                      {item.earnings_within_14d && (
                        <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-600/25 border border-rose-500 text-rose-300 text-[11px] font-bold">
                          <AlertOctagon className="w-3.5 h-3.5" />
                          EARNINGS EM {item.days_to_earnings}D ({item.next_earnings_date})
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 flex-1 font-mono text-xs tabular-nums">
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Preço / Dia</div>
                      <div className="font-bold text-white">{formatPrice(item.price)}</div>
                      <div className={item.daily_change_pct >= 0 ? 'text-emerald-400 text-[11px]' : 'text-rose-400 text-[11px]'}>
                        {formatPct(item.daily_change_pct)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Minervini / RS</div>
                      <div className={tt.passed ? 'text-emerald-400 font-bold' : 'text-amber-300 font-bold'}>
                        {tt.passed_count}/8 Regras
                      </div>
                      <div className="text-[11px] text-cyan-300">RS Rating: {rs.rs_rating ?? '—'}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Contrações VCP</div>
                      <div className={vcp.detected ? 'text-cyan-300 font-bold' : 'text-slate-400'}>{contractions || '—'}</div>
                      <div className="text-[11px] text-slate-400">
                        {vcp.breakout_signal ? `Vol ${vcp.breakout_volume_ratio}x ⚡` : vcp.volume_dry_up ? `VDU ${vcp.vdu_ratio}x ✓` : `Vol ${vcp.breakout_volume_ratio ?? '—'}x`}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Pivô Sugerido</div>
                      <div className="text-emerald-300 font-bold">{formatPrice(plan.entry_pivot)}</div>
                      <div className="text-[11px] text-slate-400">Dist: {formatPct(vcp.distance_to_pivot_pct)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Stop Máx (≤6%)</div>
                      <div className="text-rose-400 font-bold">{formatPrice(plan.stop_loss_price)}</div>
                      <div className="text-[11px] text-rose-300/80">-{plan.stop_loss_pct}% risco</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500 font-sans">Alvos 2R / 3R</div>
                      <div className="text-emerald-400 font-semibold">2R: {formatPrice(plan.target_2r)}</div>
                      <div className="text-cyan-300 text-[11px]">3R: {formatPrice(plan.target_3r)}</div>
                    </div>
                  </div>

                  <div className="flex flex-wrap xl:flex-col items-stretch gap-1.5 shrink-0">
                    <button
                      onClick={() => onOpenXRay(item.ticker)}
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/60 text-slate-200 transition"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
                      Raio-X
                    </button>
                    <button
                      onClick={() =>
                        onSimulateTrade({
                          ticker: item.ticker,
                          asset_type: item.asset_type,
                          entry_price: item.price,
                          stop_loss_pct: Math.min(plan.stop_loss_pct || 6.0, 6.0),
                          setup_tag: item.status === 'BREAKOUT' ? 'BREAKOUT' : 'VCP',
                          notes: `Setup ${item.status} (Score ${item.score}/100, Pivô ${plan.entry_pivot})`,
                        })
                      }
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 transition"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      Simular Entrada
                    </button>
                  </div>
                </div>

                <div className="border-t border-terminal-border/70 px-4 py-2 bg-[#0a101d]/60 rounded-b-xl">
                  <button
                    onClick={() => toggleExpand(item.ticker)}
                    className="w-full flex items-center justify-between text-xs text-cyan-300 hover:text-cyan-200 font-medium py-0.5"
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5" />
                      Porque é que isto é uma oportunidade? (Dicas + Estudo SEPA/VCP)
                    </span>
                    {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>

                  {isOpen && (
                    <div className="mt-3 pb-2 grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      {(item.why_opportunity || []).map((w, idx) => (
                        <div
                          key={idx}
                          className={`rounded-lg p-3 border text-xs ${
                            w.tone === 'positive'
                              ? 'bg-emerald-500/5 border-emerald-500/25'
                              : w.tone === 'danger'
                                ? 'bg-rose-500/10 border-rose-500/40'
                                : w.tone === 'warning'
                                  ? 'bg-amber-500/10 border-amber-500/30'
                                  : 'bg-terminal-card border-terminal-border'
                          }`}
                        >
                          <div className="font-semibold text-slate-100 mb-1">{w.topic}</div>
                          <p className="text-slate-300 leading-relaxed">{w.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Watchlist Config Modal */}
      {showWatchlist && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="terminal-card w-full max-w-2xl max-h-[82vh] flex flex-col overflow-hidden">
            <div className="px-5 py-3.5 border-b border-terminal-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">Configurar Watchlist do Scanner</h3>
                <p className="text-[11px] text-slate-400">Adiciona ou remove ações e criptomoedas rastreadas automaticamente.</p>
              </div>
              <button
                onClick={() => setShowWatchlist(false)}
                className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-terminal-card"
              >
                Fechar
              </button>
            </div>

            <form onSubmit={handleAddTicker} className="p-4 border-b border-terminal-border flex flex-wrap gap-2">
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                placeholder="Ex: RKLB, HIMS, SOL-USD..."
                className="flex-1 px-3 py-1.5 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
              />
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="px-3 py-1.5 text-xs bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
              >
                <option value="stock">Ação</option>
                <option value="crypto">Cripto</option>
              </select>
              <button
                type="submit"
                className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30"
              >
                <Plus className="w-3.5 h-3.5" />
                Adicionar
              </button>
            </form>

            <div className="p-4 overflow-y-auto flex-1 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {watchlist.map((w) => (
                <div
                  key={w.ticker}
                  className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#070b14] border border-terminal-border text-xs"
                >
                  <div>
                    <span className="font-mono font-semibold text-slate-200">{w.ticker}</span>
                    <span className="ml-1.5 text-[10px] text-slate-500 uppercase">{w.asset_type}</span>
                  </div>
                  <button
                    onClick={() => handleRemoveTicker(w.ticker)}
                    className="text-slate-500 hover:text-rose-400 transition"
                    title="Remover"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
