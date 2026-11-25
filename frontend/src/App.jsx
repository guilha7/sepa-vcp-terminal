import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api, getStoredUserName } from './services/api'
import { loadUserPrefs, saveUserPrefs, toggleFavoriteTicker } from './services/userPrefs'
import { Layout } from './components/Layout'
import { LoginGate } from './components/LoginGate'
import { WelcomeNameModal } from './components/WelcomeNameModal'
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

  const [userName, setUserName] = useState(() => getStoredUserName())
  const [switchingUser, setSwitchingUser] = useState(false)

  const serverDefaults = useMemo(
    () => ({
      capitalEur: health?.extra?.default_capital_eur ?? 100,
      stopLossPct: health?.extra?.default_stop_loss_pct ?? 6.0,
    }),
    [health?.extra?.default_capital_eur, health?.extra?.default_stop_loss_pct],
  )

  const [userPrefs, setUserPrefs] = useState(() => loadUserPrefs(getStoredUserName(), { capitalEur: 100, stopLossPct: 6.0 }))

  useEffect(() => {
    setUserPrefs(loadUserPrefs(userName, serverDefaults))
  }, [userName, serverDefaults])

  const handleUpdateUserPrefs = useCallback(
    (partial) => {
      const updated = saveUserPrefs(userName, partial, serverDefaults)
      setUserPrefs(updated)
      return updated
    },
    [userName, serverDefaults],
  )

  const handleToggleFavorite = useCallback(
    (ticker) => {
      const updated = toggleFavoriteTicker(userName, ticker, serverDefaults)
      setUserPrefs(updated)
      return updated
    },
    [userName, serverDefaults],
  )

  const [authChecked, setAuthChecked] = useState(false)
  const [locked, setLocked] = useState(false)
  const [adminRequired, setAdminRequired] = useState(false)
  const [isAdmin, setIsAdmin] = useState(true)

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
      setAdminRequired(Boolean(st.admin_password_required))
      setIsAdmin(Boolean(st.is_admin))
    } catch {
      setLocked(false)
      setAdminRequired(false)
      setIsAdmin(true)
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
          checkAuth()
          fetchHealth()
        }}
      />
    )
  }

  // Friends enter with just their name (no password, no registration) -> isolates Paper Trading & Journal!
  if (!userName || switchingUser) {
    return (
      <WelcomeNameModal
        initialName={userName}
        onConfirm={(chosen) => {
          setUserName(chosen)
          setSwitchingUser(false)
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
        userName={userName}
        onSwitchUser={() => setSwitchingUser(true)}
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
            favorites={userPrefs.favorites}
            onToggleFavorite={handleToggleFavorite}
            isAdmin={isAdmin}
          />
        )}
        {activeTab === 'xray' && (
          <XRayModule
            ticker={selectedTicker}
            onChangeTicker={setSelectedTicker}
            onSimulateTrade={handleSimulateTrade}
            onCreateAlert={handleCreateAlert}
            favorites={userPrefs.favorites}
            onToggleFavorite={handleToggleFavorite}
            isAdmin={isAdmin}
          />
        )}
        {activeTab === 'vision' && <ChartVisionModule onSimulateTrade={handleSimulateTrade} />}
        {activeTab === 'risk' && (
          <RiskPaperModule
            key={userName}
            prefillTrade={prefillTrade}
            onClearPrefill={() => setPrefillTrade(null)}
            onOpenXRay={handleOpenXRay}
            defaultCapitalEur={userPrefs.capitalEur}
            defaultStopLossPct={userPrefs.stopLossPct}
            defaultRiskPct={userPrefs.riskPerTradePct}
          />
        )}
        {activeTab === 'settings' && (
          <SettingsModule
            userName={userName}
            userPrefs={userPrefs}
            onUpdateUserPrefs={handleUpdateUserPrefs}
            onToggleFavorite={handleToggleFavorite}
            onOpenXRay={handleOpenXRay}
            onSettingsSaved={fetchHealth}
            onOpenAlerts={() => setAlertsOpen(true)}
            adminRequired={adminRequired}
            isAdmin={isAdmin}
            onAdminUnlocked={() => {
              checkAuth()
              fetchHealth()
            }}
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
        isAdmin={isAdmin}
      />
    </>
  )
}
