import { useCallback, useEffect, useRef, useState } from 'react'
import { analysisApi } from '@/api/analysis'
import type { AnalysisReport, MarketReviewPayload } from '@/types/analysis'
import { VI } from '@/strings/vi'

export type AnalysisTaskState =
  | { status: 'idle' }
  | { status: 'running'; kind: 'analyze' | 'market'; label: string }
  | { status: 'done'; kind: 'analyze'; report?: AnalysisReport }
  | { status: 'done'; kind: 'market'; marketReview?: MarketReviewPayload }
  | { status: 'error'; message: string }

/** Trigger phân tích cổ phiếu / diễn biến thị trường (async) và poll trạng thái. */
export function useAnalysisTask() {
  const [state, setState] = useState<AnalysisTaskState>({ status: 'idle' })
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const poll = useCallback((taskId: string, kind: 'analyze' | 'market', label: string) => {
    const tick = async () => {
      try {
        const st = await analysisApi.getStatus(taskId)
        if (st.status === 'completed') {
          if (kind === 'analyze') setState({ status: 'done', kind: 'analyze', report: st.result?.report })
          else setState({ status: 'done', kind: 'market', marketReview: st.marketReviewPayload })
        } else if (st.status === 'failed' || st.status === 'cancelled') {
          setState({ status: 'error', message: st.error || VI.errors.generic })
        } else {
          setState({ status: 'running', kind, label })
          timer.current = window.setTimeout(tick, 2000)
        }
      } catch {
        setState({ status: 'error', message: VI.errors.network })
      }
    }
    void tick()
  }, [])

  const analyze = useCallback(
    async (code: string, name?: string) => {
      window.clearTimeout(timer.current)
      setState({ status: 'running', kind: 'analyze', label: name || code })
      try {
        const res = await analysisApi.analyzeAsync({
          stockCode: code,
          stockName: name,
          reportType: 'detailed',
          asyncMode: true,
          selectionSource: 'autocomplete',
        })
        const taskId = 'taskId' in res ? res.taskId : res.accepted?.[0]?.taskId
        if (!taskId) throw new Error('no task id')
        poll(taskId, 'analyze', name || code)
      } catch (e) {
        setState({ status: 'error', message: e instanceof Error && e.message ? e.message : VI.errors.generic })
      }
    },
    [poll],
  )

  const marketReview = useCallback(async () => {
    window.clearTimeout(timer.current)
    setState({ status: 'running', kind: 'market', label: VI.home.marketReviewBtn })
    try {
      const res = await analysisApi.triggerMarketReview({ sendNotification: false })
      if (!res.taskId) throw new Error('no task id')
      poll(res.taskId, 'market', VI.home.marketReviewBtn)
    } catch (e) {
      setState({ status: 'error', message: e instanceof Error && e.message ? e.message : VI.errors.generic })
    }
  }, [poll])

  const reset = useCallback(() => {
    window.clearTimeout(timer.current)
    setState({ status: 'idle' })
  }, [])

  return { state, analyze, marketReview, reset }
}
