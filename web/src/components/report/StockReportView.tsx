import { useState } from 'react'
import {
  FileText, Gauge, Layers, TrendingUp, Target, ChevronDown,
  ArrowDownToLine, ArrowUpFromLine, ShieldAlert, Flag,
} from 'lucide-react'
import type { AnalysisReport, DecisionAction } from '@/types/analysis'
import { getSentimentLabel } from '@/types/analysis'
import { Card, CardLabel } from '@/components/ui/card'
import { PriceChange } from './PriceChange'
import { PriceChartCard } from './PriceChartCard'
import { ReportMarkdown } from './ReportMarkdown'
import { SentimentGauge } from '@/components/charts/SentimentGauge'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

function actionTone(action?: DecisionAction | null): string {
  if (!action) return 'bg-secondary text-secondary-foreground'
  if (action === 'buy' || action === 'add') return 'bg-up/15 text-up'
  if (action === 'sell' || action === 'reduce' || action === 'avoid') return 'bg-down/15 text-down'
  return 'bg-warning/15 text-warning'
}

function MocCard({
  icon, label, value, tone,
}: { icon: React.ReactNode; label: string; value?: string; tone?: 'up' | 'down' }) {
  return (
    <div className="rounded-xl border border-border bg-background/40 p-3">
      <p className={cn('flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground')}>
        {icon}
        {label}
      </p>
      <p className={cn('mt-1 font-mono text-base font-semibold tabular-nums',
        tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-foreground')}>
        {value || '--'}
      </p>
    </div>
  )
}

export function StockReportView({ report }: { report: AnalysisReport }) {
  const { meta, summary, strategy, details } = report
  const [showFull, setShowFull] = useState(false)
  const boards = Array.isArray(details?.belongBoards) ? details!.belongBoards : []
  const asStr = (v: unknown) => (typeof v === 'string' ? v : '')
  const fullMarkdown = (asStr(details?.rawResult) || asStr(details?.newsContent)).trim()

  return (
    <div className="space-y-4">
      {/* Hero */}
      <Card className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-xl font-bold text-foreground">{meta.stockName || meta.stockCode}</h2>
              <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-xs text-secondary-foreground">{meta.stockCode}</span>
            </div>
            <div className="mt-2">
              <PriceChange price={meta.currentPrice} changePct={meta.changePct} size="lg" />
            </div>
          </div>
          <div className="text-right text-xs text-muted-foreground">
            {meta.modelUsed ? <p>{meta.modelUsed}</p> : null}
            {meta.createdAt ? <p>{new Date(meta.createdAt).toLocaleString('vi-VN')}</p> : null}
          </div>
        </div>
      </Card>

      {/* Biểu đồ giá (nến + khối lượng) */}
      {meta.stockCode ? <PriceChartCard code={meta.stockCode} /> : null}

      {/* 4 thẻ nhận định */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card className="p-4">
          <CardLabel icon={<FileText className="h-3.5 w-3.5" />}>{VI.home.keyInsights}</CardLabel>
          <p className="mt-2 line-clamp-5 text-sm leading-6 text-foreground">{summary.analysisSummary || VI.common.noData}</p>
        </Card>
        <Card className="p-4">
          <CardLabel icon={<Layers className="h-3.5 w-3.5" />}>{VI.home.actionAdvice}</CardLabel>
          {summary.actionLabel ? (
            <span className={cn('mt-2 inline-block rounded-md px-2 py-0.5 text-xs font-semibold', actionTone(summary.action))}>
              {summary.actionLabel}
            </span>
          ) : null}
          <p className="mt-2 line-clamp-4 text-sm leading-6 text-foreground">{summary.operationAdvice || VI.common.noData}</p>
        </Card>
        <Card className="p-4">
          <CardLabel icon={<TrendingUp className="h-3.5 w-3.5" />}>{VI.home.trendPrediction}</CardLabel>
          <p className="mt-2 line-clamp-5 text-sm leading-6 text-foreground">{summary.trendPrediction || VI.common.noData}</p>
        </Card>
        <Card className="flex flex-col items-center justify-center p-4">
          <CardLabel icon={<Gauge className="h-3.5 w-3.5" />}>{VI.home.marketSentiment}</CardLabel>
          <div className="mt-1">
            <SentimentGauge
              score={summary.sentimentScore ?? 50}
              label={getSentimentLabel(summary.sentimentScore ?? 50, 'vi')}
              size={150}
            />
          </div>
        </Card>
      </div>

      {/* Mốc chiến lược */}
      {strategy ? (
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Target className="h-4 w-4" />
            </span>
            <h3 className="text-base font-semibold text-foreground">{VI.home.strategyPoints}</h3>
          </div>
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
            <MocCard icon={<ArrowDownToLine className="h-3.5 w-3.5" />} label={VI.home.idealBuy} value={strategy.idealBuy} tone="up" />
            <MocCard icon={<ArrowDownToLine className="h-3.5 w-3.5" />} label={VI.home.secondaryBuy} value={strategy.secondaryBuy} tone="up" />
            <MocCard icon={<ShieldAlert className="h-3.5 w-3.5" />} label={VI.home.stopLoss} value={strategy.stopLoss} tone="down" />
            <MocCard icon={<Flag className="h-3.5 w-3.5" />} label={VI.home.takeProfit} value={strategy.takeProfit} />
          </div>
        </Card>
      ) : null}

      {/* Nhóm ngành */}
      {boards.length ? (
        <Card className="p-4">
          <CardLabel icon={<Layers className="h-3.5 w-3.5" />}>{VI.home.relatedBoards}</CardLabel>
          <div className="mt-2 flex flex-wrap gap-2">
            {boards.map((b, i) => (
              <span key={`${b.name}-${i}`} className="rounded-full bg-secondary px-2.5 py-1 text-xs text-secondary-foreground">
                {b.name}
              </span>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Báo cáo đầy đủ (gập) */}
      {fullMarkdown ? (
        <Card className="p-4">
          <button
            type="button"
            onClick={() => setShowFull((v) => !v)}
            className="flex w-full items-center justify-between text-left focus-visible:outline-none"
          >
            <span className="flex items-center gap-2 text-base font-semibold text-foreground">
              <FileText className="h-4 w-4 text-primary" />
              {VI.home.fullReport}
            </span>
            <ChevronDown className={cn('h-5 w-5 text-muted-foreground transition-transform', showFull && 'rotate-180')} />
          </button>
          {showFull ? <div className="mt-3 border-t border-border pt-3"><ReportMarkdown content={fullMarkdown} /></div> : null}
        </Card>
      ) : null}
    </div>
  )
}
