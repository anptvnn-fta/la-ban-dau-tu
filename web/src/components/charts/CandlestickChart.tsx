import { useEffect, useRef } from 'react'
import {
  createChart, CandlestickSeries, HistogramSeries, LineSeries, ColorType,
  type UTCTimestamp, type CandlestickData, type HistogramData, type LineData,
} from 'lightweight-charts'
import type { OhlcBar } from '@/api/stocks'

/** Biểu đồ nến + khối lượng + chỉ báo (MA overlay, pane RSI) — TradingView Lightweight Charts. */
export function CandlestickChart({
  bars,
  height = 340,
  showIndicators = true,
}: {
  bars: OhlcBar[]
  height?: number
  showIndicators?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || !bars.length) return

    const cs = getComputedStyle(document.documentElement)
    const v = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback
    const bull = v('--candle-bull', '#26a69a')
    const bear = v('--candle-bear', '#ef5350')
    const text = v('--muted-foreground', '#94a3b8')
    const grid = v('--border', '#334155')

    const chart = createChart(el, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: text,
        fontFamily: 'IBM Plex Mono, monospace',
        fontSize: 11,
      },
      grid: { vertLines: { color: `${grid}33` }, horzLines: { color: `${grid}33` } },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid, timeVisible: false },
      crosshair: { mode: 0 },
    })

    const toTime = (d: string): UTCTimestamp => (Date.parse(`${d}T00:00:00Z`) / 1000) as UTCTimestamp

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: bull, downColor: bear, borderUpColor: bull, borderDownColor: bear,
      wickUpColor: bull, wickDownColor: bear,
    })
    candle.setData(
      bars.map<CandlestickData>((b) => ({ time: toTime(b.date), open: b.open, high: b.high, low: b.low, close: b.close })),
    )

    const vol = chart.addSeries(HistogramSeries, { priceScaleId: '', priceFormat: { type: 'volume' } })
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    vol.setData(
      bars.map<HistogramData>((b) => ({
        time: toTime(b.date),
        value: b.volume ?? 0,
        color: `${b.close >= b.open ? bull : bear}55`,
      })),
    )

    if (showIndicators) {
      // Đường trung bình động (overlay trên thang giá)
      const addMA = (key: 'ma5' | 'ma10' | 'ma20', color: string) => {
        const pts = bars.filter((b) => b[key] != null).map<LineData>((b) => ({ time: toTime(b.date), value: b[key] as number }))
        if (!pts.length) return
        const s = chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
        s.setData(pts)
      }
      addMA('ma5', '#f59e0b')
      addMA('ma10', '#3b82f6')
      addMA('ma20', '#a855f7')

      // RSI ở pane riêng (paneIndex 1) — bao trong try để an toàn nếu API khác
      const rsiPts = bars.filter((b) => b.rsi != null).map<LineData>((b) => ({ time: toTime(b.date), value: b.rsi as number }))
      if (rsiPts.length) {
        try {
          const rsi = chart.addSeries(LineSeries, { color: '#22d3ee', lineWidth: 1, priceFormat: { type: 'price', precision: 1, minMove: 0.1 } }, 1)
          rsi.setData(rsiPts)
          const panes = chart.panes()
          if (panes[1]) panes[1].setHeight(90)
        } catch {
          /* phiên bản không hỗ trợ pane → bỏ qua RSI */
        }
      }
    }

    chart.timeScale().fitContent()
    const resize = () => chart.applyOptions({ width: el.clientWidth })
    resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.remove()
    }
  }, [bars, height, showIndicators])

  return <div ref={ref} style={{ height: showIndicators ? height + 90 : height, width: '100%' }} />
}
