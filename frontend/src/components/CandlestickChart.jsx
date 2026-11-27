import React, { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'

function getLayerPreset(strategy, compact) {
  switch (strategy) {
    case 'qullamaggie':
      return {
        sma50: true,
        sma150: false,
        sma200: false,
        avwap: false,
        rs: false,
        vcp: false,
        pp: false,
        levels: true,
      }
    case 'institutional':
      return {
        sma50: true,
        sma150: false,
        sma200: !compact,
        avwap: false,
        rs: true,
        vcp: false,
        pp: true,
        levels: false,
      }
    case 'weinstein_squeeze':
      return {
        sma50: true,
        sma150: true,
        sma200: false,
        avwap: true,
        rs: true,
        vcp: false,
        pp: false,
        levels: false,
      }
    case 'minervini':
    default:
      return {
        sma50: true,
        sma150: !compact,
        sma200: true,
        avwap: false,
        rs: true,
        vcp: true,
        pp: false,
        levels: true,
      }
  }
}

export function CandlestickChart({ chartData, ticker, compact = false, strategy = 'minervini' }) {
  const containerRef = useRef(null)
  const initialPreset = getLayerPreset(strategy, compact)
  const [timeframe, setTimeframe] = useState('daily') // daily | weekly
  const [range, setRange] = useState(compact ? '6M' : '1Y')
  const [showSma50, setShowSma50] = useState(initialPreset.sma50)
  const [showSma150, setShowSma150] = useState(initialPreset.sma150)
  const [showSma200, setShowSma200] = useState(initialPreset.sma200)
  const [showAvwap, setShowAvwap] = useState(initialPreset.avwap)
  const [showRsLine, setShowRsLine] = useState(initialPreset.rs)
  const [showVcpSwings, setShowVcpSwings] = useState(initialPreset.vcp)
  const [showPocketPivots, setShowPocketPivots] = useState(initialPreset.pp)
  const [showLevels, setShowLevels] = useState(initialPreset.levels)

  // Automatically sync visible chart layers when user switches strategy (zero visual noise from other strategies!)
  useEffect(() => {
    const p = getLayerPreset(strategy, compact)
    setShowSma50(p.sma50)
    setShowSma150(p.sma150)
    setShowSma200(p.sma200)
    setShowAvwap(p.avwap)
    setShowRsLine(p.rs)
    setShowVcpSwings(p.vcp)
    setShowPocketPivots(p.pp)
    setShowLevels(p.levels)
  }, [strategy, compact])

  const activeSeries =
    timeframe === 'weekly' && chartData?.weekly?.candles?.length
      ? chartData.weekly
      : chartData

  useEffect(() => {
    const el = containerRef.current
    if (!el || !activeSeries?.candles?.length) return

    const chart = createChart(el, {
      width: el.clientWidth,
      height: compact ? 300 : 460,
      layout: {
        background: { color: '#090f1d' },
        textColor: '#94a3b8',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#131d33' },
        horzLines: { color: '#131d33' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#334155', labelBackgroundColor: '#1e293b' },
        horzLine: { color: '#334155', labelBackgroundColor: '#1e293b' },
      },
      leftPriceScale: {
        visible: showRsLine && Boolean(activeSeries.rs_line?.length),
        borderColor: '#1d2d4a',
        scaleMargins: { top: 0.14, bottom: 0.28 },
      },
      rightPriceScale: {
        borderColor: '#1d2d4a',
        scaleMargins: { top: 0.08, bottom: 0.24 },
      },
      timeScale: {
        borderColor: '#1d2d4a',
        timeVisible: false,
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    })
    candleSeries.setData(activeSeries.candles)

    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    volSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })
    volSeries.setData(activeSeries.volumes || [])

    const maLabels = timeframe === 'weekly' ? ['SMA 10w', 'SMA 30w', 'SMA 40w'] : ['SMA 50', 'SMA 150', 'SMA 200']

    if (showSma50 && activeSeries.sma50?.length) {
      const s50 = chart.addLineSeries({
        color: '#06b6d4',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: maLabels[0],
      })
      s50.setData(activeSeries.sma50)
    }

    if (showSma150 && activeSeries.sma150?.length) {
      const s150 = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: true,
        title: maLabels[1],
      })
      s150.setData(activeSeries.sma150)
    }

    if (showSma200 && activeSeries.sma200?.length) {
      const s200 = chart.addLineSeries({
        color: '#a855f7',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: maLabels[2],
      })
      s200.setData(activeSeries.sma200)
    }

    // Brian Shannon Anchored VWAP (Swing Low + YTD) on Daily chart
    if (showAvwap && timeframe === 'daily') {
      if (chartData?.avwap_swing_low?.length) {
        const avSwing = chart.addLineSeries({
          color: '#fbbf24',
          lineWidth: 1.8,
          lineStyle: LineStyle.Dashed,
          priceLineVisible: false,
          lastValueVisible: true,
          title: 'AVWAP Low',
        })
        avSwing.setData(chartData.avwap_swing_low)
      }
      if (chartData?.avwap_ytd?.length) {
        const avYtd = chart.addLineSeries({
          color: '#f472b6',
          lineWidth: 1.5,
          lineStyle: LineStyle.Dotted,
          priceLineVisible: false,
          lastValueVisible: true,
          title: 'AVWAP YTD',
        })
        avYtd.setData(chartData.avwap_ytd)
      }
    }

    // Relative Strength (RS) Line on left axis
    if (showRsLine && activeSeries.rs_line?.length) {
      const rsSeries = chart.addLineSeries({
        priceScaleId: 'left',
        color: '#60a5fa',
        lineWidth: 1.75,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'Linha RS',
      })
      rsSeries.setData(activeSeries.rs_line)
    }

    // Visual VCP Contractions + Pocket Pivot markers on Daily chart
    if (timeframe === 'daily') {
      const validDates = new Set(activeSeries.candles.map((c) => c.time))
      const markers = []

      const vcpLegs = chartData?.vcp_legs || []
      if (showVcpSwings && vcpLegs.length > 0) {
        const legColors = ['#38bdf8', '#22d3ee', '#34d399', '#a3e635']
        vcpLegs.forEach((lg, idx) => {
          if (!validDates.has(lg.start_date) || !validDates.has(lg.end_date)) return
          if (lg.start_date < lg.end_date) {
            const swingLine = chart.addLineSeries({
              color: legColors[idx % legColors.length],
              lineWidth: 2,
              lineStyle: LineStyle.LargeDashed,
              priceLineVisible: false,
              lastValueVisible: false,
              crosshairMarkerVisible: false,
            })
            swingLine.setData([
              { time: lg.start_date, value: lg.high_price },
              { time: lg.end_date, value: lg.low_price },
            ])
          }
          markers.push({
            time: lg.end_date,
            position: 'belowBar',
            color: legColors[idx % legColors.length],
            shape: 'arrowUp',
            text: `T${lg.leg} -${lg.depth_pct.toFixed(0)}%`,
          })
        })
      }

      // Pocket Pivot markers (shown ONLY for Institutional strategy or if toggled)
      const ppDates = chartData?.pocket_pivot_dates || []
      if (showPocketPivots && ppDates.length > 0) {
        ppDates.forEach((dt) => {
          if (validDates.has(dt)) {
            markers.push({
              time: dt,
              position: 'aboveBar',
              color: '#a855f7',
              shape: 'circle',
              text: 'PP',
            })
          }
        })
      }

      if (markers.length > 0) {
        markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
        candleSeries.setMarkers(markers)
      }
    }

    if (showLevels) {
      const stopLinePx = chartData.technical_stop || chartData.suggested_stop_6pct
      if (stopLinePx) {
        candleSeries.createPriceLine({
          price: stopLinePx,
          color: '#ef4444',
          lineWidth: 1.5,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: chartData.technical_stop ? 'Stop Técnico' : 'Stop -6%',
        })
      }
      if (chartData.pivot_price) {
        candleSeries.createPriceLine({
          price: chartData.pivot_price,
          color: '#10b981',
          lineWidth: 1.5,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: 'Pivô VCP',
        })
      }
    }

    const total = activeSeries.candles.length
    if (timeframe === 'weekly') {
      chart.timeScale().fitContent()
    } else {
      const barsMap = { '3M': 65, '6M': 130, '1Y': 252, '2Y': total }
      const count = Math.min(barsMap[range] || 252, total)
      if (total > 5) {
        const from = activeSeries.candles[Math.max(0, total - count)].time
        const to = activeSeries.candles[total - 1].time
        chart.timeScale().setVisibleRange({ from, to })
      } else {
        chart.timeScale().fitContent()
      }
    }

    const ro = new ResizeObserver((entries) => {
      if (entries[0]) {
        chart.applyOptions({ width: entries[0].contentRect.width })
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [chartData, activeSeries, timeframe, range, showSma50, showSma150, showSma200, showAvwap, showRsLine, showVcpSwings, showPocketPivots, showLevels, compact])

  const hasWeekly = Boolean(chartData?.weekly?.candles?.length)
  const hasVcpLegs = (chartData?.vcp_legs || []).length > 0
  const hasPpDates = (chartData?.pocket_pivot_dates || []).length > 0
  const hasAvwap = Boolean(chartData?.avwap_swing_low?.length)

  return (
    <div className="terminal-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 border-b border-terminal-border bg-terminal-card/70">
        <div className="flex flex-wrap items-center gap-2.5 text-[11px]">
          <span className="font-mono font-bold text-white">{ticker}</span>

          {hasWeekly && (
            <div className="inline-flex rounded-lg bg-[#060a13] border border-terminal-border p-0.5 font-mono">
              <button
                onClick={() => setTimeframe('daily')}
                className={`px-2 py-0.5 rounded-md transition ${
                  timeframe === 'daily' ? 'bg-cyan-500/25 text-cyan-200 font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Diário
              </button>
              <button
                onClick={() => setTimeframe('weekly')}
                className={`px-2 py-0.5 rounded-md transition ${
                  timeframe === 'weekly' ? 'bg-cyan-500/25 text-cyan-200 font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Semanal
              </button>
            </div>
          )}

          {strategy === 'minervini' && chartData?.rs_new_high_before_price && (
            <span className="px-2 py-0.5 rounded-md bg-blue-500/20 border border-blue-400/50 text-blue-300 font-mono font-bold text-[10px]">
              ● RS NEW HIGH
            </span>
          )}
          {strategy === 'weinstein_squeeze' && chartData?.ttm_squeeze_state && chartData.ttm_squeeze_state !== 'NEUTRO' && (
            <span
              className={`px-2 py-0.5 rounded-md font-mono font-bold text-[10px] border ${
                chartData.ttm_squeeze_state === 'SQUEEZE_FIRE'
                  ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-300'
                  : 'bg-amber-500/20 border-amber-400/50 text-amber-300'
              }`}
            >
              ⚡ {chartData.ttm_squeeze_state === 'SQUEEZE_FIRE' ? 'SQUEEZE FIRE' : 'SQUEEZE ON'}
            </span>
          )}

          <label className="inline-flex items-center gap-1 cursor-pointer text-cyan-400">
            <input type="checkbox" checked={showSma50} onChange={(e) => setShowSma50(e.target.checked)} className="accent-cyan-500" />
            {timeframe === 'weekly' ? '10w' : '50'}
          </label>
          {(strategy === 'minervini' || strategy === 'weinstein_squeeze') && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-amber-400">
              <input type="checkbox" checked={showSma150} onChange={(e) => setShowSma150(e.target.checked)} className="accent-amber-500" />
              {timeframe === 'weekly' ? '30w' : '150'}
            </label>
          )}
          {(strategy === 'minervini' || strategy === 'institutional') && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-purple-400">
              <input type="checkbox" checked={showSma200} onChange={(e) => setShowSma200(e.target.checked)} className="accent-purple-500" />
              {timeframe === 'weekly' ? '40w' : '200'}
            </label>
          )}
          {strategy === 'weinstein_squeeze' && hasAvwap && timeframe === 'daily' && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-yellow-300" title="Anchored VWAP">
              <input type="checkbox" checked={showAvwap} onChange={(e) => setShowAvwap(e.target.checked)} className="accent-yellow-400" />
              AVWAP
            </label>
          )}
          {strategy !== 'qullamaggie' && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-blue-400">
              <input type="checkbox" checked={showRsLine} onChange={(e) => setShowRsLine(e.target.checked)} className="accent-blue-500" />
              RS
            </label>
          )}
          {strategy === 'minervini' && hasVcpLegs && timeframe === 'daily' && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-emerald-400">
              <input type="checkbox" checked={showVcpSwings} onChange={(e) => setShowVcpSwings(e.target.checked)} className="accent-emerald-500" />
              VCP
            </label>
          )}
          {strategy === 'institutional' && hasPpDates && timeframe === 'daily' && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-purple-300">
              <input type="checkbox" checked={showPocketPivots} onChange={(e) => setShowPocketPivots(e.target.checked)} className="accent-purple-400" />
              Pocket Pivots
            </label>
          )}
          {(strategy === 'minervini' || strategy === 'qullamaggie') && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-rose-400">
              <input type="checkbox" checked={showLevels} onChange={(e) => setShowLevels(e.target.checked)} className="accent-rose-500" />
              Pivô/Stop
            </label>
          )}
        </div>

        {timeframe === 'daily' && (
          <div className="flex items-center gap-1">
            {['3M', '6M', '1Y', '2Y'].map((tf) => (
              <button
                key={tf}
                onClick={() => setRange(tf)}
                className={`px-2 py-0.5 text-[11px] font-mono rounded-md transition ${
                  range === tf
                    ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-400/40'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-terminal-hover'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        )}
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}
