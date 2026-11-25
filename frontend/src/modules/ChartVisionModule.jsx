import React, { useEffect, useRef, useState } from 'react'
import {
  BookOpen,
  Camera,
  ClipboardPaste,
  History,
  ShieldAlert,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
  Upload,
} from 'lucide-react'
import { api, formatTimestamp } from '../services/api'
import { StatusBadge } from '../components/StatusBadge'

export function ChartVisionModule({ onSimulateTrade }) {
  const [imagePreview, setImagePreview] = useState(null)
  const [imageB64, setImageB64] = useState('')
  const [mimeType, setMimeType] = useState('image/png')
  const [ticker, setTicker] = useState('')
  const [timeframe, setTimeframe] = useState('Diário')
  const [notes, setNotes] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const loadHistory = async () => {
    try {
      const res = await api.getVisionHistory()
      setHistory(res.items || [])
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  const ingestFile = (file) => {
    if (!file || !file.type.startsWith('image/')) {
      setError('Por favor seleciona ou cola uma imagem válida (PNG, JPG ou WEBP).')
      return
    }
    setError(null)
    setMimeType(file.type)
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      setImagePreview(dataUrl)
      setImageB64(dataUrl)
    }
    reader.readAsDataURL(file)
  }

  // Global Ctrl+V clipboard paste handler while module is mounted
  useEffect(() => {
    const onPaste = (e) => {
      const items = e.clipboardData?.items || []
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile()
          if (blob) {
            ingestFile(blob)
            e.preventDefault()
            break
          }
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  const handleAnalyze = async () => {
    if (!imageB64) {
      setError('Cola (Ctrl+V) ou carrega primeiro um screenshot de gráfico.')
      return
    }
    try {
      setAnalyzing(true)
      setError(null)
      const res = await api.analyzeChartVision({
        image_base64: imageB64,
        mime_type: mimeType,
        ticker: ticker.trim() || null,
        timeframe,
        notes: notes.trim() || null,
      })
      setResult(res)
      loadHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const clearImage = () => {
    setImagePreview(null)
    setImageB64('')
    setResult(null)
    setError(null)
  }

  const report = result?.report
  const plan = report?.trade_plan

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Analisador de Prints de Gráficos (Visão IA)</h2>
        <p className="text-xs text-slate-400">
          Cola diretamente um print do TradingView ou corretora (<kbd className="px-1.5 py-0.5 rounded bg-terminal-card border border-terminal-border font-mono text-cyan-300">Ctrl+V</kbd>) ou arrasta o ficheiro. Se indicares o ticker, cruzamos com dados SEPA e notícias em tempo real.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Left: Upload / Paste Zone & Controls (5 cols) */}
        <div className="xl:col-span-5 space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              const f = e.dataTransfer?.files?.[0]
              if (f) ingestFile(f)
            }}
            className={`terminal-card p-5 border-2 border-dashed transition ${
              dragOver
                ? 'border-cyan-400 bg-cyan-500/10'
                : 'border-terminal-border hover:border-cyan-500/50'
            }`}
          >
            {imagePreview ? (
              <div className="space-y-3">
                <div className="relative rounded-lg overflow-hidden border border-terminal-border bg-[#050810]">
                  <img src={imagePreview} alt="Pré-visualização do gráfico" className="w-full max-h-72 object-contain" />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-emerald-400 font-mono">Imagem pronta para análise</span>
                  <button
                    onClick={clearImage}
                    className="inline-flex items-center gap-1 text-rose-400 hover:text-rose-300"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Limpar
                  </button>
                </div>
              </div>
            ) : (
              <div
                onClick={() => fileInputRef.current?.click()}
                className="py-10 text-center cursor-pointer space-y-3"
              >
                <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400">
                  <ClipboardPaste className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-200">
                    Carrega <span className="text-cyan-300 font-mono">Ctrl+V</span> para colar o print aqui
                  </p>
                  <p className="text-xs text-slate-400 mt-1">ou arrasta / clica para escolher imagem (PNG, JPG, WEBP)</p>
                </div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-terminal-card border border-terminal-border text-slate-300">
                  <Upload className="w-3.5 h-3.5" />
                  Escolher Ficheiro
                </span>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && ingestFile(e.target.files[0])}
            />
          </div>

          <div className="terminal-card p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Ticker (Opcional — cruza c/ notícias)</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="Ex: NVDA, SOL-USD"
                  className="w-full px-3 py-2 text-xs font-mono bg-[#070b14] border border-terminal-border rounded-lg text-white focus:outline-none focus:border-cyan-500/60"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Timeframe do Print</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-[#070b14] border border-terminal-border rounded-lg text-slate-200"
                >
                  <option>Diário</option>
                  <option>Semanal</option>
                  <option>4 Horas</option>
                  <option>1 Hora</option>
                  <option>15 Minutos</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Contexto / Dúvida (Opcional)</label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Ex: Parece um VCP pronto a romper ou está esticado?"
                className="w-full px-3 py-2 text-xs bg-[#070b14] border border-terminal-border rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500/60"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2.5 text-xs text-rose-300">
                {error}
              </div>
            )}

            <button
              onClick={handleAnalyze}
              disabled={analyzing || !imageB64}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-cyan-500/25 to-emerald-500/25 hover:from-cyan-500/35 hover:to-emerald-500/35 border border-cyan-500/50 text-sm font-semibold text-white inline-flex items-center justify-center gap-2 transition disabled:opacity-45"
            >
              <Sparkles className={`w-4 h-4 text-cyan-300 ${analyzing ? 'animate-spin' : ''}`} />
              {analyzing ? 'A analisar imagem + contexto...' : 'Analisar Gráfico com Visão IA'}
            </button>
          </div>
        </div>

        {/* Right: Structured Vision Report (7 cols) */}
        <div className="xl:col-span-7 space-y-4">
          {!report ? (
            <div className="terminal-card p-10 text-center space-y-3 h-full flex flex-col justify-center">
              <Camera className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-300">Relatório Estruturado de Visão IA</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Recebe avaliação de Tendência & Estrutura, Padrões/Suportes, Risco de Fakeout/Extensão, Plano com Stop &lt;= 6% e Dica de Estudo personalizada. Funciona com Gemini Free Tier, Ollama local (qwen2.5-vl / llama3.2-vision) ou fallback quantitativo.
              </p>
            </div>
          ) : (
            <div className="terminal-card p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-terminal-border pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-base font-bold text-white">
                    Relatório Técnico {result.ticker ? `— ${result.ticker}` : ''}
                  </h3>
                </div>
                <StatusBadge variant={result.ai_mode === 'fallback' ? 'yellow' : 'cyan'}>
                  {result.provider}
                </StatusBadge>
              </div>

              {result.warning && (
                <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
                  {result.warning}
                </div>
              )}

              <div className="space-y-3 text-xs">
                <div className="rounded-lg bg-[#090f1d] border border-terminal-border p-3.5">
                  <div className="font-bold text-cyan-300 mb-1 flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5" />
                    1. Tendência e Estrutura
                  </div>
                  <p className="text-slate-200 leading-relaxed">{report.trend_and_structure}</p>
                </div>

                <div className="rounded-lg bg-[#090f1d] border border-terminal-border p-3.5">
                  <div className="font-bold text-emerald-300 mb-1 flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5" />
                    2. Padrões e Níveis-Chave (Suporte / Resistência)
                  </div>
                  <p className="text-slate-200 leading-relaxed">{report.patterns_and_levels}</p>
                </div>

                <div className="rounded-lg bg-rose-500/5 border border-rose-500/25 p-3.5">
                  <div className="font-bold text-rose-400 mb-1 flex items-center gap-1.5">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    3. Avaliação de Risco (Fakeout / Extensão)
                  </div>
                  <p className="text-slate-200 leading-relaxed">{report.risk_assessment}</p>
                </div>

                {/* Structured Trade Plan */}
                <div
                  className={`rounded-lg p-3.5 space-y-2 border ${
                    plan?.bias === 'EVITAR'
                      ? 'bg-rose-500/10 border-rose-500/40'
                      : 'bg-emerald-500/5 border-emerald-500/30'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`font-bold ${plan?.bias === 'EVITAR' ? 'text-rose-300' : 'text-emerald-300'}`}>
                      4. Sugestão de Plano (Stop &lt;= 6%)
                    </span>
                    <StatusBadge
                      variant={
                        plan?.bias === 'COMPRA_NO_PIVO'
                          ? 'green'
                          : plan?.bias === 'EVITAR'
                            ? 'red'
                            : 'yellow'
                      }
                    >
                      {plan?.bias || 'AGUARDAR'}
                    </StatusBadge>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                    <div className="bg-[#070b14] rounded p-2.5 border border-terminal-border">
                      <div className="text-[10px] text-slate-400">Entrada</div>
                      <div className="text-slate-100 mt-0.5">{plan?.entry_zone}</div>
                    </div>
                    <div className="bg-[#070b14] rounded p-2.5 border border-rose-500/30">
                      <div className="text-[10px] text-rose-400">Stop-Loss (&lt;= {plan?.max_stop_pct ?? 6}%)</div>
                      <div className="text-slate-100 mt-0.5">{plan?.stop_loss_rule}</div>
                    </div>
                    <div className="bg-[#070b14] rounded p-2.5 border border-emerald-500/25">
                      <div className="text-[10px] text-emerald-400">Alvos (2R / 3R)</div>
                      <div className="text-slate-100 mt-0.5">{plan?.targets}</div>
                    </div>
                  </div>

                  {result.ticker_context?.sepa && plan?.bias !== 'EVITAR' && (
                    <div className="pt-2">
                      <button
                        onClick={() =>
                          onSimulateTrade({
                            ticker: result.ticker,
                            asset_type: result.ticker_context.sepa.asset_type,
                            entry_price: result.ticker_context.sepa.price,
                            stop_loss_pct: Math.min(plan?.max_stop_pct || 6.0, 6.0),
                            notes: `Análise Visão IA (${plan?.bias})`,
                          })
                        }
                        className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40"
                      >
                        Enviar {result.ticker} para Paper Trading
                      </button>
                    </div>
                  )}
                </div>

                <div className="rounded-lg bg-cyan-500/10 border border-cyan-500/30 p-3.5">
                  <div className="font-bold text-cyan-300 mb-1 flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5" />
                    5. Dica de Estudo
                  </div>
                  <p className="text-slate-100 leading-relaxed">{report.study_tip}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* History */}
      {history.length > 0 && (
        <div className="terminal-card p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
            <History className="w-4 h-4 text-cyan-400" />
            Histórico Recente de Análises de Gráficos (SQLite)
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            {history.slice(0, 6).map((h) => (
              <button
                key={h.id}
                onClick={() =>
                  setResult({
                    ticker: h.ticker,
                    provider: h.provider,
                    ai_mode: h.provider.includes('Local') ? 'fallback' : 'ai',
                    report: h.report,
                  })
                }
                className="text-left p-3 rounded-lg bg-[#090f1d] border border-terminal-border hover:border-cyan-500/40 transition"
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-mono font-bold text-cyan-300">{h.ticker || 'Gráfico Livre'}</span>
                  <span className="text-[10px] text-slate-500 font-mono">{formatTimestamp(h.created_at)}</span>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2">{h.report?.trend_and_structure}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
