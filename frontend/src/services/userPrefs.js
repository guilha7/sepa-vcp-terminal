const PREFS_KEY_PREFIX = 'sepa_user_prefs_v1_'

function normalizeUserKey(userName) {
  const clean = (userName || 'default').trim().toLowerCase().replace(/\s+/g, '_')
  return `${PREFS_KEY_PREFIX}${clean || 'default'}`
}

export function sanitizeTicker(raw) {
  return (raw || '').trim().toUpperCase().replace(/[^A-Z0-9.\-^=]/g, '').slice(0, 16)
}

export function clampNumber(val, min, max, fallback) {
  const n = Number(val)
  if (!Number.isFinite(n)) return fallback
  return Math.min(Math.max(n, min), max)
}

export function loadUserPrefs(userName, serverDefaults = {}) {
  const defaultCapital = clampNumber(serverDefaults.capitalEur, 10, 10000000, 100)
  const defaultStop = clampNumber(serverDefaults.stopLossPct, 1.0, 7.0, 6.0)
  const base = {
    capitalEur: defaultCapital,
    stopLossPct: defaultStop,
    riskPerTradePct: 2.0,
    favorites: [],
    customized: false,
  }

  try {
    const raw = localStorage.getItem(normalizeUserKey(userName))
    if (!raw) return base
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return base

    const favs = Array.isArray(parsed.favorites)
      ? [...new Set(parsed.favorites.map(sanitizeTicker).filter(Boolean))]
      : []

    return {
      capitalEur: clampNumber(parsed.capitalEur, 10, 10000000, defaultCapital),
      stopLossPct: clampNumber(parsed.stopLossPct, 1.0, 7.0, defaultStop),
      riskPerTradePct: clampNumber(parsed.riskPerTradePct, 0.25, 5.0, 2.0),
      favorites: favs,
      customized: Boolean(parsed.customized),
    }
  } catch {
    return base
  }
}

export function saveUserPrefs(userName, partial, serverDefaults = {}) {
  const current = loadUserPrefs(userName, serverDefaults)
  const favs =
    partial.favorites !== undefined
      ? [...new Set((partial.favorites || []).map(sanitizeTicker).filter(Boolean))]
      : current.favorites

  const next = {
    capitalEur: clampNumber(
      partial.capitalEur !== undefined ? partial.capitalEur : current.capitalEur,
      10,
      10000000,
      current.capitalEur,
    ),
    stopLossPct: clampNumber(
      partial.stopLossPct !== undefined ? partial.stopLossPct : current.stopLossPct,
      1.0,
      7.0,
      current.stopLossPct,
    ),
    riskPerTradePct: clampNumber(
      partial.riskPerTradePct !== undefined ? partial.riskPerTradePct : current.riskPerTradePct,
      0.25,
      5.0,
      current.riskPerTradePct,
    ),
    favorites: favs,
    customized: true,
  }

  try {
    localStorage.setItem(normalizeUserKey(userName), JSON.stringify(next))
  } catch {
    // ignore storage quota errors
  }
  return next
}

export function toggleFavoriteTicker(userName, ticker, serverDefaults = {}) {
  const tk = sanitizeTicker(ticker)
  const current = loadUserPrefs(userName, serverDefaults)
  if (!tk) return current
  const exists = current.favorites.includes(tk)
  const nextFavs = exists ? current.favorites.filter((t) => t !== tk) : [tk, ...current.favorites]
  return saveUserPrefs(userName, { favorites: nextFavs }, serverDefaults)
}
