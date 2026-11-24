import React, { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'

export function CandlestickChart({ chartData, ticker, compact = false }) {
  const containerRef = useRef(null)
  const [timeframe, setTimeframe] = useState('daily') // daily | weekly
  const [range, setRange] = useState(compact ? '6M' : '1Y')
  const [showSma50, setShowSma50] = useState(true)
  const [showSma150, setShowSma150] = useState(!compact)
  const [showSma200, setShowSma200] = useState(true)
  const [showRsLine, setShowRsLine] = useState(true)
  const [showVcpSwings, setShowVcpSwings] = useState(true)
  const [showLevels, setShowLevels] = useState(true)

  const activeSeries =
    timeframe === 'weekly' && chartData?.weekly?.candles?.length
      ? chartData.weekly
      : chartData

  useEffect(() => {
    const el = containerRef.current
    if (!el || !activeSeries?.candles?.length) return

    const chart = createChart(el, {
      width: el.clientWidth,
      height: compact ? 300 : 450,
      layout: {
        background: { color: '#0a101d' },
        textColor: '#94a3b8',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#141e33' },
        horzLines: { color: '#141e33' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#334155', labelBackgroundColor: '#1e293b' },
        horzLine: { color: '#334155', labelBackgroundColor: '#1e293b' },
      },
      leftPriceScale: {
        visible: showRsLine && Boolean(activeSeries.rs_line?.length),
        borderColor: '#1e2c48',
        scaleMargins: { top: 0.14, bottom: 0.28 },
      },
      rightPriceScale: {
        borderColor: '#1e2c48',
        scaleMargins: { top: 0.08, bottom: 0.24 },
      },
      timeScale: {
        borderColor: '#1e2c48',
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

    // Relative Strength (RS) Line on left axis (classic IBD/Minervini footprint)
    if (showRsLine && activeSeries.rs_line?.length) {
      const rsSeries = chart.addLineSeries({
        priceScaleId: 'left',
        color: '#60a5fa',
        lineWidth: 1.75,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'Linha RS',
      })
      rsSeries.setData(activeSeries.rs_line)
    }

    // Visual VCP Contractions (T1 -> T2 -> T3) plotted directly on Daily chart!
    const vcpLegs = chartData?.vcp_legs || []
    if (showVcpSwings && timeframe === 'daily' && vcpLegs.length > 0) {
      const validDates = new Set(activeSeries.candles.map((c) => c.time))
      const markers = []
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

      if (markers.length > 0) {
        markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
        candleSeries.setMarkers(markers)
      }
    }

    if (showLevels) {
      if (chartData.suggested_stop_6pct) {
        candleSeries.createPriceLine({
          price: chartData.suggested_stop_6pct,
          color: '#ef4444',
          lineWidth: 1.5,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: 'Stop -6%',
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
  }, [chartData, activeSeries, timeframe, range, showSma50, showSma150, showSma200, showRsLine, showVcpSwings, showLevels, compact])

  const hasWeekly = Boolean(chartData?.weekly?.candles?.length)
  const hasVcpLegs = (chartData?.vcp_legs || []).length > 0

  return (
    <div className="terminal-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 border-b border-terminal-border bg-terminal-card/60">
        <div className="flex flex-wrap items-center gap-2.5 text-[11px]">
          <span className="font-mono font-bold text-slate-200">{ticker}</span>

          {/* Daily / Weekly Switcher */}
          {hasWeekly && (
            <div className="inline-flex rounded-md bg-[#070b14] border border-terminal-border p-0.5 font-mono">
              <button
                onClick={() => setTimeframe('daily')}
                className={`px-2 py-0.5 rounded transition ${
                  timeframe === 'daily' ? 'bg-cyan-500/25 text-cyan-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Diário
              </button>
              <button
                onClick={() => setTimeframe('weekly')}
                className={`px-2 py-0.5 rounded transition ${
                  timeframe === 'weekly' ? 'bg-cyan-500/25 text-cyan-300 font-semibold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Semanal
              </button>
            </div>
          )}

          {chartData?.rs_new_high_before_price && (
            <span className="px-2 py-0.5 rounded bg-blue-500/20 border border-blue-400/50 text-blue-300 font-mono font-bold text-[10px]">
              ● RS NEW HIGH
            </span>
          )}

          <label className="inline-flex items-center gap-1 cursor-pointer text-cyan-400">
            <input type="checkbox" checked={showSma50} onChange={(e) => setShowSma50(e.target.checked)} className="accent-cyan-500" />
            {timeframe === 'weekly' ? '10w' : '50'}
          </label>
          <label className="inline-flex items-center gap-1 cursor-pointer text-amber-400">
            <input type="checkbox" checked={showSma150} onChange={(e) => setShowSma150(e.target.checked)} className="accent-amber-500" />
            {timeframe === 'weekly' ? '30w' : '150'}
          </label>
          <label className="inline-flex items-center gap-1 cursor-pointer text-purple-400">
            <input type="checkbox" checked={showSma200} onChange={(e) => setShowSma200(e.target.checked)} className="accent-purple-500" />
            {timeframe === 'weekly' ? '40w' : '200'}
          </label>
          <label className="inline-flex items-center gap-1 cursor-pointer text-blue-400">
            <input type="checkbox" checked={showRsLine} onChange={(e) => setShowRsLine(e.target.checked)} className="accent-blue-500" />
            RS
          </label>
          {hasVcpLegs && timeframe === 'daily' && (
            <label className="inline-flex items-center gap-1 cursor-pointer text-emerald-400">
              <input type="checkbox" checked={showVcpSwings} onChange={(e) => setShowVcpSwings(e.target.checked)} className="accent-emerald-500" />
              VCP
            </label>
          )}
          <label className="inline-flex items-center gap-1 cursor-pointer text-rose-400">
            <input type="checkbox" checked={showLevels} onChange={(e) => setShowLevels(e.target.checked)} className="accent-rose-500" />
            Pivô/-6%
          </label>
        </div>

        {timeframe === 'daily' && (
          <div className="flex items-center gap-1">
            {['3M', '6M', '1Y', '2Y'].map((tf) => (
              <button
                key={tf}
                onClick={() => setRange(tf)}
                className={`px-2 py-0.5 text-[11px] font-mono rounded transition ${
                  range === tf
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
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
