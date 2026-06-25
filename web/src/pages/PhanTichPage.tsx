import { useEffect, useRef, useState } from 'react'
import { Loader2, BarChart3, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { StockSearch, type SelectedStock } from '@/components/StockSearch'
import { StockReportView } from '@/components/report/StockReportView'
import { MarketReviewView } from '@/components/report/MarketReviewView'
import { HistoryList, type HistoryListHandle } from '@/components/history/HistoryList'
import { Card } from '@/components/ui/card'
import { useAnalysisTask } from '@/hooks/useAnalysisTask'
import { historyApi } from '@/api/history'
import type { AnalysisReport, MarketReviewPayload } from '@/types/analysis'
import { VI } from '@/strings/vi'

export default function PhanTichPage() {
  const { state, analyze, marketReview, reset } = useAnalysisTask()
  const [report, setReport] = useState<AnalysisReport | null>(null)
  const [market, setMarket] = useState<MarketReviewPayload | null>(null)
  const [activeId, setActiveId] = useState<number | undefined>(undefined)
  const historyRef = useRef<HistoryListHandle>(null)

  useEffect(() => {
    if (state.status === 'done') {
      if (state.kind === 'analyze' && state.report) {
        setReport(state.report)
        setMarket(null)
        setActiveId(state.report.meta.id)
      } else if (state.kind === 'market' && state.marketReview) {
        setMarket(state.marketReview)
        setReport(null)
        setActiveId(undefined)
      }
      historyRef.current?.reload()
    }
  }, [state])

  const onAnalyze = (stock: SelectedStock) => {
    setReport(null)
    setMarket(null)
    analyze(stock.code, stock.name)
  }

  const onMarketReview = () => {
    setReport(null)
    setMarket(null)
    setActiveId(undefined)
    marketReview()
  }

  const onSelectHistory = async (id: number) => {
    reset()
    setActiveId(id)
    setMarket(null)
    try {
      const rep = await historyApi.getDetail(id)
      setReport(rep)
    } catch {
      setReport(null)
    }
  }

  const running = state.status === 'running'

  return (
    <>
      <PageHeader title={VI.home.title} subtitle={VI.app.tagline} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        {/* Cột chính */}
        <div className="min-w-0 space-y-4">
          <StockSearch onAnalyze={onAnalyze} loading={running && state.kind === 'analyze'} />

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onMarketReview}
              disabled={running}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <BarChart3 className="h-4 w-4" />
              {VI.home.marketReviewBtn}
            </button>
          </div>

          {/* Kết quả */}
          {running ? (
            <Card className="flex h-72 flex-col items-center justify-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">
                {state.kind === 'market' ? 'Đang tổng hợp diễn biến thị trường…' : `Đang phân tích ${state.label}…`}
              </p>
            </Card>
          ) : state.status === 'error' ? (
            <Card className="flex h-48 flex-col items-center justify-center gap-2 text-center">
              <AlertTriangle className="h-7 w-7 text-danger" />
              <p className="text-sm text-danger">{state.message}</p>
            </Card>
          ) : report ? (
            <StockReportView report={report} />
          ) : market ? (
            <MarketReviewView payload={market} />
          ) : (
            <Placeholder note={VI.home.emptyAnalysis} />
          )}
        </div>

        {/* Cột lịch sử */}
        <aside className="xl:sticky xl:top-2 xl:self-start">
          <HistoryList ref={historyRef} onSelect={onSelectHistory} activeId={activeId} />
        </aside>
      </div>
    </>
  )
}
