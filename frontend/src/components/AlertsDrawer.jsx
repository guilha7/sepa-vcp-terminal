import React, { useEffect, useState } from 'react'
import {
  Bell,
  CheckCheck,
  CloudUpload,
  Plus,
  RefreshCw,
  Send,
  Smartphone,
  Trash2,
  X,
} from 'lucide-react'
import { api, formatPrice, formatTimestamp } from '../services/api'
import { StatusBadge } from './StatusBadge'

export function AlertsDrawer({ open, onClose, prefillAlert, onClearPrefill, onAlertsChanged }) {
  const [tab, setTab] = useState('feed') // feed | price | channels
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState(null)

  // Price Alert Form
  const [ticker, setTicker] = useState('SPOT')
  const [condition, setCondition] = useState('ABOVE')
  const [targetPrice, setTargetPrice] = useState('')
  const [notes, setNotes] = useState('')

  // Telegram / Discord Channels Form
  const [tgToken, setTgToken] = useState('')
  const [tgChat, setTgChat] = useState('')
  const [discordUrl, setDiscordUrl] = useState('')

  const load = async () => {
    try {
      setLoading(true)
      const res = await api.getAlertsOverview(50)
      setData(res)
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) load()
  }, [open])

  useEffect(() => {
    if (prefillAlert && open) {
      setTab('price')
      setTicker(prefillAlert.ticker || '')
      setCondition(prefillAlert.condition || 'ABOVE')
      setTargetPrice(prefillAlert.target_price ? String(prefillAlert.target_price) : '')
      setNotes(prefillAlert.notes || '')
      onClearPrefill?.()
    }
  }, [prefillAlert, open])

  if (!open) return null

  const handleMarkRead = async () => {
    await api.markAlertsRead()
    await load()
    onAlertsChanged?.()
  }

  const handleCreatePriceAlert = async (e) => {
    e.preventDefault()
    if (!ticker.trim() || !(Number(targetPrice) > 0)) return
    try {
      await api.createPriceAlert({
        ticker: ticker.trim().toUpperCase(),
        condition,
        target_price: Number(targetPrice),
        notes: notes.trim(),
      })
      setTargetPrice('')
      setNotes('')
      setFeedback({ type: 'success', text: `Alerta criado para ${ticker.toUpperCase()}!` })
      await load()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    }
  }

  const handleCheckNow = async () => {
    try {
      setChecking(true)
      const res = await api.checkPriceAlertsNow()
      setFeedback({
        type: 'success',
        text: `Verificados ${res.checked} alertas ativos • Disparados agora: ${res.triggered.length}.`,
      })
      await load()
      onAlertsChanged?.()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    } finally {
      setChecking(false)
    }
  }

  const handleDeletePriceAlert = async (id) => {
    await api.deletePriceAlert(id)
    await load()
  }

  const handleExportToCloud = async () => {
    try {
      const res = await api.exportAlertsToCloud()
      setFeedback({
        type: 'success',
        text: `${res.exported_count} alertas ativos gravados em alertas_cloud.json! Faz git push para o GitHub Actions vigiar 24/7.`,
      })
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    }
  }

  const handleSaveChannels = async (e) => {
    e.preventDefault()
    const payload = {}
    if (tgToken.trim()) payload.telegram_bot_token = tgToken.trim()
    if (tgChat.trim()) payload.telegram_chat_id = tgChat.trim()
    if (discordUrl.trim()) payload.discord_webhook_url = discordUrl.trim()
    await api.updateAlertChannels(payload)
    setTgToken('')
    setTgChat('')
    setDiscordUrl('')
    setFeedback({ type: 'success', text: 'Canais de notificação guardados em SQLite!' })
    await load()
    onAlertsChanged?.()
  }

  const handleTestChannels = async () => {
    try {
      const res = await api.testAlertChannels()
      const d = res.delivery || {}
      const info = [
        d.telegram ? 'Telegram OK' : null,
        d.discord ? 'Discord OK' : null,
        ...(d.errors || []),
      ]
        .filter(Boolean)
        .join(' • ')
      setFeedback({
        type: d.telegram || d.discord ? 'success' : 'info',
        text: info || 'Alerta de teste gravado localmente (configura Telegram ou Discord para envio externo).',
      })
      await load()
      onAlertsChanged?.()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    }
  }

  const channels = data?.channels || {}

  return (
    <div onClick={onClose} className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex justify-end">
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-[#090f1d] border-l border-terminal-border h-full flex flex-col shadow-2xl"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-terminal-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-white">Central de Alertas & Telemóvel</h3>
              <p className="text-[11px] text-slate-400">Breakouts, Stops, Mudanças Macro & Alertas de Preço</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-terminal-hover">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="px-4 pt-3 flex items-center gap-1.5 border-b border-terminal-border pb-3 text-xs">
          {[
            { k: 'feed', l: `Feed (${data?.unread_count || 0})` },
            { k: 'price', l: `Alertas de Preço (${(data?.price_alerts || []).filter((p) => p.active).length})` },
            { k: 'channels', l: 'Telegram / Discord' },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => setTab(t.k)}
              className={`px-3 py-1.5 rounded-lg font-medium transition ${
                tab === t.k ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:bg-terminal-hover'
              }`}
            >
              {t.l}
            </button>
          ))}
        </div>

        {feedback && (
          <div
            className={`mx-4 mt-3 px-3 py-2 rounded-lg text-xs border ${
              feedback.type === 'error'
                ? 'bg-rose-500/10 border-rose-500/40 text-rose-300'
                : feedback.type === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-200'
            }`}
          >
            {feedback.text}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {tab === 'feed' && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Histórico de notificações</span>
                <button
                  onClick={handleMarkRead}
                  className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  Marcar tudo como lido
                </button>
              </div>

              {loading && !data ? (
                <p className="text-xs text-slate-500 text-center py-6">A carregar...</p>
              ) : (data?.alerts || []).length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-8">
                  Ainda sem alertas registados. Cria um alerta de preço ou corre o scanner!
                </p>
              ) : (
                <div className="space-y-2">
                  {(data?.alerts || []).map((a) => (
                    <div
                      key={a.id}
                      className={`p-3 rounded-lg border text-xs ${
                        a.level === 'danger'
                          ? 'bg-rose-500/10 border-rose-500/35 text-rose-100'
                          : a.level === 'success'
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-100'
                            : a.level === 'warning'
                              ? 'bg-amber-500/10 border-amber-500/30 text-amber-100'
                              : 'bg-terminal-card border-terminal-border text-slate-200'
                      } ${a.read === 0 ? 'ring-1 ring-cyan-400/40' : 'opacity-80'}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-mono text-[10px] font-bold uppercase tracking-wider opacity-85">
                          {a.category} {a.ticker ? `• ${a.ticker}` : ''}
                        </span>
                        <span className="font-mono text-[10px] opacity-65">{formatTimestamp(a.created_at)}</span>
                      </div>
                      <p className="leading-relaxed">{a.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'price' && (
            <>
              <form onSubmit={handleCreatePriceAlert} className="terminal-card p-3.5 space-y-2.5 text-xs">
                <div className="font-semibold text-white">Novo Alerta de Preço (Vigilância de Pivô)</div>
                <div className="grid grid-cols-3 gap-2">
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="Ticker"
                    className="px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                  />
                  <select
                    value={condition}
                    onChange={(e) => setCondition(e.target.value)}
                    className="px-2 py-1.5 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
                  >
                    <option value="ABOVE">Cruzar Acima (&gt;=)</option>
                    <option value="BELOW">Cair Abaixo (&lt;=)</option>
                  </select>
                  <input
                    type="number"
                    step="any"
                    value={targetPrice}
                    onChange={(e) => setTargetPrice(e.target.value)}
                    placeholder="Preço alvo"
                    className="px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                  />
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Nota (ex: Pivô VCP, suporte SMA 50...)"
                    className="flex-1 px-2.5 py-1.5 bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
                  />
                  <button
                    type="submit"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 font-semibold"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Criar
                  </button>
                </div>
              </form>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-slate-400">Monitorizados automaticamente pelo scheduler</span>
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleExportToCloud}
                    className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
                    title="Exporta alertas ativos para alertas_cloud.json (GitHub Actions 24/7)"
                  >
                    <CloudUpload className="w-3.5 h-3.5" />
                    Exportar p/ Cloud
                  </button>
                  <button
                    onClick={handleCheckNow}
                    disabled={checking}
                    className="inline-flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
                    Verificar Agora
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {(data?.price_alerts || []).map((pa) => (
                  <div
                    key={pa.id}
                    className="p-3 rounded-lg bg-terminal-card border border-terminal-border flex items-center justify-between gap-2 text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2 font-mono">
                        <span className="font-bold text-white">{pa.ticker}</span>
                        <span className={pa.condition === 'ABOVE' ? 'text-emerald-400' : 'text-rose-400'}>
                          {pa.condition === 'ABOVE' ? '≥' : '≤'} {formatPrice(pa.target_price)}
                        </span>
                        <StatusBadge variant={pa.triggered ? 'green' : 'cyan'}>
                          {pa.triggered ? `DISPARADO @ ${formatPrice(pa.triggered_price)}` : 'ATIVO'}
                        </StatusBadge>
                      </div>
                      {pa.notes && <p className="text-[11px] text-slate-400 mt-0.5">{pa.notes}</p>}
                    </div>
                    <button
                      onClick={() => handleDeletePriceAlert(pa.id)}
                      className="text-slate-500 hover:text-rose-400 p-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {(data?.price_alerts || []).length === 0 && (
                  <p className="text-xs text-slate-500 text-center py-6">Sem alertas de preço definidos.</p>
                )}
              </div>
            </>
          )}

          {tab === 'channels' && (
            <div className="space-y-4 text-xs">
              <div className="terminal-card p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white inline-flex items-center gap-1.5">
                    <Smartphone className="w-4 h-4 text-cyan-400" />
                    Estado dos Canais (100% Gratuitos)
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge variant={channels.telegram_configured ? 'green' : 'slate'}>
                    Telegram: {channels.telegram_configured ? `ATIVO (${channels.telegram_chat_id_masked})` : 'Não configurado'}
                  </StatusBadge>
                  <StatusBadge variant={channels.discord_configured ? 'green' : 'slate'}>
                    Discord: {channels.discord_configured ? 'ATIVO' : 'Não configurado'}
                  </StatusBadge>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Recebe alertas no telemóvel sempre que ocorrer um <strong>Breakout VCP</strong>, um{' '}
                  <strong>Alerta de Preço</strong>, uma <strong>Mudança no Semáforo Macro</strong> ou um{' '}
                  <strong>Stop-Loss / Alvo 2R</strong> no Paper Trading.
                </p>
              </div>

              <form onSubmit={handleSaveChannels} className="terminal-card p-4 space-y-3">
                <div className="font-semibold text-cyan-300">Telegram Bot (Grátis via @BotFather)</div>
                <input
                  type="password"
                  value={tgToken}
                  onChange={(e) => setTgToken(e.target.value)}
                  placeholder="TELEGRAM_BOT_TOKEN (ex: 123456:ABC-DEF...)"
                  className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
                <input
                  type="text"
                  value={tgChat}
                  onChange={(e) => setTgChat(e.target.value)}
                  placeholder="TELEGRAM_CHAT_ID (obtém no @userinfobot)"
                  className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />

                <div className="font-semibold text-purple-300 pt-2">Discord Webhook (Grátis)</div>
                <input
                  type="password"
                  value={discordUrl}
                  onChange={(e) => setDiscordUrl(e.target.value)}
                  placeholder="https://discord.com/api/webhooks/..."
                  className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />

                <div className="flex gap-2 pt-1">
                  <button
                    type="submit"
                    className="flex-1 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 font-semibold"
                  >
                    Guardar Canais
                  </button>
                  <button
                    type="button"
                    onClick={handleTestChannels}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold"
                  >
                    <Send className="w-3.5 h-3.5" />
                    Testar
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
