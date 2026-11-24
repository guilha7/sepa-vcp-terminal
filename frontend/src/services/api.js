const API_BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const msg =
      typeof data?.detail === 'string'
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ')
          : `Erro HTTP ${res.status}`
    throw new Error(msg)
  }
  return data
}

export const api = {
  getHealth: () => request('/health'),

  // Module 1: Macro & Sector Rotation
  getMacroOverview: (forceRefresh = false) =>
    request(`/macro/overview?force_refresh=${forceRefresh}`),

  // Module 2: SEPA/VCP Scanner, SSE Streaming & Quick Chart
  getScannerResults: (assetType = '', forceRefresh = false) => {
    const params = new URLSearchParams()
    if (assetType) params.set('asset_type', assetType)
    if (forceRefresh) params.set('force_refresh', 'true')
    const q = params.toString()
    return request(`/scanner/results${q ? `?${q}` : ''}`)
  },
  runScanner: (assetType = '') => {
    const q = assetType ? `?asset_type=${assetType}` : ''
    return request(`/scanner/run${q}`, { method: 'POST' })
  },
  streamScanner: (assetType = '', { onProgress, onComplete, onError }) => {
    const params = new URLSearchParams({ force_refresh: 'true' })
    if (assetType) params.set('asset_type', assetType)
    const es = new EventSource(`${API_BASE}/scanner/stream?${params.toString()}`)
    es.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'progress') onProgress?.(msg)
        else if (msg.type === 'complete') {
          es.close()
          onComplete?.(msg.result)
        } else if (msg.type === 'error') {
          es.close()
          onError?.(new Error(msg.message || 'Erro durante scan SSE'))
        }
      } catch {
        // ignore parse glitch
      }
    }
    es.onerror = () => {
      es.close()
      onError?.(new Error('Ligação SSE interrompida.'))
    }
    return () => es.close()
  },
  getQuickChart: (ticker) => request(`/scanner/chart/${encodeURIComponent(ticker)}`),
  getWatchlist: () => request('/scanner/watchlist'),
  addWatchlistTicker: (ticker, asset_type) =>
    request('/scanner/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker, asset_type }),
    }),
  removeWatchlistTicker: (ticker) =>
    request(`/scanner/watchlist/${encodeURIComponent(ticker)}`, {
      method: 'DELETE',
    }),

  // Module 3: Asset X-Ray
  getXRay: (ticker, forceRefresh = false) =>
    request(`/xray/${encodeURIComponent(ticker)}?force_refresh=${forceRefresh}`),

  // Module 4: Chart Vision AI
  analyzeChartVision: (payload) =>
    request('/vision/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getVisionHistory: () => request('/vision/history'),

  // Module 5: Risk Calculator, FX, Paper Trading & Journal
  getFxRate: (forceRefresh = false) => request(`/risk/fx?force_refresh=${forceRefresh}`),
  calculatePosition: (payload) =>
    request('/risk/calculate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getPaperPortfolio: (refresh = false) =>
    request(`/paper/portfolio?refresh=${refresh}`),
  openPaperPosition: (payload) =>
    request('/paper/positions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  movePositionBreakeven: (id) =>
    request(`/paper/positions/${id}/breakeven`, { method: 'POST' }),
  updatePositionJournal: (id, payload) =>
    request(`/paper/positions/${id}/journal`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  closePaperPosition: (id, exitPrice = null, journalLesson = null) =>
    request(`/paper/positions/${id}/close`, {
      method: 'POST',
      body: JSON.stringify({
        exit_price: exitPrice,
        reason: 'CLOSED_MANUAL',
        journal_lesson: journalLesson,
      }),
    }),
  deletePaperPosition: (id) =>
    request(`/paper/positions/${id}`, { method: 'DELETE' }),
  refreshPaperPortfolio: () =>
    request('/paper/refresh', { method: 'POST' }),

  // Alerts & External Notifications (Telegram / Discord + Price Alerts)
  getAlertsOverview: (limit = 40) => request(`/alerts?limit=${limit}`),
  markAlertsRead: () => request('/alerts/read-all', { method: 'POST' }),
  createPriceAlert: (payload) =>
    request('/alerts/price', { method: 'POST', body: JSON.stringify(payload) }),
  deletePriceAlert: (id) =>
    request(`/alerts/price/${id}`, { method: 'DELETE' }),
  checkPriceAlertsNow: () => request('/alerts/price/check', { method: 'POST' }),
  updateAlertChannels: (payload) =>
    request('/alerts/channels', { method: 'POST', body: JSON.stringify(payload) }),
  testAlertChannels: () => request('/alerts/test', { method: 'POST' }),
  exportAlertsToCloud: () => request('/alerts/export-cloud', { method: 'POST' }),

  // Module 6 / Settings: Runtime AI, Risk, Universe Packs, Cache & Scheduler
  getSettings: () => request('/settings'),
  saveSettings: (payload) =>
    request('/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  testAiConnection: () => request('/settings/test-ai', { method: 'POST' }),
  applyUniversePack: (pack_id, mode = 'add') =>
    request('/settings/universe-pack', {
      method: 'POST',
      body: JSON.stringify({ pack_id, mode }),
    }),
  clearCache: (category = 'all') =>
    request('/settings/cache/clear', {
      method: 'POST',
      body: JSON.stringify({ category }),
    }),
}

export function formatPrice(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return '—'
  const n = Number(val)
  if (Math.abs(n) >= 1000) return n.toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (Math.abs(n) >= 1) return n.toLocaleString('pt-PT', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
  if (Math.abs(n) >= 0.01) return n.toLocaleString('pt-PT', { minimumFractionDigits: 4, maximumFractionDigits: 5 })
  return n.toLocaleString('pt-PT', { minimumFractionDigits: 6, maximumFractionDigits: 7 })
}

export function formatPct(val, showSign = true) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return '—'
  const n = Number(val)
  const sign = showSign && n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

export function formatCompactNumber(val) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return '—'
  const n = Number(val)
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(1)}K`
  return `$${n.toFixed(0)}`
}

export function formatTimestamp(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts * 1000).toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}
