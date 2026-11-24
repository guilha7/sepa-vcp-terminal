import React, { useCallback, useEffect, useState } from 'react'
import { api } from './services/api'
import { Layout } from './components/Layout'
import { LoginGate } from './components/LoginGate'
import { OnboardingGuide } from './components/OnboardingGuide'
import { CommandPalette } from './components/CommandPalette'
import { AlertsDrawer } from './components/AlertsDrawer'
import { MacroRotationModule } from './modules/MacroRotationModule'
import { ScannerModule } from './modules/ScannerModule'
import { XRayModule } from './modules/XRayModule'
import { ChartVisionModule } from './modules/ChartVisionModule'
import { RiskPaperModule } from './modules/RiskPaperModule'
import { SettingsModule } from './modules/SettingsModule'

export default function App() {
  const [activeTab, setActiveTab] = useState('macro')
  const [selectedTicker, setSelectedTicker] = useState('NVDA')
  const [prefillTrade, setPrefillTrade] = useState(null)
  const [prefillAlert, setPrefillAlert] = useState(null)
  const [health, setHealth] = useState(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [authChecked, setAuthChecked] = useState(false)
  const [locked, setLocked] = useState(false)

  const [guideOpen, setGuideOpen] = useState(() => {
    try {
      return localStorage.getItem('sepa_guide_dismissed') !== '1'
    } catch {
      return true
    }
  })

  const checkAuth = useCallback(async () => {
    try {
      const st = await api.getAuthStatus()
      setLocked(Boolean(st.password_required && !st.authenticated))
    } catch {
      setLocked(false)
    } finally {
      setAuthChecked(true)
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const handleDismissGuide = () => {
    setGuideOpen(false)
    try {
      localStorage.setItem('sepa_guide_dismissed', '1')
    } catch {
      // ignore
    }
  }

  const handleToggleGuide = () => {
    setGuideOpen((prev) => {
      const next = !prev
      try {
        localStorage.setItem('sepa_guide_dismissed', next ? '0' : '1')
      } catch {
        // ignore
      }
      return next
    })
  }

  const fetchHealth = useCallback(async () => {
    try {
      const res = await api.getHealth()
      setHealth(res)
    } catch {
      setHealth(null)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 25000)
    return () => clearInterval(id)
  }, [fetchHealth])

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const handleOpenXRay = (ticker) => {
    setSelectedTicker(ticker)
    setActiveTab('xray')
  }

  const handleSimulateTrade = (tradePayload) => {
    setPrefillTrade(tradePayload)
    setActiveTab('risk')
  }

  const handleCreateAlert = (alertPayload) => {
    setPrefillAlert(alertPayload)
    setAlertsOpen(true)
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-terminal-bg text-xs text-slate-400">
        A iniciar SEPA/VCP Desk...
      </div>
    )
  }

  if (locked) {
    return (
      <LoginGate
        onUnlocked={() => {
          setLocked(false)
          fetchHealth()
        }}
      />
    )
  }

  return (
    <>
      <Layout
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onQuickSearch={handleOpenXRay}
        onOpenPalette={() => setPaletteOpen(true)}
        onOpenAlerts={() => setAlertsOpen(true)}
        onToggleGuide={handleToggleGuide}
        guideOpen={guideOpen}
        health={health}
      >
        <OnboardingGuide
          visible={guideOpen}
          onDismiss={handleDismissGuide}
          onSelectTab={(tab) => setActiveTab(tab)}
        />

        {activeTab === 'macro' && <MacroRotationModule onOpenXRay={handleOpenXRay} />}
        {activeTab === 'scanner' && (
          <ScannerModule
            onOpenXRay={handleOpenXRay}
            onSimulateTrade={handleSimulateTrade}
            onCreateAlert={handleCreateAlert}
          />
        )}
        {activeTab === 'xray' && (
          <XRayModule
            ticker={selectedTicker}
            onChangeTicker={setSelectedTicker}
            onSimulateTrade={handleSimulateTrade}
            onCreateAlert={handleCreateAlert}
          />
        )}
        {activeTab === 'vision' && <ChartVisionModule onSimulateTrade={handleSimulateTrade} />}
        {activeTab === 'risk' && (
          <RiskPaperModule
            prefillTrade={prefillTrade}
            onClearPrefill={() => setPrefillTrade(null)}
            onOpenXRay={handleOpenXRay}
            defaultCapitalEur={health?.extra?.default_capital_eur ?? 100}
            defaultStopLossPct={health?.extra?.default_stop_loss_pct ?? 6.0}
          />
        )}
        {activeTab === 'settings' && (
          <SettingsModule
            onSettingsSaved={fetchHealth}
            onOpenAlerts={() => setAlertsOpen(true)}
          />
        )}
      </Layout>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectTab={setActiveTab}
        onOpenXRay={handleOpenXRay}
        onOpenAlerts={() => setAlertsOpen(true)}
      />

      <AlertsDrawer
        open={alertsOpen}
        onClose={() => setAlertsOpen(false)}
        prefillAlert={prefillAlert}
        onClearPrefill={() => setPrefillAlert(null)}
        onAlertsChanged={fetchHealth}
      />
    </>
  )
}
