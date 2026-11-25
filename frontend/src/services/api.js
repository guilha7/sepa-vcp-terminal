const API_BASE = '/api'
const TOKEN_STORAGE_KEY = 'sepa_access_token'
const ADMIN_TOKEN_KEY = 'sepa_admin_token'
const USER_NAME_KEY = 'sepa_user_name'

export function getStoredAccessToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function setStoredAccessToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // ignore
  }
}

export function getStoredAdminToken() {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setStoredAdminToken(token) {
  try {
    if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token)
    else localStorage.removeItem(ADMIN_TOKEN_KEY)
  } catch {
    // ignore
  }
}

export function getStoredUserName() {
  try {
    return (localStorage.getItem(USER_NAME_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function setStoredUserName(name) {
  try {
    const clean = (name || '').trim()
    if (clean) localStorage.setItem(USER_NAME_KEY, clean)
    else localStorage.removeItem(USER_NAME_KEY)
  } catch {
    // ignore
  }
}

async function request(path, options = {}) {
  const token = getStoredAccessToken()
  const adminToken = getStoredAdminToken()
  const userName = getStoredUserName()
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Access-Token': token } : {}),
      ...(adminToken ? { 'X-Admin-Token': adminToken } : {}),
      ...(userName ? { 'X-User-Name': userName } : {}),
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
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  getAuthStatus: () => request('/auth/status'),
  login: (password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  adminLogin: (password) =>
    request('/auth/admin-login', { method: 'POST', body: JSON.stringify({ password }) }),
  getHealth: () => request('/health'),

  // Module 1: Macro & Sector Rotation
  getMacroOverview: (forceRefresh = false) =>
    request(`/macro/overview?force_refresh=${forceRefresh}`),

  // Module 2: SEPA/VCP Scanner, SSE Streaming & Quick Chart
  getScannerResults: (assetType = '', forceRefresh = false, cacheOnly = false) => {
    const params = new URLSearchParams()
    if (assetType) params.set('asset_type', assetType)
    if (forceRefresh) params.set('force_refresh', 'true')
    if (cacheOnly) params.set('cache_only', 'true')
    const q = params.toString()
    return request(`/scanner/results${q ? `?${q}` : ''}`)
  },
  runScanner: (assetType = '') => {
    const q = assetType ? `?asset_type=${assetType}` : ''
    return request(`/scanner/run${q}`, { method: 'POST' })
  },
  streamScanner: (assetType = '', { forceRefresh = true, onProgress, onComplete, onError }) => {
    const params = new URLSearchParams({ force_refresh: String(Boolean(forceRefresh)) })
    if (assetType) params.set('asset_type', assetType)
    const token = getStoredAccessToken()
    if (token) params.set('access_token', token)
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
  getUsDiscoveryPresets: () => request('/scanner/us-discovery/presets'),
  streamUsDiscovery: (preset = 'sepa_leaders', limit = 70, forceRefresh = false, { onProgress, onComplete, onError }) => {
    const params = new URLSearchParams({
      preset,
      limit: String(limit),
      force_refresh: String(Boolean(forceRefresh)),
    })
    const token = getStoredAccessToken()
    if (token) params.set('access_token', token)
    const es = new EventSource(`${API_BASE}/scanner/us-discovery/stream?${params.toString()}`)
    es.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'progress') onProgress?.(msg)
        else if (msg.type === 'complete') {
          es.close()
          onComplete?.(msg.result)
        } else if (msg.type === 'error') {
          es.close()
          onError?.(new Error(msg.message || 'Erro durante descoberta EUA'))
        }
      } catch {
        // ignore parse glitch
      }
    }
    es.onerror = () => {
      es.close()
      onError?.(new Error('Ligação SSE interrompida durante descoberta EUA.'))
    }
    return () => es.close()
  },
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
  getPaperPortfolio: (refresh = false, baseCapital = null) => {
    const params = new URLSearchParams({ refresh: String(Boolean(refresh)) })
    if (baseCapital && Number(baseCapital) > 0) params.set('base_capital', String(Number(baseCapital)))
    return request(`/paper/portfolio?${params.toString()}`)
  },
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
  refreshPaperPortfolio: (baseCapital = null) => {
    const q = baseCapital && Number(baseCapital) > 0 ? `?base_capital=${Number(baseCapital)}` : ''
    return request(`/paper/refresh${q}`, { method: 'POST' })
  },

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
  sendMorningBriefingNow: () => request('/alerts/send-morning-briefing', { method: 'POST' }),
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

export function formatCompactNumber(val, currency = 'USD') {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return '—'
  const n = Number(val)
  const sign = n < 0 ? '-' : ''
  const abs = Math.abs(n)
  const ccy = (currency || 'USD').toUpperCase()
  const prefix = ccy === 'EUR' ? '€' : ccy === 'GBP' ? '£' : '$'
  if (abs >= 1e12) return `${sign}${prefix}${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}${prefix}${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}${prefix}${(abs / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${sign}${prefix}${(abs / 1e3).toFixed(1)}K`
  return `${sign}${prefix}${abs.toFixed(0)}`
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
