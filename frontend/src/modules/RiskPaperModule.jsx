import React, { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRightLeft,
  Bell,
  BookOpen,
  Calculator,
  ExternalLink,
  Lock,
  NotebookPen,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Zap,
} from 'lucide-react'
import { api, formatPct, formatPrice, formatTimestamp } from '../services/api'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { StatusBadge } from '../components/StatusBadge'
import { WarningBanner } from '../components/WarningBanner'

const SETUP_TAGS = ['VCP', 'BREAKOUT', 'STAGE2_PULLBACK', 'POCKET_PIVOT', 'FOMO', 'OUTRO']
const EMOTION_TAGS = ['DISCIPLINADO', 'CONFIANTE', 'ANSIOSO', 'FOMO', 'IMPULSIVO']

export function RiskPaperModule({
  prefillTrade,
  onClearPrefill,
  onOpenXRay,
  defaultCapitalEur = 100,
  defaultStopLossPct = 6.0,
  defaultRiskPct = 2.0,
}) {
  // Calculator state (synced with Personal Preferences / Settings defaults, hard ceiling 7%, live EUR/USD conversion!)
  const [ticker, setTicker] = useState('NVDA')
  const [assetType, setAssetType] = useState('stock')
  const [assetCurrency, setAssetCurrency] = useState('USD')
  const [fxRate, setFxRate] = useState(1.08)
  const [capitalEur, setCapitalEur] = useState(defaultCapitalEur)
  const [entryPrice, setEntryPrice] = useState(140)
  const [stopLossPct, setStopLossPct] = useState(defaultStopLossPct)
  const [sizingMode, setSizingMode] = useState('capital_allocation')
  const [riskPctAccount, setRiskPctAccount] = useState(defaultRiskPct)

  useEffect(() => {
    setCapitalEur(defaultCapitalEur)
  }, [defaultCapitalEur])

  useEffect(() => {
    setStopLossPct(Math.min(defaultStopLossPct, 7.0))
  }, [defaultStopLossPct])

  useEffect(() => {
    setRiskPctAccount(defaultRiskPct)
  }, [defaultRiskPct])
  const [customTarget, setCustomTarget] = useState('')
  const [allowFractional, setAllowFractional] = useState(true)

  // Minervini active exit + Journal fields
  const [autoManage2R, setAutoManage2R] = useState(true)
  const [trailingMode, setTrailingMode] = useState('NONE') // NONE | SMA10 | SMA21
  const [setupTag, setSetupTag] = useState('VCP')
  const [journalEmotion, setJournalEmotion] = useState('DISCIPLINADO')
  const [notes, setNotes] = useState('')

  const [calcResult, setCalcResult] = useState(null)
  const [calcError, setCalcError] = useState(null)

  // Paper Trading & Journal Editor Modal
  const [portfolio, setPortfolio] = useState(null)
  const [loadingPort, setLoadingPort] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [actionMsg, setActionMsg] = useState(null)
  const [editingJournal, setEditingJournal] = useState(null) // position object being edited

  useEffect(() => {
    api
      .getFxRate(false)
      .then((res) => {
        if (res?.rate) setFxRate(res.rate)
      })
      .catch(() => {})
  }, [])

  // Apply prefill from Scanner / X-Ray / Vision
  useEffect(() => {
    if (prefillTrade) {
      setTicker(prefillTrade.ticker || 'NVDA')
      setAssetType(prefillTrade.asset_type || 'stock')
      setAssetCurrency(prefillTrade.asset_currency || 'USD')
      if (prefillTrade.entry_price) setEntryPrice(Number(prefillTrade.entry_price))
      if (prefillTrade.stop_loss_pct) setStopLossPct(Math.min(Number(prefillTrade.stop_loss_pct), 7.0))
      if (prefillTrade.setup_tag) setSetupTag(prefillTrade.setup_tag)
      if (prefillTrade.notes) setNotes(prefillTrade.notes)
      onClearPrefill?.()
    }
  }, [prefillTrade])

  // Live calculate whenever inputs change
  useEffect(() => {
    const entry = Number(entryPrice)
    const cap = Number(capitalEur)
    const stop = Number(stopLossPct)
    if (!(entry > 0) || !(cap > 0) || !(stop > 0)) return
    if (stop > 7.0) {
      setCalcError('Stop-Loss bloqueado: teto máximo absoluto é 7.0% (recomendado ≤ 6.0%).')
      setCalcResult(null)
      return
    }

    const timer = setTimeout(async () => {
      try {
        setCalcError(null)
        const res = await api.calculatePosition({
          capital_eur: cap,
          entry_price: entry,
          asset_currency: assetCurrency,
          stop_loss_pct: stop,
          sizing_mode: sizingMode,
          risk_pct_of_account: Number(riskPctAccount) || 2.0,
          custom_target_price: customTarget ? Number(customTarget) : null,
          allow_fractional: allowFractional,
        })
        setCalcResult(res)
        if (res?.fx_rate_eurusd && assetCurrency === 'USD') setFxRate(res.fx_rate_eurusd)
      } catch (err) {
        setCalcError(err.message)
      }
    }, 150)
    return () => clearTimeout(timer)
  }, [capitalEur, entryPrice, assetCurrency, stopLossPct, sizingMode, riskPctAccount, customTarget, allowFractional])

  const loadPortfolio = async (refresh = false) => {
    try {
      if (refresh) setRefreshing(true)
      else setLoadingPort(true)
      const res = refresh
        ? await api.refreshPaperPortfolio(defaultCapitalEur)
        : await api.getPaperPortfolio(false, defaultCapitalEur)
      setPortfolio(res)
      if (res?.fx_rate_eurusd) setFxRate(res.fx_rate_eurusd)

      if (refresh) {
        const msgs = []
        if (res.triggered_partials?.length) {
          msgs.push(`Alvo 2R (50% + Breakeven) acionado em: ${res.triggered_partials.map((p) => p.ticker).join(', ')}`)
        }
        if (res.triggered_stops?.length) {
          msgs.push(`Stop automático acionado em: ${res.triggered_stops.map((s) => s.ticker).join(', ')}`)
        }
        if (msgs.length) {
          setActionMsg({ type: res.triggered_stops?.length ? 'danger' : 'success', text: msgs.join(' | ') })
        }
      }
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    } finally {
      setLoadingPort(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadPortfolio(false)
  }, [defaultCapitalEur])

  const handleSimulateEntry = async () => {
    if (!ticker.trim() || !calcResult || calcResult.quantity <= 0) return
    try {
      await api.openPaperPosition({
        ticker: ticker.trim().toUpperCase(),
        asset_type: assetType,
        asset_currency: assetCurrency,
        entry_price: Number(entryPrice),
        capital_eur: Number(calcResult.position_value_eur || capitalEur),
        stop_loss_pct: Math.min(Number(stopLossPct), 7.0),
        quantity: calcResult.quantity,
        auto_manage_2r: autoManage2R,
        trailing_stop_mode: trailingMode,
        setup_tag: setupTag,
        journal_emotion: journalEmotion,
        notes: notes || `Simulação ${setupTag} (Stop -${stopLossPct}%)`,
      })
      setActionMsg({
        type: 'success',
        text: `Posição aberta em ${ticker.toUpperCase()} (${calcResult.quantity} un. @ ${formatPrice(entryPrice)} ${assetCurrency} | Stop -${stopLossPct}%${autoManage2R ? ' | Auto 2R + BE ativo' : ''}).`,
      })
      setNotes('')
      loadPortfolio(false)
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    }
  }

  const handleMoveBreakeven = async (pos) => {
    await api.movePositionBreakeven(pos.id)
    setActionMsg({ type: 'success', text: `Stop de ${pos.ticker} movido para Breakeven (${formatPrice(pos.entry_price)}) — risco 0€!` })
    loadPortfolio(false)
  }

  const handleClosePosition = async (pos) => {
    await api.closePaperPosition(pos.id, pos.current_price)
    loadPortfolio(false)
  }

  const handleDeletePosition = async (posId) => {
    if (!window.confirm('Eliminar permanentemente este registo do teu Diário de Paper Trading?')) return
    await api.deletePaperPosition(posId)
    loadPortfolio(false)
  }

  const handleSaveJournal = async (e) => {
    e.preventDefault()
    if (!editingJournal) return
    await api.updatePositionJournal(editingJournal.id, {
      setup_tag: editingJournal.setup_tag,
      journal_emotion: editingJournal.journal_emotion,
      journal_lesson: editingJournal.journal_lesson,
      notes: editingJournal.notes,
      auto_manage_2r: Boolean(editingJournal.auto_manage_2r),
      trailing_stop_mode: editingJournal.trailing_stop_mode,
    })
    setEditingJournal(null)
    setActionMsg({ type: 'success', text: 'Diário de trade atualizado em SQLite.' })
    loadPortfolio(false)
  }

  const m = portfolio?.metrics || {}
  const heat = portfolio?.portfolio_heat || null
  const positions = portfolio?.positions || []
  const jStats = portfolio?.journal_stats || { by_setup: [], by_emotion: [] }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white">Gestão de Risco (6% Max Loss), FX EUR/USD & Diário Paper Trading</h2>
          <p className="text-xs text-slate-400">
            Conversão live EUR/USD • Auto Parcial 2R + Breakeven • Trailing Stop SMA 10/21 • Diário de performance por Setup.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-terminal-panel border border-terminal-border text-xs font-mono text-cyan-300">
            <ArrowRightLeft className="w-3.5 h-3.5" />
            1€ = ${Number(fxRate).toFixed(4)}
          </span>
          <button
            onClick={() => loadPortfolio(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Atualizar Preços, 2R & Stops
          </button>
        </div>
      </div>

      {actionMsg && (
        <div
          className={`rounded-lg px-4 py-2.5 text-xs border flex items-center justify-between ${
            actionMsg.type === 'danger'
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-200'
              : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
          }`}
        >
          <span>{actionMsg.text}</span>
          <button onClick={() => setActionMsg(null)} className="opacity-70 hover:opacity-100 ml-4">
            ✕
          </button>
        </div>
      )}

      <WarningBanner warnings={[...(portfolio?.warnings || []), ...(calcResult?.warnings || [])]} />

      {/* Top Grid: Position Calculator (Left) + Metrics & Equity Curve (Right) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Position Calculator */}
        <div className="xl:col-span-5 terminal-card p-5 space-y-3.5 border-emerald-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calculator className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Calculadora de Posição (FX Live)</h3>
            </div>
            <StatusBadge variant={stopLossPct > 6.0 ? 'yellow' : 'green'}>
              Stop {Number(stopLossPct).toFixed(1)}% (Máx 7%)
            </StatusBadge>
          </div>

          <div className="grid grid-cols-3 gap-2.5 text-xs">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="w-full px-2.5 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Classe</label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full px-2.5 py-2 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
              >
                <option value="stock">Ação / ETF</option>
                <option value="crypto">Cripto</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Moeda Ativo</label>
              <select
                value={assetCurrency}
                onChange={(e) => setAssetCurrency(e.target.value)}
                className="w-full px-2.5 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-cyan-300"
              >
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">
                Capital (€) — Teu padrão: {Number(defaultCapitalEur).toFixed(0)}€
              </label>
              <input
                type="number"
                min="1"
                step="10"
                value={capitalEur}
                onChange={(e) => setCapitalEur(e.target.value)}
                className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Preço Entrada ({assetCurrency})</label>
              <input
                type="number"
                min="0.000001"
                step="any"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
              />
            </div>
          </div>

          {/* Stop-Loss Slider */}
          <div className="space-y-1.5 bg-[#090f1d] border border-terminal-border rounded-lg p-3">
            <div className="flex items-center justify-between text-xs">
              <label className="text-slate-300 font-medium">Stop-Loss Máximo</label>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="0.5"
                  max="7.0"
                  step="0.5"
                  value={stopLossPct}
                  onChange={(e) => setStopLossPct(Math.min(Number(e.target.value), 7.0))}
                  className="w-16 px-2 py-0.5 font-mono text-right bg-[#070b14] border border-terminal-border rounded text-rose-400 font-bold"
                />
                <span className="font-mono text-rose-400">%</span>
              </div>
            </div>
            <input
              type="range"
              min="1.0"
              max="7.0"
              step="0.25"
              value={Math.min(Number(stopLossPct) || 6, 7)}
              onChange={(e) => setStopLossPct(Number(e.target.value))}
              className="w-full accent-rose-500"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500">
              <span>1%</span>
              <span className="text-emerald-400">6.0% (Padrão Minervini)</span>
              <span className="text-rose-400">7.0% (Teto Absoluto)</span>
            </div>
          </div>

          {/* Minervini Active Exit & Journal Config */}
          <div className="bg-[#090f1d] border border-terminal-border rounded-lg p-3 space-y-2.5 text-xs">
            <label className="flex items-center gap-2 text-emerald-300 font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={autoManage2R}
                onChange={(e) => setAutoManage2R(e.target.checked)}
                className="accent-emerald-500"
              />
              Auto 2R: Vender 50% no alvo 2R e mover Stop p/ Breakeven
            </label>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Trailing Stop</label>
                <select
                  value={trailingMode}
                  onChange={(e) => setTrailingMode(e.target.value)}
                  className="w-full px-2 py-1.5 bg-[#070b14] border border-terminal-border rounded-md text-slate-200 text-[11px]"
                >
                  <option value="NONE">Fixo / BE</option>
                  <option value="SMA10">SMA 10</option>
                  <option value="SMA21">SMA 21</option>
                  <option value="SMA50">SMA 50</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Setup (Diário)</label>
                <select
                  value={setupTag}
                  onChange={(e) => setSetupTag(e.target.value)}
                  className="w-full px-2 py-1.5 bg-[#070b14] border border-terminal-border rounded-md text-cyan-300 text-[11px] font-mono"
                >
                  {SETUP_TAGS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Emoção</label>
                <select
                  value={journalEmotion}
                  onChange={(e) => setJournalEmotion(e.target.value)}
                  className="w-full px-2 py-1.5 bg-[#070b14] border border-terminal-border rounded-md text-slate-200 text-[11px]"
                >
                  {EMOTION_TAGS.map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <select
                value={sizingMode}
                onChange={(e) => setSizingMode(e.target.value)}
                className="px-2 py-1.5 bg-[#070b14] border border-terminal-border rounded-md text-slate-300 text-[11px]"
              >
                <option value="capital_allocation">Alocar Capital (100%)</option>
                <option value="account_risk">Limitar Risco % Conta</option>
              </select>
              {sizingMode === 'account_risk' ? (
                <input
                  type="number"
                  min="0.5"
                  max="7"
                  step="0.5"
                  value={riskPctAccount}
                  onChange={(e) => setRiskPctAccount(e.target.value)}
                  placeholder="Risco % Conta"
                  className="px-2 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-md text-white text-[11px]"
                />
              ) : (
                <input
                  type="number"
                  step="any"
                  value={customTarget}
                  onChange={(e) => setCustomTarget(e.target.value)}
                  placeholder="Alvo manual (opc.)"
                  className="px-2 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-md text-white text-[11px]"
                />
              )}
            </div>

            <label className="inline-flex items-center gap-2 text-[11px] text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={allowFractional}
                onChange={(e) => setAllowFractional(e.target.checked)}
                className="accent-cyan-500"
              />
              Permitir unidades fracionadas (ideal para contas pequenas)
            </label>
          </div>

          {(calcError || calcResult?.risk_warning) && (
            <div className="rounded-lg bg-amber-500/10 border border-amber-500/40 px-3 py-2 text-xs text-amber-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{calcError || calcResult.risk_warning}</span>
            </div>
          )}

          {calcResult && (
            <div className="grid grid-cols-2 gap-2 font-mono text-xs">
              <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-2.5">
                <div className="text-[10px] text-cyan-300 font-sans">Quantidade a Comprar</div>
                <div className="text-lg font-bold text-white mt-0.5">{calcResult.quantity}</div>
                <div className="text-[10px] text-slate-400">
                  {calcResult.position_value_eur.toFixed(2)}€
                  {assetCurrency === 'USD' ? ` ($${calcResult.position_value_asset_ccy})` : ''}
                </div>
              </div>

              <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5">
                <div className="text-[10px] text-rose-300 font-sans">Perda Máxima Real (€)</div>
                <div className="text-lg font-bold text-rose-400 mt-0.5">-{calcResult.max_loss_eur.toFixed(2)}€</div>
                <div className="text-[10px] text-slate-400">
                  Stop @ {formatPrice(calcResult.stop_loss_price)} {assetCurrency}
                </div>
              </div>

              <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-lg p-2.5">
                <div className="text-[10px] text-emerald-300 font-sans">Alvo 2R (1:2)</div>
                <div className="text-sm font-bold text-emerald-400">+{calcResult.target_2r_profit_eur.toFixed(2)}€</div>
                <div className="text-[10px] text-slate-400">@ {formatPrice(calcResult.target_2r_price)}</div>
              </div>

              <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-lg p-2.5">
                <div className="text-[10px] text-cyan-300 font-sans">Alvo 3R (1:3)</div>
                <div className="text-sm font-bold text-cyan-300">+{calcResult.target_3r_profit_eur.toFixed(2)}€</div>
                <div className="text-[10px] text-slate-400">@ {formatPrice(calcResult.target_3r_price)}</div>
              </div>
            </div>
          )}

          <button
            onClick={handleSimulateEntry}
            disabled={!calcResult || calcResult.quantity <= 0}
            className="w-full py-2.5 rounded-lg bg-emerald-500/25 hover:bg-emerald-500/35 border border-emerald-500/50 text-sm font-semibold text-emerald-200 inline-flex items-center justify-center gap-2 transition disabled:opacity-40"
          >
            <Zap className="w-4 h-4" />
            Simular Entrada no Paper Trading
          </button>
        </div>

        {/* Right: Metrics + Equity Curve + Journal Analytics */}
        <div className="xl:col-span-7 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono tabular-nums">
            <div className="terminal-card p-3.5">
              <div className="text-[11px] font-sans text-slate-400">Equity Simulada</div>
              <div className="text-xl font-bold text-white mt-1">
                {(m.current_equity_eur ?? Number(defaultCapitalEur)).toFixed(2)}€
              </div>
              <div className="text-[10px] text-slate-500">
                Base: {(m.base_capital_eur ?? Number(defaultCapitalEur)).toFixed(0)}€
              </div>
            </div>

            <div className="terminal-card p-3.5">
              <div className="text-[11px] font-sans text-slate-400">P&amp;L Total (€)</div>
              <div className={`text-xl font-bold mt-1 ${(m.total_pnl_eur || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(m.total_pnl_eur || 0) >= 0 ? '+' : ''}
                {(m.total_pnl_eur ?? 0).toFixed(2)}€
              </div>
              <div className="text-[10px] text-slate-400">{formatPct(m.total_pnl_pct ?? 0)}</div>
            </div>

            <div className="terminal-card p-3.5">
              <div className="text-[11px] font-sans text-slate-400">Win Rate</div>
              <div className="text-xl font-bold text-cyan-300 mt-1">{(m.win_rate_pct ?? 0).toFixed(1)}%</div>
              <div className="text-[10px] text-slate-400">
                {m.wins ?? 0}W / {m.losses ?? 0}L (PF {m.profit_factor ?? 0})
              </div>
            </div>

            <div className="terminal-card p-3.5">
              <div className="text-[11px] font-sans text-slate-400">Max Drawdown</div>
              <div className="text-xl font-bold text-rose-400 mt-1">-{(m.max_drawdown_pct ?? 0).toFixed(2)}%</div>
              <div className="text-[10px] text-slate-400">
                2R Parciais: {m.partial_2r_count ?? 0} • R Médio: {m.avg_r_multiple ?? 0}R
              </div>
            </div>
          </div>

          {/* Portfolio Heat & Sector Concentration Monitor */}
          {heat && (
            <div
              className={`terminal-card p-4 space-y-3 border ${
                heat.heat_level === 'ALTO'
                  ? 'border-rose-500/45 bg-rose-500/5'
                  : heat.heat_level === 'MODERADO'
                    ? 'border-amber-500/35'
                    : 'border-emerald-500/25'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-bold text-white">Calor da Carteira (Portfolio Heat &amp; Concentração)</div>
                  <p className="text-[11px] text-slate-400">{heat.heat_message}</p>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <StatusBadge
                    variant={
                      heat.heat_level === 'ALTO' ? 'red' : heat.heat_level === 'MODERADO' ? 'yellow' : 'green'
                    }
                  >
                    Risco Aberto: -{heat.open_risk_eur.toFixed(2)}€ ({heat.open_risk_pct.toFixed(1)}%)
                  </StatusBadge>
                  {heat.breakeven_protected_count > 0 && (
                    <StatusBadge variant="cyan">
                      {heat.breakeven_protected_count} em Breakeven (0€ risco)
                    </StatusBadge>
                  )}
                </div>
              </div>

              <div className="w-full h-2 rounded-full bg-[#070b14] overflow-hidden border border-terminal-border">
                <div
                  className={`h-full transition-all ${
                    heat.heat_level === 'ALTO'
                      ? 'bg-rose-500'
                      : heat.heat_level === 'MODERADO'
                        ? 'bg-amber-400'
                        : 'bg-emerald-400'
                  }`}
                  style={{ width: `${Math.min(Math.max((heat.open_risk_pct / 8.0) * 100, heat.open_risk_pct > 0 ? 6 : 0), 100)}%` }}
                />
              </div>

              {(heat.sector_exposure || []).length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="text-slate-400 mr-1">Exposição aberta:</span>
                  {heat.sector_exposure.map((sec) => (
                    <span
                      key={sec.sector}
                      className="px-2 py-0.5 rounded-md bg-[#080e1c] border border-terminal-border font-mono text-slate-200"
                    >
                      {sec.sector}: <strong className="text-cyan-300">{sec.capital_pct}%</strong> ({sec.count})
                    </span>
                  ))}
                </div>
              )}

              {heat.concentration_warning && (
                <div className="rounded-lg bg-amber-500/15 border border-amber-500/40 px-3 py-2 text-xs text-amber-200 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-300 shrink-0" />
                  <span>{heat.concentration_warning}</span>
                </div>
              )}
            </div>
          )}

          {/* Equity Curve */}
          <div className="terminal-card p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Curva de Capital — Paper Trading
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Abertas: {m.open_trades ?? 0} • Fechadas: {m.closed_trades ?? 0}
              </span>
            </div>
            <EquityCurveChart points={portfolio?.equity_curve || []} />
          </div>

          {/* Van K. Tharp Expectancy & SQN Quality Card */}
          <div className="terminal-card p-4 border-cyan-500/30 flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="text-xs font-bold text-cyan-300">
                Qualidade Estatística do Teu Sistema — Van K. Tharp (Expectancy &amp; SQN)
              </div>
              <p className="text-[11px] text-slate-400">
                Mede se a tua estratégia tem vantagem matemática real (SQN ≥ 2.0 = sistema sólido; ≥ 3.0 = excelente).
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
              <div className="px-3 py-2 rounded-xl bg-[#080e1c] border border-terminal-border">
                <div className="text-[10px] font-sans text-slate-400">Expectancy (R)</div>
                <div className={`text-base font-bold ${(m.expectancy_r || 0) >= 0.2 ? 'text-emerald-400' : 'text-amber-300'}`}>
                  {(m.expectancy_r || 0) >= 0 ? '+' : ''}
                  {(m.expectancy_r ?? 0).toFixed(2)}R
                </div>
              </div>
              <div className="px-3 py-2 rounded-xl bg-[#080e1c] border border-terminal-border">
                <div className="text-[10px] font-sans text-slate-400">SQN Score</div>
                <div className={`text-base font-bold ${(m.sqn || 0) >= 2.0 ? 'text-emerald-400' : 'text-cyan-300'}`}>
                  {m.sqn !== null && m.sqn !== undefined ? m.sqn.toFixed(2) : '—'}
                </div>
              </div>
              <StatusBadge variant={(m.sqn || 0) >= 2.0 ? 'green' : 'slate'}>
                {m.sqn_grade || 'Amostra curta (< 5 trades)'}
              </StatusBadge>
            </div>
          </div>

          {/* Trading Journal Analytics: Where You Win vs Lose */}
          <div className="terminal-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <BookOpen className="w-4 h-4 text-cyan-400" />
                Diário de Trading — Onde Ganhas vs. Onde Perdes
              </div>
              <span className="text-[10px] text-slate-500">Agrupado por Setup &amp; Emoção (trades fechados)</span>
            </div>

            {jStats.by_setup.length === 0 ? (
              <p className="text-xs text-slate-500">
                Fecha trades com etiquetas de Setup (VCP, Breakout, FOMO...) para gerar automaticamente as estatísticas de edge do teu diário.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="space-y-1.5">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Por Setup</div>
                  {jStats.by_setup.map((row) => (
                    <div
                      key={row.tag}
                      className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#090f1d] border border-terminal-border font-mono"
                    >
                      <div>
                        <span className="font-bold text-cyan-300">{row.tag}</span>
                        <span className="text-[10px] text-slate-400 ml-2">
                          {row.trades}T • WR {row.win_rate_pct}% • {row.avg_r}R
                        </span>
                      </div>
                      <span className={row.pnl_eur >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                        {row.pnl_eur >= 0 ? '+' : ''}
                        {row.pnl_eur.toFixed(2)}€
                      </span>
                    </div>
                  ))}
                </div>

                <div className="space-y-1.5">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Por Emoção / Disciplina</div>
                  {jStats.by_emotion.map((row) => (
                    <div
                      key={row.tag}
                      className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#090f1d] border border-terminal-border font-mono"
                    >
                      <div>
                        <span className="font-bold text-slate-200">{row.tag}</span>
                        <span className="text-[10px] text-slate-400 ml-2">
                          {row.trades}T • WR {row.win_rate_pct}%
                        </span>
                      </div>
                      <span className={row.pnl_eur >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                        {row.pnl_eur >= 0 ? '+' : ''}
                        {row.pnl_eur.toFixed(2)}€
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="terminal-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-terminal-border flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-white">Posições de Paper Trading &amp; Diário (SQLite)</h3>
          <span className="text-[11px] text-slate-400">
            Automação: Stop-Loss rígido + Parcial 50% em 2R + Breakeven + Trailing SMA 10/21.
          </span>
        </div>

        {loadingPort && !portfolio ? (
          <div className="p-8 text-center text-xs text-slate-400">A carregar posições...</div>
        ) : positions.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            Ainda não tens posições simuladas. Usa a calculadora acima ou clica em &quot;Simular Entrada&quot; no Scanner ou Raio-X.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-terminal-card/70 text-[11px] uppercase font-mono text-slate-400 border-b border-terminal-border">
                <tr>
                  <th className="px-4 py-3">Ativo &amp; Setup</th>
                  <th className="px-3 py-3 text-right">Entrada</th>
                  <th className="px-3 py-3 text-right">Atual / Saída</th>
                  <th className="px-3 py-3 text-right">Stop Atual</th>
                  <th className="px-3 py-3 text-right">Alvos 2R / 3R</th>
                  <th className="px-3 py-3 text-right">Qtd / Alocado</th>
                  <th className="px-3 py-3 text-right">P&amp;L (€)</th>
                  <th className="px-3 py-3">Gestão / Estado</th>
                  <th className="px-4 py-3 text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-terminal-border/60 font-mono tabular-nums">
                {positions.map((p) => {
                  const isOpen = p.status === 'OPEN'
                  const pnlPos = Number(p.pnl_eur) >= 0
                  return (
                    <tr key={p.id} className="hover:bg-terminal-hover/60">
                      <td className="px-4 py-3 font-sans">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <button
                            onClick={() => onOpenXRay(p.ticker)}
                            className="font-mono font-bold text-white hover:text-cyan-300"
                          >
                            {p.ticker}
                          </button>
                          <StatusBadge variant="cyan">{p.setup_tag || 'VCP'}</StatusBadge>
                          <span className="text-[10px] text-slate-500">{p.currency || 'USD'}</span>
                        </div>
                        {p.journal_lesson ? (
                          <div className="text-[10px] text-amber-300/90 truncate max-w-[200px]">📝 {p.journal_lesson}</div>
                        ) : (
                          p.notes && <div className="text-[10px] text-slate-500 truncate max-w-[200px]">{p.notes}</div>
                        )}
                      </td>
                      <td className="px-3 py-3 text-right text-slate-200">{formatPrice(p.entry_price)}</td>
                      <td className="px-3 py-3 text-right text-white font-semibold">
                        {formatPrice(isOpen ? p.current_price : p.exit_price)}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div className={p.breakeven_moved ? 'text-emerald-400 font-bold' : 'text-rose-400'}>
                          {formatPrice(p.stop_loss_price)}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {p.breakeven_moved ? 'BREAKEVEN ✓' : `-${p.stop_loss_pct}%`}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right text-[11px]">
                        <div className="text-emerald-400">{formatPrice(p.target_2r)}</div>
                        <div className="text-cyan-400">{formatPrice(p.target_3r)}</div>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div className="text-slate-200">
                          {Number(p.quantity) >= 100 ? Number(p.quantity).toFixed(2) : Number(p.quantity).toFixed(4)}
                        </div>
                        <div className="text-[10px] text-slate-500">{Number(p.capital_allocated).toFixed(2)}€</div>
                      </td>
                      <td className={`px-3 py-3 text-right font-bold ${pnlPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                        <div>
                          {pnlPos ? '+' : ''}
                          {Number(p.pnl_eur).toFixed(2)}€
                        </div>
                        <div className="text-[10px]">{formatPct(p.pnl_pct)}</div>
                      </td>
                      <td className="px-3 py-3 font-sans space-y-1">
                        <div>
                          {p.status === 'OPEN' ? (
                            <StatusBadge variant="cyan">ABERTA</StatusBadge>
                          ) : p.status === 'CLOSED_STOP' ? (
                            <StatusBadge variant="red">STOP AUTO</StatusBadge>
                          ) : p.status === 'CLOSED_BE' ? (
                            <StatusBadge variant="green">BREAKEVEN / TRAIL</StatusBadge>
                          ) : (
                            <StatusBadge variant="green">FECHADA</StatusBadge>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {p.partial_2r_taken === 1 && <StatusBadge variant="green">2R 50% ✓</StatusBadge>}
                          {p.trailing_stop_mode && p.trailing_stop_mode !== 'NONE' && (
                            <StatusBadge variant="purple">TRAIL {p.trailing_stop_mode}</StatusBadge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            onClick={() => setEditingJournal({ ...p })}
                            className="p-1.5 rounded bg-terminal-card border border-terminal-border hover:border-cyan-500/50 text-cyan-300"
                            title="Editar Diário / Lição"
                          >
                            <NotebookPen className="w-3.5 h-3.5" />
                          </button>
                          {isOpen && !p.breakeven_moved && (
                            <button
                              onClick={() => handleMoveBreakeven(p)}
                              className="p-1.5 rounded bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25"
                              title="Mover Stop para Breakeven (risco zero)"
                            >
                              <Lock className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {isOpen && (
                            <button
                              onClick={() => handleClosePosition(p)}
                              className="px-2 py-1 text-[11px] font-sans font-semibold rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300"
                            >
                              Fechar
                            </button>
                          )}
                          <button
                            onClick={() => handleDeletePosition(p.id)}
                            className="p-1.5 rounded bg-terminal-card border border-terminal-border hover:border-rose-500/50 text-slate-400 hover:text-rose-400"
                            title="Eliminar registo"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Journal Modal */}
      {editingJournal && (
        <div
          onClick={() => setEditingJournal(null)}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveJournal}
            className="terminal-card w-full max-w-lg p-5 space-y-4 text-xs"
          >
            <div className="flex items-center justify-between border-b border-terminal-border pb-3">
              <h3 className="text-sm font-bold text-white">Diário de Trade — {editingJournal.ticker}</h3>
              <button type="button" onClick={() => setEditingJournal(null)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Etiqueta de Setup</label>
                <select
                  value={editingJournal.setup_tag || 'VCP'}
                  onChange={(e) => setEditingJournal({ ...editingJournal, setup_tag: e.target.value })}
                  className="w-full px-3 py-2 bg-[#070b14] border border-terminal-border rounded-lg text-cyan-300 font-mono"
                >
                  {SETUP_TAGS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Estado Emocional</label>
                <select
                  value={editingJournal.journal_emotion || 'DISCIPLINADO'}
                  onChange={(e) => setEditingJournal({ ...editingJournal, journal_emotion: e.target.value })}
                  className="w-full px-3 py-2 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
                >
                  {EMOTION_TAGS.map((em) => (
                    <option key={em} value={em}>{em}</option>
                  ))}
                </select>
              </div>
            </div>

            {editingJournal.status === 'OPEN' && (
              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center gap-2 text-emerald-300">
                  <input
                    type="checkbox"
                    checked={Boolean(editingJournal.auto_manage_2r)}
                    onChange={(e) => setEditingJournal({ ...editingJournal, auto_manage_2r: e.target.checked })}
                    className="accent-emerald-500"
                  />
                  Auto 2R (50% + BE)
                </label>
                <select
                  value={editingJournal.trailing_stop_mode || 'NONE'}
                  onChange={(e) => setEditingJournal({ ...editingJournal, trailing_stop_mode: e.target.value })}
                  className="px-2.5 py-1.5 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
                >
                  <option value="NONE">Trailing: Nenhum</option>
                  <option value="SMA10">Trailing: SMA 10</option>
                  <option value="SMA21">Trailing: SMA 21</option>
                  <option value="SMA50">Trailing: SMA 50</option>
                </select>
              </div>
            )}

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Lição / Revisão Pós-Trade</label>
              <textarea
                rows={3}
                value={editingJournal.journal_lesson || ''}
                onChange={(e) => setEditingJournal({ ...editingJournal, journal_lesson: e.target.value })}
                placeholder="Ex: Respeitei o pivô com VDU e realizei parcial em 2R. Próxima vez aguardar fecho da 1ª hora."
                className="w-full px-3 py-2 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingJournal(null)}
                className="px-3 py-1.5 rounded-lg bg-terminal-card border border-terminal-border text-slate-300"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-cyan-500/25 hover:bg-cyan-500/35 border border-cyan-500/50 text-cyan-200 font-semibold"
              >
                Guardar Diário
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
