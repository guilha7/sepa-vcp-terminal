import React, { useState } from 'react'
import { Lock, TrendingUp } from 'lucide-react'
import { api, setStoredAccessToken } from '../services/api'

export function LoginGate({ onUnlocked }) {
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!password.trim()) return
    try {
      setLoading(true)
      setError(null)
      const res = await api.login(password)
      setStoredAccessToken(res.token || '')
      onUnlocked()
    } catch (err) {
      setError(err.message || 'Password incorreta.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-terminal-bg px-4">
      <form
        onSubmit={handleSubmit}
        className="terminal-card w-full max-w-md p-7 space-y-5 border-cyan-500/35"
      >
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-500/30 to-cyan-500/20 border border-emerald-400/40 flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-emerald-300" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold bg-gradient-to-r from-white via-cyan-100 to-emerald-300 bg-clip-text text-transparent">
              SEPA / VCP DESK
            </h1>
            <p className="text-xs text-slate-400">Acesso Privado Protegido</p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-cyan-400" />
            Password de Acesso
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Insere a tua password..."
            autoFocus
            className="w-full px-3.5 py-2.5 text-sm font-mono bg-[#060a13] border border-terminal-border rounded-xl text-white focus:outline-none focus:border-cyan-400"
          />
        </div>

        {error && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/40 px-3 py-2 text-xs text-rose-300">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500/30 to-emerald-500/30 hover:from-cyan-500/40 hover:to-emerald-500/40 border border-cyan-400/50 text-sm font-semibold text-white transition disabled:opacity-50"
        >
          {loading ? 'A verificar...' : 'Entrar no Terminal'}
        </button>
      </form>
    </div>
  )
}
