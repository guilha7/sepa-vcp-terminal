import React from 'react'
import { ArrowRight, Compass, X } from 'lucide-react'

const STEPS = [
  {
    num: '01',
    tab: 'macro',
    title: 'Ver o Semáforo & Fluxo',
    desc: 'Descobre se o mercado está Verde (Risk-On), quantos Dias de Distribuição existem e em que setores está a entrar dinheiro.',
    cta: 'Abrir Macro',
    accent: 'from-emerald-500/20 to-cyan-500/10 border-emerald-500/35 text-emerald-300',
  },
  {
    num: '02',
    tab: 'scanner',
    title: 'Achar Líderes no Scanner',
    desc: 'Filtra por VCP, Pocket Pivot, TTM Squeeze ou Episodic Pivot e usa as setas ↑↓ do teclado para ver gráficos num segundo.',
    cta: 'Explorar Scanner',
    accent: 'from-cyan-500/20 to-blue-500/10 border-cyan-500/35 text-cyan-300',
  },
  {
    num: '03',
    tab: 'xray',
    title: 'Confirmar no Raio-X',
    desc: 'Vê o gráfico Diário/Semanal com Anchored VWAP, Linha RS, 8 regras de Minervini, Earnings, Notícias e Briefing IA.',
    cta: 'Abrir Raio-X',
    accent: 'from-purple-500/20 to-cyan-500/10 border-purple-500/35 text-purple-300',
  },
  {
    num: '04',
    tab: 'risk',
    title: 'Calcular Risco ≤ 6% & Simular',
    desc: 'Calcula quantas unidades comprar (EUR→USD ao vivo), ativa Auto 2R + Breakeven e mede o teu SQN no Diário.',
    cta: 'Abrir Risco & Diário',
    accent: 'from-amber-500/20 to-emerald-500/10 border-amber-500/35 text-amber-300',
  },
]

export function OnboardingGuide({ visible, onDismiss, onSelectTab }) {
  if (!visible) return null

  return (
    <div className="mb-6 rounded-2xl border border-cyan-500/35 bg-gradient-to-br from-[#0e192e] via-[#0b1324] to-[#08101e] p-5 shadow-xl">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300 shrink-0">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-display text-base sm:text-lg font-bold text-white">
              Novo por aqui? Segue estes 4 passos simples
            </h2>
            <p className="text-xs text-slate-400">
              A ordem exata usada por traders profissionais para analisar o mercado em 5 minutos sem confusão.
            </p>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-terminal-card border border-terminal-border text-slate-400 hover:text-white transition"
        >
          <X className="w-3.5 h-3.5" />
          Ocultar guia
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {STEPS.map((st) => (
          <button
            key={st.num}
            onClick={() => onSelectTab(st.tab)}
            className={`group text-left rounded-xl p-3.5 border bg-gradient-to-br ${st.accent} hover:brightness-110 transition flex flex-col justify-between gap-2.5`}
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold opacity-90">PASSO {st.num}</span>
                <ArrowRight className="w-3.5 h-3.5 opacity-60 group-hover:translate-x-0.5 transition" />
              </div>
              <div className="font-display text-sm font-bold text-white">{st.title}</div>
              <p className="text-[11px] text-slate-300/90 leading-relaxed">{st.desc}</p>
            </div>
            <span className="text-[11px] font-semibold underline decoration-white/30 underline-offset-4">
              {st.cta}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
