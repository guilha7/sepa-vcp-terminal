import React, { useState } from 'react'
import { ArrowRight, TrendingUp, User } from 'lucide-react'
import { setStoredUserName } from '../services/api'

export function WelcomeNameModal({ initialName = '', onConfirm }) {
  const [name, setName] = useState(initialName)

  const handleSubmit = (e) => {
    e.preventDefault()
    const clean = name.trim()
    if (!clean) return
    setStoredUserName(clean)
    onConfirm(clean)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-terminal-bg px-4">
      <form
        onSubmit={handleSubmit}
        className="terminal-card w-full max-w-md p-7 space-y-5 border-cyan-500/35"
      >
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-500/30 via-cyan-500/20 to-blue-500/20 border border-emerald-400/40 flex items-center justify-center shadow-lg">
            <TrendingUp className="w-6 h-6 text-emerald-300" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold bg-gradient-to-r from-white via-cyan-100 to-emerald-300 bg-clip-text text-transparent">
              SEPA / VCP DESK
            </h1>
            <p className="text-xs text-slate-400">Terminal de Análise &amp; Paper Trading</p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs text-slate-200 font-semibold flex items-center gap-1.5">
            <User className="w-3.5 h-3.5 text-cyan-400" />
            Como te chamas?
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex: Guilherme, João, Diogo..."
            maxLength={30}
            autoFocus
            className="w-full px-3.5 py-2.5 text-sm bg-[#060a13] border border-terminal-border rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-400"
          />
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Sem registo nem password — o teu nome serve apenas para guardar o teu próprio{' '}
            <strong>Paper Trading e Diário</strong> separados dos teus amigos.
          </p>
        </div>

        <button
          type="submit"
          disabled={!name.trim()}
          className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500/30 to-emerald-500/30 hover:from-cyan-500/40 hover:to-emerald-500/40 border border-cyan-400/50 text-sm font-semibold text-white inline-flex items-center justify-center gap-2 transition disabled:opacity-45"
        >
          Entrar no Terminal
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
