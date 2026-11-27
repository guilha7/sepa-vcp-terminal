import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertOctagon,
  BellPlus,
  Columns2,
  ExternalLink,
  Globe2,
  Keyboard,
  Lock,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Star,
  Trash2,
  Zap,
} from 'lucide-react'
import { api, formatPct, formatPrice, formatTimestamp } from '../services/api'
import { CandlestickChart } from '../components/CandlestickChart'
import { SetupStatusBadge, StatusBadge } from '../components/StatusBadge'
import { StrategySelector } from '../components/StrategySelector'
import { WarningBanner } from '../components/WarningBanner'

const US_PRESETS = [
  { id: 'sepa_leaders', label: 'EUA: Líderes Stage 2', hint: 'Top Stage 2 entre ~7.000 ações NYSE/NASDAQ' },
  { id: 'small_mid_growth', label: 'EUA: Joias Small & Mid-Cap', hint: 'Empresas $300M–$15B em forte tendência' },
  { id: 'volume_breakouts', label: 'EUA: Explosão Volume Hoje', hint: 'Vol ≥ 1.5x média e alta forte' },
  { id: 'near_52w_high', label: 'EUA: Top Força 1 Ano', hint: 'Maiores vencedoras anuais Stage 2' },
  { id: 'eu_leaders', label: 'Europa: Líderes (EUR)', hint: 'DAX, CAC, AEX, IBEX, Itália e Lisboa' },
  { id: 'portugal_psi', label: 'Portugal: Lisboa (PSI)', hint: 'EDP, Galp, Sonae, NOS, BCP, Jerónimo Martins...' },
]

function strategyScore(item, strategy) {
  const q = item.quant || {}
  if (strategy === 'qullamaggie') {
    let s = Number(q.adr_pct_20d || 0) * 6
    if (q.episodic_pivot?.detected) s += 45
    if (q.high_tight_flag?.detected) s += 45
    if (item.trend_template?.passed) s += 20
    if (q.is_atr_overextended) s -= 20
    return s
  }
  if (strategy === 'institutional') {
    let s = Number(item.trend_template?.relative_strength?.rs_rating || 50) * 0.5
    if (q.pocket_pivot?.detected) s += 35
    if (q.three_weeks_tight?.detected) s += 25
    if (q.canslim?.score !== null && q.canslim?.score !== undefined) s += Number(q.canslim.score) * 0.4
    return s
  }
  if (strategy === 'weinstein_squeeze') {
    let s = Number(q.mansfield_rs || 0) * 2
    if (q.weinstein?.stage === 2) s += 35
    if (q.ttm_squeeze?.squeeze_fire_long) s += 40
    else if (q.ttm_squeeze?.squeeze_on) s += 25
    return s
  }
  return Number(item.score || 0)
}

export function ScannerModule({
  onOpenXRay,
  onSimulateTrade,
  onCreateAlert,
  favorites = [],
  onToggleFavorite,
  activeStrategy = 'minervini',
  onChangeStrategy,
  isAdmin = true,
}) {
  const [scanMode, setScanMode] = useState('watchlist') // watchlist | us_all
  const [usPreset, setUsPreset] = useState('sepa_leaders')
  const [watchlistData, setWatchlistData] = useState(null)
  const [usDiscoveryData, setUsDiscoveryData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(null)
  const [error, setError] = useState(null)

  const data = scanMode === 'us_all' ? usDiscoveryData : watchlistData

  // Filters & Layout
  const [assetFilter, setAssetFilter] = useState('all')
  const [stageFilter, setStageFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [splitMode, setSplitMode] = useState(true)
  const [selectedTicker, setSelectedTicker] = useState(null)

  // Quick Chart cache
  const [previewData, setPreviewData] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const chartCacheRef = useRef({})
  const sseCloseRef = useRef(null)

  // Watchlist modal
  const [showWatchlist, setShowWatchlist] = useState(false)
  const [watchlist, setWatchlist] = useState([])
  const [newTicker, setNewTicker] = useState('')
  const [newType, setNewType] = useState('stock')

  const handleStrategyChange = (nextStrategy) => {
    setStageFilter('all')
    onChangeStrategy?.(nextStrategy)
  }

  const loadCachedResults = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await api.getScannerResults('', false, true)
      if (res?.cache_empty || !(res?.opportunities || []).length) {
        setLoading(false)
        startStreamingScan(false)
        return
      }
      setWatchlistData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const startStreamingScan = (forceRefresh = true) => {
    if (sseCloseRef.current) sseCloseRef.current()
    setScanning(true)
    setError(null)
    setScanProgress({
      pct: 4,
      current: 0,
      total: 90,
      ticker: forceRefresh ? 'A iniciar...' : 'Primeiro scan após arranque...',
      stage: forceRefresh ? 'A ligar ao servidor...' : 'A aquecer cache inicial (próximas aberturas serão instantâneas)',
    })
    sseCloseRef.current = api.streamScanner('', {
      forceRefresh,
      onProgress: (p) => setScanProgress(p),
      onComplete: (res) => {
        chartCacheRef.current = {}
        setWatchlistData(res)
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

  const startUsDiscoveryScan = (presetId = usPreset, forceRefresh = false) => {
    if (sseCloseRef.current) sseCloseRef.current()
    setUsPreset(presetId)
    setScanMode('us_all')
    setAssetFilter('all')
    setStageFilter('all')
    setScanning(true)
    setError(null)
    setScanProgress({
      pct: 3,
      current: 0,
      total: 100,
      ticker: 'Mercado',
      stage: 'Fase 1: A filtrar mercado selecionado...',
    })
    sseCloseRef.current = api.streamUsDiscovery(presetId, 45, forceRefresh, {
      onProgress: (p) => setScanProgress(p),
      onComplete: (res) => {
        chartCacheRef.current = {}
        setUsDiscoveryData(res)
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

  const favoriteSet = useMemo(() => new Set((favorites || []).map((t) => t.toUpperCase())), [favorites])
  const rawItems = data?.opportunities || []

  const favoritesInScanCount = useMemo(
    () => rawItems.filter((item) => favoriteSet.has(item.ticker.toUpperCase())).length,
    [rawItems, favoriteSet],
  )

  // Strategy-exclusive filter pills (ZERO filters from other strategies!)
  const strategyFilterPills = useMemo(() => {
    if (activeStrategy === 'qullamaggie') {
      const epC = rawItems.filter((i) => i.quant?.episodic_pivot?.detected).length
      const htfC = rawItems.filter((i) => i.quant?.high_tight_flag?.detected).length
      const adrC = rawItems.filter((i) => (i.quant?.adr_pct_20d || 0) >= 4.0).length
      return [
        { k: 'all', l: 'Todos' },
        { k: 'ep', l: `Episodic Pivot (${epC})` },
        { k: 'htf', l: `High Tight Flag (${htfC})` },
        { k: 'adr4', l: `ADR ≥ 4% (${adrC})` },
        { k: 'favorites', l: `★ Favoritos (${favoritesInScanCount})` },
      ]
    }
    if (activeStrategy === 'institutional') {
      const ppC = rawItems.filter((i) => i.quant?.pocket_pivot?.detected).length
      const wt3C = rawItems.filter((i) => i.quant?.three_weeks_tight?.detected).length
      const csC = rawItems.filter((i) => ['A', 'B'].includes(i.quant?.canslim?.grade)).length
      return [
        { k: 'all', l: 'Todos' },
        { k: 'pocket', l: `Pocket Pivot (${ppC})` },
        { k: 'wt3', l: `3 Weeks Tight (${wt3C})` },
        { k: 'canslim_ab', l: `CAN SLIM A/B (${csC})` },
        { k: 'favorites', l: `★ Favoritos (${favoritesInScanCount})` },
      ]
    }
    if (activeStrategy === 'weinstein_squeeze') {
      const s2C = rawItems.filter((i) => i.quant?.weinstein?.stage === 2).length
      const sqOn = rawItems.filter((i) => i.quant?.ttm_squeeze?.squeeze_on).length
      const sqFire = rawItems.filter((i) => i.quant?.ttm_squeeze?.squeeze_fire_long).length
      return [
        { k: 'all', l: 'Todos' },
        { k: 'weinstein_s2', l: `Stage 2 (${s2C})` },
        { k: 'squeeze_on', l: `Squeeze ON (${sqOn})` },
        { k: 'squeeze_fire', l: `Squeeze FIRE (${sqFire})` },
        { k: 'favorites', l: `★ Favoritos (${favoritesInScanCount})` },
      ]
    }
    // Default: Minervini SEPA / VCP
    const s2C = rawItems.filter((i) => i.trend_template?.passed).length
    const vcpC = rawItems.filter((i) => i.vcp?.detected || i.vcp?.breakout_signal).length
    const brkC = rawItems.filter((i) => i.status === 'BREAKOUT').length
    const rsC = rawItems.filter((i) => i.trend_template?.relative_strength?.rs_new_high_before_price).length
    return [
      { k: 'all', l: 'Todos' },
      { k: 'stage2', l: `Stage 2 (${s2C})` },
      { k: 'vcp', l: `VCP (${vcpC})` },
      { k: 'breakout', l: `Breakout (${brkC})` },
      { k: 'rs_nh', l: `RS New High (${rsC})` },
      { k: 'favorites', l: `★ Favoritos (${favoritesInScanCount})` },
    ]
  }, [activeStrategy, rawItems, favoritesInScanCount])

  const filtered = useMemo(() => {
    const out = rawItems.filter((item) => {
      if (assetFilter !== 'all' && item.asset_type !== assetFilter) return false
      if (stageFilter === 'favorites' && !favoriteSet.has(item.ticker.toUpperCase())) return false
      // Minervini filters
      if (stageFilter === 'stage2' && !item.trend_template?.passed) return false
      if (stageFilter === 'vcp' && !item.vcp?.detected && !item.vcp?.breakout_signal) return false
      if (stageFilter === 'breakout' && item.status !== 'BREAKOUT') return false
      if (stageFilter === 'rs_nh' && !item.trend_template?.relative_strength?.rs_new_high_before_price) return false
      // Qullamaggie filters
      if (stageFilter === 'ep' && !item.quant?.episodic_pivot?.detected) return false
      if (stageFilter === 'htf' && !item.quant?.high_tight_flag?.detected) return false
      if (stageFilter === 'adr4' && (item.quant?.adr_pct_20d || 0) < 4.0) return false
      // Institutional filters
      if (stageFilter === 'pocket' && !item.quant?.pocket_pivot?.detected) return false
      if (stageFilter === 'wt3' && !item.quant?.three_weeks_tight?.detected) return false
      if (stageFilter === 'canslim_ab' && !['A', 'B'].includes(item.quant?.canslim?.grade)) return false
      // Weinstein & Squeeze filters
      if (stageFilter === 'weinstein_s2' && item.quant?.weinstein?.stage !== 2) return false
      if (stageFilter === 'squeeze_on' && !item.quant?.ttm_squeeze?.squeeze_on) return false
      if (stageFilter === 'squeeze_fire' && !item.quant?.ttm_squeeze?.squeeze_fire_long) return false

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
    return out.sort((a, b) => strategyScore(b, activeStrategy) - strategyScore(a, activeStrategy))
  }, [rawItems, assetFilter, stageFilter, query, favoriteSet, activeStrategy])

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

  const renderStrategyRowBadge = (item) => {
    const q = item.quant || {}
    if (activeStrategy === 'qullamaggie') {
      if (q.episodic_pivot?.detected) return <StatusBadge variant="green">EP +{q.episodic_pivot.gap_pct}%</StatusBadge>
      if (q.high_tight_flag?.detected) return <StatusBadge variant="cyan">HTF</StatusBadge>
      return (
        <StatusBadge variant={(q.adr_pct_20d || 0) >= 4 ? 'cyan' : 'slate'}>
          ADR {q.adr_pct_20d ?? '—'}%
        </StatusBadge>
      )
    }
    if (activeStrategy === 'institutional') {
      if (q.pocket_pivot?.detected) return <StatusBadge variant="green">POCKET PIVOT</StatusBadge>
      if (q.three_weeks_tight?.detected) return <StatusBadge variant="purple">3 WEEKS TIGHT</StatusBadge>
      return <StatusBadge variant="slate">CAN SLIM {q.canslim?.grade || '—'}</StatusBadge>
    }
    if (activeStrategy === 'weinstein_squeeze') {
      if (q.ttm_squeeze?.squeeze_fire_long) return <StatusBadge variant="green">SQUEEZE FIRE</StatusBadge>
      if (q.ttm_squeeze?.squeeze_on) return <StatusBadge variant="yellow">SQUEEZE ON ({q.ttm_squeeze.squeeze_bars}d)</StatusBadge>
      return (
        <StatusBadge variant={q.weinstein?.stage === 2 ? 'green' : q.weinstein?.stage === 4 ? 'red' : 'slate'}>
          Stage {q.weinstein?.stage || '—'}
        </StatusBadge>
      )
    }
    return <SetupStatusBadge status={item.status} />
  }

  const renderStrategyRowSubline = (item) => {
    const q = item.quant || {}
    const tt = item.trend_template || {}
    const rs = tt.relative_strength || {}
    const vcp = item.vcp || {}
    if (activeStrategy === 'qullamaggie') {
      return `ADR ${q.adr_pct_20d ?? '—'}%/dia • Ext. SMA50: ${q.atr_extension_sma50 ?? '—'}x ATR`
    }
    if (activeStrategy === 'institutional') {
      return `CAN SLIM ${q.canslim?.grade || '—'} (${q.canslim?.score ?? '—'}) • RS ${rs.rs_rating ?? '—'}/99`
    }
    if (activeStrategy === 'weinstein_squeeze') {
      const mrs = q.mansfield_rs !== null && q.mansfield_rs !== undefined ? `${q.mansfield_rs >= 0 ? '+' : ''}${q.mansfield_rs}` : '—'
      return `Fase ${q.weinstein?.stage || '—'} • Mansfield RS ${mrs} • ${q.ttm_squeeze?.state?.replace('_', ' ') || 'Sem Squeeze'}`
    }
    const cStr = (vcp.contractions_pct || []).map((c) => `${c.toFixed(0)}%`).join('→')
    return `${tt.passed_count}/8 Stage 2 • RS ${rs.rs_rating ?? '—'}${cStr ? ` • VCP ${cStr}` : ''}`
  }

  const renderPreviewStrategyBox = (item) => {
    const q = item.quant || {}
    const tt = item.trend_template || {}
    const plan = item.trade_plan || {}

    if (activeStrategy === 'qullamaggie') {
      return (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">ADR% (20d)</div>
            <div className="font-bold text-cyan-300 mt-0.5">{q.adr_pct_20d ?? '—'}%/dia</div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Extensão SMA50</div>
            <div className={`font-bold mt-0.5 ${q.is_atr_overextended ? 'text-rose-400' : 'text-emerald-400'}`}>
              {q.atr_extension_sma50 ?? '—'}x ATR
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Episodic Pivot</div>
            <div className={`font-bold mt-0.5 ${q.episodic_pivot?.detected ? 'text-emerald-400' : 'text-slate-400'}`}>
              {q.episodic_pivot?.detected ? `SIM (+${q.episodic_pivot.gap_pct}%)` : 'Não'}
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">High Tight Flag</div>
            <div className={`font-bold mt-0.5 ${q.high_tight_flag?.detected ? 'text-cyan-300' : 'text-slate-400'}`}>
              {q.high_tight_flag?.detected ? `SIM (+${q.high_tight_flag.pole_gain_pct}%)` : 'Não'}
            </div>
          </div>
        </div>
      )
    }

    if (activeStrategy === 'institutional') {
      return (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Pocket Pivot (10d)</div>
            <div className={`font-bold mt-0.5 ${q.pocket_pivot?.detected ? 'text-emerald-400' : 'text-slate-400'}`}>
              {q.pocket_pivot?.detected ? `SIM (${q.pocket_pivot.vol_vs_max_down}x)` : 'Não'}
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">3 Weeks Tight</div>
            <div className={`font-bold mt-0.5 ${q.three_weeks_tight?.detected ? 'text-purple-300' : 'text-slate-400'}`}>
              {q.three_weeks_tight?.detected ? 'SIM' : 'Não'}
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">CAN SLIM</div>
            <div className="font-bold text-purple-300 mt-0.5">
              {q.canslim?.score !== null && q.canslim?.score !== undefined ? `${q.canslim.grade} (${q.canslim.score})` : 'N/A'}
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">RS Rating</div>
            <div className="font-bold text-cyan-300 mt-0.5">{tt.relative_strength?.rs_rating ?? '—'}/99</div>
          </div>
        </div>
      )
    }

    if (activeStrategy === 'weinstein_squeeze') {
      return (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono">
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Fase Weinstein</div>
            <div className={`font-bold mt-0.5 ${q.weinstein?.stage === 2 ? 'text-emerald-400' : q.weinstein?.stage === 4 ? 'text-rose-400' : 'text-amber-300'}`}>
              Stage {q.weinstein?.stage || '—'} ({q.weinstein?.label || '—'})
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">TTM Squeeze</div>
            <div className={`font-bold mt-0.5 ${q.ttm_squeeze?.squeeze_fire_long ? 'text-emerald-400' : q.ttm_squeeze?.squeeze_on ? 'text-amber-300' : 'text-slate-400'}`}>
              {q.ttm_squeeze?.state?.replace('_', ' ') || 'NEUTRO'}
            </div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Mansfield RS</div>
            <div className={`font-bold mt-0.5 ${(q.mansfield_rs || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {q.mansfield_rs !== null && q.mansfield_rs !== undefined ? `${q.mansfield_rs >= 0 ? '+' : ''}${q.mansfield_rs}` : '—'}
            </div>
          </div>
        </div>
      )
    }

    // Default: Minervini SEPA / VCP
    return (
      <div className="space-y-2.5">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Pivô VCP</div>
            <div className="font-bold text-emerald-300 mt-0.5">{formatPrice(plan.entry_pivot)}</div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-rose-500/25 p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Stop (-{plan.stop_loss_pct}%)</div>
            <div className="font-bold text-rose-400 mt-0.5">{formatPrice(plan.stop_loss_price)}</div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Alvo 2R</div>
            <div className="font-bold text-emerald-400 mt-0.5">{formatPrice(plan.target_2r)}</div>
          </div>
          <div className="rounded-lg bg-[#080e1c] border border-terminal-border p-2.5">
            <div className="text-[10px] font-sans text-slate-400">Alvo 3R</div>
            <div className="font-bold text-cyan-300 mt-0.5">{formatPrice(plan.target_3r)}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(tt.rules || []).map((r) => (
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
      </div>
    )
  }

  if (loading && !data && !scanning) {
    return (
      <div className="terminal-card p-10 text-center space-y-3">
        <div className="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-slate-200 font-medium">A carregar Scanner...</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="heading-hero">Scanner de Setups</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Último scan: {formatTimestamp(data?.scanned_at)} • Usa as setas ↑↓ para percorrer e Enter para abrir o Raio-X.
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
            Gráfico ao Lado
          </button>
          <button
            onClick={handleOpenWatchlist}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-terminal-panel border border-terminal-border hover:border-cyan-500/50 text-slate-200 transition"
          >
            <Settings2 className="w-3.5 h-3.5 text-cyan-400" />
            Watchlist
          </button>
          <button
            onClick={() => (scanMode === 'us_all' ? startUsDiscoveryScan(usPreset, true) : startStreamingScan(true))}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'A analisar...' : 'Atualizar Scan'}
          </button>
        </div>
      </div>

      {/* Single Active Strategy Selector (Zero Cross-Strategy Noise!) */}
      <StrategySelector activeStrategy={activeStrategy} onChange={handleStrategyChange} />

      {/* Universe Switcher: Watchlist vs US (~7,000) & Europe / Portugal */}
      <div className="terminal-card p-3 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded-xl bg-[#060a13] border border-terminal-border p-1 text-xs">
            <button
              onClick={() => setScanMode('watchlist')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                scanMode === 'watchlist'
                  ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Watchlist (Ações + Cripto)
            </button>
            <button
              onClick={() => {
                setScanMode('us_all')
                if (!usDiscoveryData && !scanning) startUsDiscoveryScan(usPreset, false)
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold transition ${
                scanMode === 'us_all'
                  ? 'bg-gradient-to-r from-emerald-500/25 to-cyan-500/25 text-emerald-200 border border-emerald-400/50'
                  : 'text-slate-300 hover:text-emerald-200'
              }`}
            >
              <Globe2 className="w-3.5 h-3.5 text-emerald-400" />
              Descobrir EUA (~7.000) &amp; Europa / PT
            </button>
          </div>

          {scanMode === 'us_all' && usDiscoveryData?.discovery_meta && (
            <span className="text-[11px] font-mono text-emerald-300">
              {usDiscoveryData.discovery_meta.total_matched_stage1} ações na Fase 1 • {usDiscoveryData.discovery_meta.new_outside_watchlist_count} novas
            </span>
          )}
        </div>

        {scanMode === 'us_all' && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-terminal-border/60">
            <span className="text-[11px] text-slate-400 inline-flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              Mercado:
            </span>
            {US_PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => startUsDiscoveryScan(p.id, false)}
                disabled={scanning}
                title={p.hint}
                className={`px-2.5 py-1 rounded-lg text-xs border transition ${
                  usPreset === p.id
                    ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200 font-semibold'
                    : 'bg-[#070b14] border-terminal-border text-slate-300 hover:border-emerald-500/40'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
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

      {/* Clean Filters Bar (Strictly ONLY Active Strategy Filters) */}
      <div className="terminal-card p-3 flex flex-wrap items-center gap-2.5">
        {scanMode === 'watchlist' && (
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
        )}

        <div className="inline-flex flex-wrap rounded-xl bg-[#060a13] border border-terminal-border p-0.5 text-xs">
          {strategyFilterPills.map((o) => (
            <button
              key={o.k}
              onClick={() => setStageFilter(o.k)}
              className={`px-2.5 py-1 rounded-lg transition ${
                stageFilter === o.k
                  ? o.k === 'favorites'
                    ? 'bg-amber-500/20 text-amber-200 font-semibold'
                    : 'bg-emerald-500/20 text-emerald-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
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
          placeholder="Filtrar ticker..."
          className="px-3 py-1.5 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/60"
        />

        <span className="text-[11px] font-mono text-slate-400 ml-auto">
          <strong className="text-white">{filtered.length}</strong>/{rawItems.length}
        </span>

        {splitMode && (
          <span className="hidden lg:inline-flex items-center gap-1 text-[10px] font-mono text-slate-500">
            <Keyboard className="w-3.5 h-3.5 text-cyan-500" /> ↑↓ • Enter
          </span>
        )}
      </div>

      {/* Personal Favorites Quick Jump Bar */}
      {favorites.length > 0 && (
        <div className="terminal-card px-3.5 py-2 flex flex-wrap items-center gap-2 border-amber-500/25">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber-300 shrink-0">
            <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
            Favoritos:
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {favorites.map((tk) => (
              <button
                key={tk}
                onClick={() => onOpenXRay(tk)}
                className="px-2.5 py-0.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-200 font-mono text-[11px] font-semibold transition"
              >
                {tk}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results Area */}
      {filtered.length === 0 ? (
        <div className="terminal-card p-8 text-center text-sm text-slate-400">
          Nenhum ativo encontrado para este filtro na estratégia selecionada.
        </div>
      ) : splitMode ? (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
          {/* Left Compact List (5 cols) */}
          <div className="xl:col-span-5 space-y-2 max-h-[72vh] overflow-y-auto pr-1">
            {filtered.map((item) => {
              const active = selectedItem?.ticker === item.ticker
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
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          onToggleFavorite?.(item.ticker)
                        }}
                        className="p-1 rounded hover:bg-amber-500/15 text-slate-500 hover:text-amber-300 transition shrink-0"
                        title="Favoritar"
                      >
                        <Star
                          className={`w-3.5 h-3.5 ${
                            favoriteSet.has(item.ticker.toUpperCase()) ? 'fill-amber-400 text-amber-400' : ''
                          }`}
                        />
                      </button>

                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-mono font-bold text-sm text-white">{item.ticker}</span>
                          {item.is_new_discovery && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 font-mono text-[9px] font-bold">
                              NOVA
                            </span>
                          )}
                          {renderStrategyRowBadge(item)}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate mt-0.5">
                          {renderStrategyRowSubline(item)}
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

          {/* Right Sticky Clean Preview (7 cols) */}
          {selectedItem && (
            <div className="xl:col-span-7 xl:sticky xl:top-20 space-y-3">
              <div className="terminal-card p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-mono font-bold text-white">{selectedItem.ticker}</h3>
                      <span className="text-xs text-slate-400 truncate max-w-[200px]">{selectedItem.name}</span>
                      {renderStrategyRowBadge(selectedItem)}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      onClick={() => onToggleFavorite?.(selectedItem.ticker)}
                      className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border font-medium transition ${
                        favoriteSet.has(selectedItem.ticker.toUpperCase())
                          ? 'bg-amber-500/20 border-amber-400/50 text-amber-200'
                          : 'bg-terminal-card border-terminal-border hover:border-amber-400/40 text-slate-300'
                      }`}
                    >
                      <Star
                        className={`w-3.5 h-3.5 ${
                          favoriteSet.has(selectedItem.ticker.toUpperCase()) ? 'fill-amber-400 text-amber-400' : ''
                        }`}
                      />
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() =>
                          onCreateAlert?.({
                            ticker: selectedItem.ticker,
                            condition: 'ABOVE',
                            target_price: selectedItem.trade_plan?.entry_pivot || selectedItem.price,
                            notes: `Alerta Pivô ${selectedItem.ticker}`,
                          })
                        }
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-medium"
                      >
                        <BellPlus className="w-3.5 h-3.5" />
                        Alerta
                      </button>
                    )}
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
                          asset_currency: /\.(LS|DE|PA|AS|MC|MI)$/i.test(selectedItem.ticker || '') ? 'EUR' : 'USD',
                          entry_price: selectedItem.price,
                          stop_loss_pct: Math.min(selectedItem.trade_plan?.stop_loss_pct || 6.0, 6.0),
                          setup_tag: activeStrategy === 'minervini' ? 'VCP' : activeStrategy.toUpperCase(),
                          notes: `Setup ${selectedItem.ticker} (${activeStrategy})`,
                        })
                      }
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      Simular
                    </button>
                  </div>
                </div>

                {/* Live Chart synced ONLY to Active Strategy */}
                {previewLoading ? (
                  <div className="h-[300px] rounded-xl bg-[#0a101d] border border-terminal-border flex items-center justify-center text-xs text-slate-400">
                    A carregar gráfico de {selectedItem.ticker}...
                  </div>
                ) : previewData?.chart ? (
                  <CandlestickChart
                    chartData={previewData.chart}
                    ticker={selectedItem.ticker}
                    strategy={activeStrategy}
                    compact
                  />
                ) : (
                  <div className="h-[220px] rounded-xl bg-[#0a101d] border border-terminal-border flex items-center justify-center text-xs text-slate-500">
                    Pré-visualização indisponível para {selectedItem.ticker}.
                  </div>
                )}

                {/* Active Strategy-Only Metrics Box */}
                {renderPreviewStrategyBox(selectedItem)}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Clean Full-Width List Mode */
        <div className="space-y-2">
          {filtered.map((item) => (
            <div
              key={item.ticker}
              className="terminal-card p-3.5 flex flex-wrap items-center justify-between gap-3 hover:border-slate-600 transition"
            >
              <div className="flex items-center gap-3 min-w-[220px]">
                <button
                  type="button"
                  onClick={() => onToggleFavorite?.(item.ticker)}
                  className="p-1 rounded hover:bg-amber-500/15 text-slate-500 hover:text-amber-300"
                >
                  <Star
                    className={`w-4 h-4 ${
                      favoriteSet.has(item.ticker.toUpperCase()) ? 'fill-amber-400 text-amber-400' : ''
                    }`}
                  />
                </button>
                <div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      onClick={() => onOpenXRay(item.ticker)}
                      className="font-mono font-bold text-base text-white hover:text-cyan-300"
                    >
                      {item.ticker}
                    </button>
                    {item.is_new_discovery && (
                      <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 font-mono text-[10px] font-bold">
                        NOVA
                      </span>
                    )}
                    {renderStrategyRowBadge(item)}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{renderStrategyRowSubline(item)}</div>
                </div>
              </div>

              <div className="flex items-center gap-4 font-mono text-xs">
                <div className="text-right">
                  <div className="font-bold text-white">{formatPrice(item.price)}</div>
                  <div className={item.daily_change_pct >= 0 ? 'text-emerald-400 text-[11px]' : 'text-rose-400 text-[11px]'}>
                    {formatPct(item.daily_change_pct)}
                  </div>
                </div>
                <button
                  onClick={() => onOpenXRay(item.ticker)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-terminal-card border border-terminal-border hover:border-cyan-500/60 text-slate-200 font-sans font-medium"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
                  Raio-X
                </button>
                <button
                  onClick={() =>
                    onSimulateTrade({
                      ticker: item.ticker,
                      asset_type: item.asset_type,
                      asset_currency: /\.(LS|DE|PA|AS|MC|MI)$/i.test(item.ticker || '') ? 'EUR' : 'USD',
                      entry_price: item.price,
                      stop_loss_pct: Math.min(item.trade_plan?.stop_loss_pct || 6.0, 6.0),
                      setup_tag: activeStrategy === 'minervini' ? 'VCP' : activeStrategy.toUpperCase(),
                      notes: `Setup ${item.ticker}`,
                    })
                  }
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-sans font-semibold"
                >
                  <Zap className="w-3.5 h-3.5" />
                  Simular
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Watchlist Config Modal */}
      {showWatchlist && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="terminal-card w-full max-w-2xl max-h-[82vh] flex flex-col overflow-hidden">
            <div className="px-5 py-3.5 border-b border-terminal-border flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white">Watchlist do Scanner</h3>
                <p className="text-[11px] text-slate-400">Lista base analisada automaticamente pelo Scanner.</p>
              </div>
              <button
                onClick={() => setShowWatchlist(false)}
                className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-terminal-card"
              >
                Fechar
              </button>
            </div>

            {isAdmin ? (
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
            ) : (
              <div className="p-3.5 border-b border-terminal-border bg-amber-500/10 text-xs text-amber-200 flex items-center gap-2">
                <Lock className="w-4 h-4 text-amber-300 shrink-0" />
                <span>A Watchlist global é gerida pelo administrador. Usa a estrela ★ para os teus Favoritos!</span>
              </div>
            )}

            <div className="p-4 overflow-y-auto flex-1 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {watchlist.map((w) => (
                <div
                  key={w.ticker}
                  className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#070b14] border border-terminal-border text-xs"
                >
                  <button
                    type="button"
                    onClick={() => {
                      setShowWatchlist(false)
                      onOpenXRay(w.ticker)
                    }}
                    className="text-left hover:text-cyan-300 transition"
                  >
                    <span className="font-mono font-semibold text-slate-200">{w.ticker}</span>
                    <span className="ml-1.5 text-[10px] text-slate-500 uppercase">{w.asset_type}</span>
                  </button>
                  {isAdmin ? (
                    <button
                      onClick={() => handleRemoveTicker(w.ticker)}
                      className="text-slate-500 hover:text-rose-400 transition"
                      title="Remover"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  ) : (
                    <button
                      onClick={() => onToggleFavorite?.(w.ticker)}
                      className="text-slate-500 hover:text-amber-300 transition"
                    >
                      <Star
                        className={`w-3.5 h-3.5 ${
                          favoriteSet.has(w.ticker.toUpperCase()) ? 'fill-amber-400 text-amber-400' : ''
                        }`}
                      />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
