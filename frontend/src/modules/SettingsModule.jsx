import React, { useEffect, useState } from 'react'
import {
  Bell,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  ExternalLink,
  Layers,
  Lock,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
  User,
  X,
  XCircle,
} from 'lucide-react'
import { api, setStoredAdminToken } from '../services/api'
import { sanitizeTicker } from '../services/userPrefs'
import { StatusBadge } from '../components/StatusBadge'

export function SettingsModule({
  userName = 'Trader',
  userPrefs = { capitalEur: 100, stopLossPct: 6.0, riskPerTradePct: 2.0, favorites: [] },
  onUpdateUserPrefs,
  onToggleFavorite,
  onOpenXRay,
  onSettingsSaved,
  onOpenAlerts,
  adminRequired = false,
  isAdmin = true,
  onAdminUnlocked,
}) {
  // Personal preferences (accessible to every friend, saved per-profile in browser)
  const [myCapital, setMyCapital] = useState(userPrefs.capitalEur ?? 100)
  const [myStop, setMyStop] = useState(userPrefs.stopLossPct ?? 6.0)
  const [myRisk, setMyRisk] = useState(userPrefs.riskPerTradePct ?? 2.0)
  const [newFav, setNewFav] = useState('')
  const [personalFeedback, setPersonalFeedback] = useState(null)

  useEffect(() => {
    setMyCapital(userPrefs.capitalEur ?? 100)
    setMyStop(userPrefs.stopLossPct ?? 6.0)
    setMyRisk(userPrefs.riskPerTradePct ?? 2.0)
  }, [userPrefs.capitalEur, userPrefs.stopLossPct, userPrefs.riskPerTradePct])

  const [adminPwd, setAdminPwd] = useState('')
  const [adminErr, setAdminErr] = useState(null)
  const [unlocking, setUnlocking] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingAi, setTestingAi] = useState(false)
  const [aiTestResult, setAiTestResult] = useState(null)
  const [feedback, setFeedback] = useState(null)

  // Form state
  const [aiProvider, setAiProvider] = useState('auto')
  const [geminiKeyInput, setGeminiKeyInput] = useState('')
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash')
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434')
  const [ollamaModel, setOllamaModel] = useState('llama3.2')
  const [ollamaVisionModel, setOllamaVisionModel] = useState('qwen2.5-vl')

  const [defaultCapital, setDefaultCapital] = useState(100)
  const [defaultStop, setDefaultStop] = useState(6.0)

  const [ttlPrices, setTtlPrices] = useState(600)
  const [ttlNews, setTtlNews] = useState(900)
  const [ttlScan, setTtlScan] = useState(21600)
  const [ttlFund, setTtlFund] = useState(86400)

  const [schedulerEnabled, setSchedulerEnabled] = useState(true)
  const [macroMins, setMacroMins] = useState(15)
  const [paperMins, setPaperMins] = useState(10)
  const [scanHours, setScanHours] = useState(6)

  const hydrate = (res) => {
    setData(res)
    if (res?.ai) {
      setAiProvider(res.ai.ai_provider || 'auto')
      setGeminiModel(res.ai.gemini_model || 'gemini-2.5-flash')
      setOllamaUrl(res.ai.ollama_base_url || 'http://127.0.0.1:11434')
      setOllamaModel(res.ai.ollama_model || 'llama3.2')
      setOllamaVisionModel(res.ai.ollama_vision_model || 'qwen2.5-vl')
    }
    if (res?.risk) {
      setDefaultCapital(res.risk.default_capital_eur ?? 100)
      setDefaultStop(res.risk.default_stop_loss_pct ?? 6.0)
    }
    if (res?.cache) {
      setTtlPrices(res.cache.cache_ttl_prices ?? 600)
      setTtlNews(res.cache.cache_ttl_news ?? 900)
      setTtlScan(res.cache.cache_ttl_scan ?? 21600)
      setTtlFund(res.cache.cache_ttl_fundamentals ?? 86400)
    }
    if (res?.scheduler) {
      setSchedulerEnabled(Boolean(res.scheduler.scheduler_enabled))
      setMacroMins(res.scheduler.scheduler_macro_minutes ?? 15)
      setPaperMins(res.scheduler.scheduler_paper_minutes ?? 10)
      setScanHours(res.scheduler.scheduler_scan_hours ?? 6)
    }
  }

  const load = async () => {
    try {
      setLoading(true)
      const res = await api.getSettings()
      hydrate(res)
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!adminRequired || isAdmin) {
      load()
    } else {
      setLoading(false)
    }
  }, [adminRequired, isAdmin])

  const handleSavePersonal = (e) => {
    e.preventDefault()
    const saved = onUpdateUserPrefs?.({
      capitalEur: Number(myCapital),
      stopLossPct: Math.min(Number(myStop), 7.0),
      riskPerTradePct: Number(myRisk),
    })
    if (saved) {
      setMyCapital(saved.capitalEur)
      setMyStop(saved.stopLossPct)
      setMyRisk(saved.riskPerTradePct)
      setPersonalFeedback(
        `Preferências de ${userName} guardadas! A Calculadora e o teu Paper Trading já usam ${saved.capitalEur.toFixed(0)}€ e Stop -${saved.stopLossPct}%.`,
      )
    }
  }

  const handleAddFavorite = (e) => {
    e.preventDefault()
    const tk = sanitizeTicker(newFav)
    if (!tk) return
    const currentFavs = userPrefs.favorites || []
    if (!currentFavs.includes(tk)) {
      onUpdateUserPrefs?.({ favorites: [tk, ...currentFavs] })
    }
    setNewFav('')
  }

  const handleAdminUnlock = async (e) => {
    e.preventDefault()
    if (!adminPwd.trim()) return
    try {
      setUnlocking(true)
      setAdminErr(null)
      const res = await api.adminLogin(adminPwd)
      setStoredAdminToken(res.admin_token || '')
      setAdminPwd('')
      onAdminUnlocked?.()
    } catch (err) {
      setAdminErr(err.message || 'Password de Administrador incorreta.')
    } finally {
      setUnlocking(false)
    }
  }

  const personalSection = (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="heading-hero">Preferências Pessoais ({userName})</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Personaliza o teu capital, gestão de risco e lista de favoritos — fica guardado só para o teu perfil, sem alterar as definições dos outros.
          </p>
        </div>
        <StatusBadge variant="cyan">
          <span className="inline-flex items-center gap-1">
            <User className="w-3 h-3" /> Perfil: {userName}
          </span>
        </StatusBadge>
      </div>

      {personalFeedback && (
        <div className="rounded-xl px-4 py-2.5 text-xs border bg-emerald-500/15 border-emerald-500/40 text-emerald-200 flex items-center justify-between">
          <span>{personalFeedback}</span>
          <button type="button" onClick={() => setPersonalFeedback(null)} className="opacity-70 hover:opacity-100 ml-4">
            ✕
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Personal Risk & Capital */}
        <form onSubmit={handleSavePersonal} className="xl:col-span-6 terminal-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-terminal-border pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">O Teu Capital &amp; Risco Padrão</h3>
            </div>
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 transition"
            >
              <Save className="w-3.5 h-3.5" />
              Guardar
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Capital Base (€)</label>
              <input
                type="number"
                min="10"
                step="10"
                value={myCapital}
                onChange={(e) => setMyCapital(e.target.value)}
                className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Stop-Loss (%) • máx 7%</label>
              <input
                type="number"
                min="1"
                max="7"
                step="0.5"
                value={myStop}
                onChange={(e) => setMyStop(Math.min(Number(e.target.value), 7.0))}
                className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-rose-400 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Risco / Trade (%)</label>
              <input
                type="number"
                min="0.25"
                max="5"
                step="0.25"
                value={myRisk}
                onChange={(e) => setMyRisk(e.target.value)}
                className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-cyan-300 text-sm font-bold"
              />
            </div>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            Estes valores pré-preenchem a tua <strong>Calculadora de Posição</strong> e ajustam automaticamente a tua <strong>Curva de Capital</strong> no Paper Trading.
          </p>
        </form>

        {/* Personal Favorites / Watchlist */}
        <div className="xl:col-span-6 terminal-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-terminal-border pb-3">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
              <h3 className="text-sm font-bold text-white">Os Meus Favoritos (Watchlist Pessoal)</h3>
            </div>
            <StatusBadge variant="yellow">{(userPrefs.favorites || []).length} guardados</StatusBadge>
          </div>

          <form onSubmit={handleAddFavorite} className="flex gap-2">
            <input
              type="text"
              value={newFav}
              onChange={(e) => setNewFav(e.target.value.toUpperCase())}
              placeholder="Qualquer ticker (ex: NVDA, EDP.LS, BTC-USD, DIS...)"
              className="flex-1 px-3 py-2 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:border-amber-400/60"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1 px-3.5 py-2 text-xs font-semibold rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Adicionar ★
            </button>
          </form>

          {(userPrefs.favorites || []).length === 0 ? (
            <p className="text-xs text-slate-500 py-2">
              Ainda não tens favoritos. Podes adicionar qualquer ticker aqui acima ou clicar na estrela ★ no Scanner e no Raio-X!
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(userPrefs.favorites || []).map((tk) => (
                <div
                  key={tk}
                  className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs font-mono"
                >
                  <button
                    type="button"
                    onClick={() => onOpenXRay?.(tk)}
                    className="font-bold text-amber-200 hover:text-white transition"
                    title={`Abrir Raio-X de ${tk}`}
                  >
                    {tk}
                  </button>
                  <button
                    type="button"
                    onClick={() => onToggleFavorite?.(tk)}
                    className="p-0.5 rounded text-slate-400 hover:text-rose-400 transition"
                    title="Remover dos favoritos"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )

  if (adminRequired && !isAdmin) {
    return (
      <div className="space-y-8">
        {personalSection}

        <div className="border-t border-terminal-border/70 pt-6">
          <form onSubmit={handleAdminUnlock} className="max-w-lg terminal-card p-5 space-y-3.5 border-amber-500/30">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/40 flex items-center justify-center text-amber-300 shrink-0">
                <Lock className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-display text-sm font-bold text-white">Área Reservada ao Administrador</h3>
                <p className="text-[11px] text-slate-400">
                  Chave IA Gemini, Pacotes globais do Scanner, Cache e Telegram estão protegidos para uso do dono do site.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                type="password"
                value={adminPwd}
                onChange={(e) => setAdminPwd(e.target.value)}
                placeholder="Password de Administrador (ADMIN_PASSWORD)"
                className="flex-1 min-w-[200px] px-3.5 py-2 text-xs font-mono bg-[#060a13] border border-terminal-border rounded-xl text-white focus:outline-none focus:border-amber-400"
              />
              <button
                type="submit"
                disabled={unlocking}
                className="px-4 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-xs font-semibold text-amber-200 transition"
              >
                {unlocking ? 'A desbloquear...' : 'Desbloquear Admin'}
              </button>
            </div>
            {adminErr && <p className="text-xs text-rose-400">{adminErr}</p>}
          </form>
        </div>
      </div>
    )
  }

  const handleSaveAll = async (e) => {
    e?.preventDefault()
    try {
      setSaving(true)
      setFeedback(null)
      const payload = {
        ai_provider: aiProvider,
        gemini_model: geminiModel,
        ollama_base_url: ollamaUrl,
        ollama_model: ollamaModel,
        ollama_vision_model: ollamaVisionModel,
        default_capital_eur: Number(defaultCapital),
        default_stop_loss_pct: Math.min(Number(defaultStop), 7.0),
        cache_ttl_prices: Number(ttlPrices),
        cache_ttl_news: Number(ttlNews),
        cache_ttl_scan: Number(ttlScan),
        cache_ttl_fundamentals: Number(ttlFund),
        scheduler_enabled: schedulerEnabled,
        scheduler_macro_minutes: Number(macroMins),
        scheduler_paper_minutes: Number(paperMins),
        scheduler_scan_hours: Number(scanHours),
      }
      if (geminiKeyInput.trim()) {
        payload.gemini_api_key = geminiKeyInput.trim()
      }
      const res = await api.saveSettings(payload)
      hydrate(res)
      setGeminiKeyInput('')
      setFeedback({
        type: 'success',
        text: 'Definições guardadas em SQLite e aplicadas imediatamente (sem reiniciar o servidor)!',
      })
      onSettingsSaved?.()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  const handleClearGeminiKey = async () => {
    const res = await api.saveSettings({ clear_gemini_key: true })
    hydrate(res)
    setFeedback({ type: 'success', text: 'Chave Gemini removida. O terminal voltou ao modo automático/local.' })
    onSettingsSaved?.()
  }

  const handleTestAi = async () => {
    try {
      setTestingAi(true)
      setAiTestResult(null)
      const res = await api.testAiConnection()
      setAiTestResult(res)
    } catch (err) {
      setAiTestResult({ ok: false, provider: 'erro', message: err.message })
    } finally {
      setTestingAi(false)
    }
  }

  const handleApplyPack = async (packId, mode) => {
    try {
      const res = await api.applyUniversePack(packId, mode)
      if (res?.overview) hydrate(res.overview)
      setFeedback({
        type: 'success',
        text: `Pacote "${res.pack_name}" aplicado (${res.applied_count} tickers ${mode === 'replace_class' ? 'substituídos' : 'adicionados'} na watchlist)!`,
      })
      onSettingsSaved?.()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    }
  }

  const handleClearCache = async (category) => {
    try {
      const res = await api.clearCache(category)
      setFeedback({
        type: 'success',
        text: `Cache limpa (${category}): ${res.removed_entries} entradas removidas.`,
      })
      await load()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message })
    }
  }

  if (loading && !data) {
    return (
      <div className="space-y-6">
        {personalSection}
        <div className="terminal-card p-10 text-center text-sm text-slate-400">
          A carregar definições de administrador...
        </div>
      </div>
    )
  }

  const storage = data?.cache?.storage || {}

  return (
    <div className="space-y-8">
      {personalSection}

      <form onSubmit={handleSaveAll} className="space-y-6 border-t border-terminal-border/70 pt-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-white">Definições do Servidor &amp; Administrador</h2>
            <p className="text-xs text-slate-400">
              Configura IA gratuita, capital padrão global, pacotes do scanner, cache SQLite e scheduler — aplicado em tempo real.
            </p>
          </div>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-500/25 hover:bg-emerald-500/35 border border-emerald-500/50 text-emerald-200 transition disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? 'A guardar...' : 'Guardar Definições Admin'}
          </button>
        </div>

        {feedback && (
          <div
            className={`rounded-lg px-4 py-2.5 text-xs border flex items-center justify-between ${feedback.type === 'error'
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-200'
              : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
              }`}
          >
            <span>{feedback.text}</span>
            <button type="button" onClick={() => setFeedback(null)} className="opacity-70 hover:opacity-100 ml-4">
              ✕
            </button>
          </div>
        )}

        {/* Row 1: AI Engine + Risk Profile */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          {/* AI Provider Card (7 cols) */}
          <section className="xl:col-span-7 terminal-card p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-bold text-white">Motor de IA (Briefings &amp; Visão de Gráficos)</h3>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge variant={data?.ai?.ai_provider_active === 'fallback' ? 'yellow' : 'green'}>
                  Ativo: {data?.ai?.ai_provider_active?.toUpperCase()}
                </StatusBadge>
                <button
                  type="button"
                  onClick={handleTestAi}
                  disabled={testingAi}
                  className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 transition"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${testingAi ? 'animate-spin' : ''}`} />
                  Testar Ligação IA
                </button>
              </div>
            </div>

            {aiTestResult && (
              <div
                className={`rounded-lg p-3 text-xs border flex items-start gap-2 ${aiTestResult.ok
                  ? 'bg-emerald-500/10 border-emerald-500/35 text-emerald-200'
                  : 'bg-rose-500/10 border-rose-500/35 text-rose-200'
                  }`}
              >
                {aiTestResult.ok ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="font-semibold">
                    Resultado ({aiTestResult.provider?.toUpperCase()} • {aiTestResult.latency_ms} ms)
                  </div>
                  <p className="opacity-90 mt-0.5">{aiTestResult.message}</p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Modo do Provedor IA</label>
                <select
                  value={aiProvider}
                  onChange={(e) => setAiProvider(e.target.value)}
                  className="w-full px-3 py-2 bg-[#070b14] border border-terminal-border rounded-lg text-slate-100"
                >
                  <option value="auto">Automático (Gemini → Ollama → Fallback Local)</option>
                  <option value="gemini">Apenas Google Gemini (Free Tier)</option>
                  <option value="ollama">Apenas Ollama Local (Offline)</option>
                  <option value="none">Desativado (Apenas Fallback Algorítmico)</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Modelo Google Gemini</label>
                <select
                  value={geminiModel}
                  onChange={(e) => setGeminiModel(e.target.value)}
                  className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-cyan-300"
                >
                  <option value="gemini-2.5-flash">gemini-2.5-flash (Recomendado / Grátis)</option>
                  <option value="gemini-2.0-flash">gemini-2.0-flash</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                </select>
              </div>
            </div>

            {/* Gemini Key */}
            <div className="rounded-lg bg-[#090f1d] border border-terminal-border p-3.5 space-y-2 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-slate-200">
                  Google Gemini API Key (100% Gratuita — sem cartão)
                </span>
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:underline"
                >
                  Obter chave grátis <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  type="password"
                  value={geminiKeyInput}
                  onChange={(e) => setGeminiKeyInput(e.target.value)}
                  placeholder={
                    data?.ai?.gemini_configured
                      ? `Chave atual: ${data.ai.gemini_api_key_masked} (escreve nova para substituir)`
                      : 'Cola aqui a tua GEMINI_API_KEY (AIza...)'
                  }
                  className="flex-1 px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
                {data?.ai?.gemini_configured && (
                  <button
                    type="button"
                    onClick={handleClearGeminiKey}
                    className="px-3 py-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/40 text-rose-300 text-xs"
                  >
                    Limpar Chave
                  </button>
                )}
              </div>
            </div>

            {/* Ollama Local */}
            <div className="rounded-lg bg-[#090f1d] border border-terminal-border p-3.5 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">Ollama Local (100% Offline)</span>
                <StatusBadge variant={data?.ai?.ollama_online ? 'green' : 'slate'}>
                  {data?.ai?.ollama_online ? 'OLLAMA DETETADO' : 'OLLAMA OFFLINE'}
                </StatusBadge>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">URL Local</label>
                  <input
                    type="text"
                    value={ollamaUrl}
                    onChange={(e) => setOllamaUrl(e.target.value)}
                    className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">Modelo Texto</label>
                  <input
                    type="text"
                    value={ollamaModel}
                    onChange={(e) => setOllamaModel(e.target.value)}
                    className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">Modelo Visão</label>
                  <input
                    type="text"
                    value={ollamaVisionModel}
                    onChange={(e) => setOllamaVisionModel(e.target.value)}
                    className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                  />
                </div>
              </div>
              {(data?.ai?.ollama_installed_models || []).length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-slate-400">Modelos instalados:</span>
                  {data.ai.ollama_installed_models.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => (m.includes('vl') || m.includes('vision') || m.includes('llava') ? setOllamaVisionModel(m) : setOllamaModel(m))}
                      className="px-2 py-0.5 rounded bg-cyan-500/15 border border-cyan-500/35 text-cyan-300 font-mono text-[10px] hover:bg-cyan-500/25"
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Risk Profile & Notifications (5 cols) */}
          <div className="xl:col-span-5 space-y-5">
            <section className="terminal-card p-5 space-y-3.5">
              <div className="flex items-center gap-2 border-b border-terminal-border pb-3">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Perfil de Risco &amp; Capital Padrão</h3>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Capital Base Padrão (€)</label>
                  <input
                    type="number"
                    min="10"
                    step="10"
                    value={defaultCapital}
                    onChange={(e) => setDefaultCapital(e.target.value)}
                    className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white text-sm font-bold"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Stop-Loss Padrão (%) — Teto 7%</label>
                  <input
                    type="number"
                    min="1"
                    max="7"
                    step="0.5"
                    value={defaultStop}
                    onChange={(e) => setDefaultStop(Math.min(Number(e.target.value), 7.0))}
                    className="w-full px-3 py-2 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-rose-400 text-sm font-bold"
                  />
                </div>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Estes valores pré-preenchem automaticamente a <strong>Calculadora de Posição</strong> e definem o capital inicial de referência da curva de capital no <strong>Paper Trading</strong>.
              </p>
            </section>

            <section className="terminal-card p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-terminal-border pb-3">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-bold text-white">Alertas Telemóvel (Telegram / Discord)</h3>
                </div>
                <button
                  type="button"
                  onClick={onOpenAlerts}
                  className="px-2.5 py-1 text-xs rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-300 font-medium"
                >
                  Configurar Canais
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusBadge variant={data?.notifications?.telegram_configured ? 'green' : 'slate'}>
                  Telegram: {data?.notifications?.telegram_configured ? 'ATIVO' : 'Desligado'}
                </StatusBadge>
                <StatusBadge variant={data?.notifications?.discord_configured ? 'green' : 'slate'}>
                  Discord: {data?.notifications?.discord_configured ? 'ATIVO' : 'Desligado'}
                </StatusBadge>
              </div>
              <p className="text-[11px] text-slate-400">
                Podes configurar tokens gratuitos de Telegram ou Webhook do Discord diretamente na Central de Alertas.
              </p>
            </section>
          </div>
        </div>

        {/* Row 2: 1-Click Scanner Universe Packs */}
        <section className="terminal-card p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <div>
                <h3 className="text-sm font-bold text-white">Pacotes de Universo do Scanner (1-Clique)</h3>
                <p className="text-[11px] text-slate-400">
                  Adiciona grupos temáticos inteiros à watchlist ou substitui a lista de ações/cripto sem escrever ticker a ticker.
                </p>
              </div>
            </div>
            <StatusBadge variant="cyan">{storage.watchlist_active ?? 0} ativos na Watchlist</StatusBadge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {(data?.universe_packs || []).map((pack) => {
              const pct = Math.round((pack.in_watchlist / Math.max(pack.total_tickers, 1)) * 100)
              return (
                <div
                  key={pack.id}
                  className="rounded-xl bg-[#090f1d] border border-terminal-border p-4 flex flex-col justify-between gap-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-white">{pack.name}</span>
                      <StatusBadge variant={pack.asset_type === 'crypto' ? 'purple' : 'slate'}>
                        {pack.total_tickers} {pack.asset_type === 'crypto' ? 'Cripto' : 'Ações'}
                      </StatusBadge>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{pack.description}</p>
                    <div className="text-[10px] font-mono text-slate-500 truncate">
                      {pack.sample_tickers.join(' • ')}…
                    </div>
                    <div className="pt-1">
                      <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                        <span>Na watchlist</span>
                        <span className="text-cyan-300">
                          {pack.in_watchlist}/{pack.total_tickers} ({pct}%)
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-[#070b14] overflow-hidden">
                        <div className="h-full bg-cyan-400" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleApplyPack(pack.id, 'add')}
                      className="flex-1 py-1.5 text-[11px] font-semibold rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 transition"
                    >
                      + Adicionar Pacote
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApplyPack(pack.id, 'replace_class')}
                      className="px-2.5 py-1.5 text-[11px] rounded-lg bg-terminal-card hover:bg-terminal-hover border border-terminal-border text-slate-300 transition"
                      title={`Substituir todas as ${pack.asset_type === 'crypto' ? 'cripto' : 'ações'} da watchlist por este pacote`}
                    >
                      Usar Só Este
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Row 3: Cache SQLite & Background Scheduler */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          {/* Cache Control (7 cols) */}
          <section className="xl:col-span-7 terminal-card p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Cache Inteligente SQLite &amp; Armazenamento</h3>
              </div>
              <span className="font-mono text-xs text-slate-400">
                DB: <strong className="text-white">{storage.db_size_kb ?? 0} KB</strong> • {storage.cache_total ?? 0} entradas
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono">
              {[
                { label: 'Preços / OHLCV', val: storage.cache_by_category?.prices ?? 0 },
                { label: 'Notícias RSS', val: storage.cache_by_category?.news ?? 0 },
                { label: 'Fundamentais', val: storage.cache_by_category?.fundamentals ?? 0 },
                { label: 'Scan Snapshots', val: storage.scan_snapshots ?? 0 },
              ].map((st) => (
                <div key={st.label} className="bg-[#090f1d] border border-terminal-border rounded-lg p-2.5">
                  <div className="text-[10px] font-sans text-slate-400">{st.label}</div>
                  <div className="text-lg font-bold text-white mt-0.5">{st.val}</div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">TTL Preços (seg)</label>
                <input
                  type="number"
                  min="60"
                  value={ttlPrices}
                  onChange={(e) => setTtlPrices(e.target.value)}
                  className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">TTL Notícias (seg)</label>
                <input
                  type="number"
                  min="60"
                  value={ttlNews}
                  onChange={(e) => setTtlNews(e.target.value)}
                  className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">TTL Scanner (seg)</label>
                <input
                  type="number"
                  min="300"
                  value={ttlScan}
                  onChange={(e) => setTtlScan(e.target.value)}
                  className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">TTL Fundam. (seg)</label>
                <input
                  type="number"
                  min="300"
                  value={ttlFund}
                  onChange={(e) => setTtlFund(e.target.value)}
                  className="w-full px-2.5 py-1.5 font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              {[
                { k: 'prices', l: 'Limpar Preços' },
                { k: 'news', l: 'Limpar Notícias' },
                { k: 'ai', l: 'Limpar Briefings IA' },
                { k: 'all', l: 'Limpar Toda a Cache', danger: true },
              ].map((btn) => (
                <button
                  key={btn.k}
                  type="button"
                  onClick={() => handleClearCache(btn.k)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-lg border transition ${btn.danger
                    ? 'bg-rose-500/15 hover:bg-rose-500/25 border-rose-500/40 text-rose-300 font-semibold'
                    : 'bg-terminal-card hover:bg-terminal-hover border-terminal-border text-slate-300'
                    }`}
                >
                  <Trash2 className="w-3 h-3" />
                  {btn.l}
                </button>
              ))}
            </div>
          </section>

          {/* APScheduler (5 cols) */}
          <section className="xl:col-span-5 terminal-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-terminal-border pb-3">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-white">Agendador Automático (APScheduler)</h3>
              </div>
              <label className="inline-flex items-center gap-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={schedulerEnabled}
                  onChange={(e) => setSchedulerEnabled(e.target.checked)}
                  className="accent-emerald-500"
                />
                <span className={schedulerEnabled ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {schedulerEnabled ? 'ATIVO' : 'PAUSADO'}
                </span>
              </label>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-300">Atualizar Macro &amp; Rotação (minutos)</span>
                <input
                  type="number"
                  min="5"
                  value={macroMins}
                  onChange={(e) => setMacroMins(e.target.value)}
                  className="w-20 px-2.5 py-1.5 font-mono text-right bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-300">Verificar Stops -6%, 2R &amp; Alertas (minutos)</span>
                <input
                  type="number"
                  min="2"
                  value={paperMins}
                  onChange={(e) => setPaperMins(e.target.value)}
                  className="w-20 px-2.5 py-1.5 font-mono text-right bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-300">Scanner Completo SEPA/VCP (horas)</span>
                <input
                  type="number"
                  min="1"
                  value={scanHours}
                  onChange={(e) => setScanHours(e.target.value)}
                  className="w-20 px-2.5 py-1.5 font-mono text-right bg-[#070b14] border border-terminal-border rounded-lg text-white"
                />
              </div>
            </div>

            <p className="text-[11px] text-slate-500 leading-relaxed">
              Ao guardar alterações nos intervalos, o scheduler reinicia automaticamente em background com a nova periodicidade.
            </p>
          </section>
        </div>
      </form>
    </div>
  )
}
