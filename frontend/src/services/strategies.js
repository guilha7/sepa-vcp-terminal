export const STRATEGIES = [
  {
    id: 'minervini',
    label: 'Minervini SEPA / VCP',
    shortLabel: 'Minervini VCP',
    tagline: 'Tendência Stage 2 (8 regras), contrações VCP, Pivô, Stop ≤ 6% e Linha RS.',
    color: 'emerald',
  },
  {
    id: 'qullamaggie',
    label: 'Qullamaggie Momentum',
    shortLabel: 'Qullamaggie',
    tagline: 'Episodic Pivots (EP), High Tight Flag (HTF), ADR% diário e Extensão ATR.',
    color: 'cyan',
  },
  {
    id: 'institutional',
    label: "Institucional (O'Neil)",
    shortLabel: "O'Neil / CAN SLIM",
    tagline: 'Pocket Pivots, 3 Weeks Tight, Volume A–E, Code 33 trimestral e Insiders.',
    color: 'purple',
  },
  {
    id: 'weinstein_squeeze',
    label: 'Weinstein & TTM Squeeze',
    shortLabel: 'Weinstein / Squeeze',
    tagline: 'Fases 1–4 (Weinstein), TTM Squeeze, Mansfield RS e Anchored VWAP.',
    color: 'amber',
  },
]

export const VALID_STRATEGY_IDS = new Set(STRATEGIES.map((s) => s.id))

export function getStrategyMeta(id) {
  return STRATEGIES.find((s) => s.id === id) || STRATEGIES[0]
}
