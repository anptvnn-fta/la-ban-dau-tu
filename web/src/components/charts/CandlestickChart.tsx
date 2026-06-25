import { useEffect, useRef } from 'react'
import {
  createChart, CandlestickSeries, HistogramSeries, ColorType,
  type UTCTimestamp, type CandlestickData, type HistogramData,
} from 'lightweight-charts'
import type { OhlcBar } from '@/api/stocks'

/** Biểu đồ nến + khối lượng (TradingView Lightweight Charts). */
export function CandlestickChart({ bars, height = 340 }: { bars: OhlcBar[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || !bars.length) return

    const css = getComputedStyle(document.documentElement)
    const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback
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

    chart.timeScale().fitContent()
    const resize = () => chart.applyOptions({ width: el.clientWidth })
    resize()
    window.addEventListener('resize', resize)
    return () => {
      window.removeEventListener('resize', resize)
      chart.remove()
    }
  }, [bars, height])

  return <div ref={ref} style={{ height, width: '100%' }} />
}
