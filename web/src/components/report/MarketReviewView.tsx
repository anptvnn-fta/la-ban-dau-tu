import { BarChart3 } from 'lucide-react'
import type { MarketReviewPayload } from '@/types/analysis'
import { Card } from '@/components/ui/card'
import { ReportMarkdown } from './ReportMarkdown'
import { fmtPrice, fmtPct, priceToneClass } from '@/utils/num'
import { VI } from '@/strings/vi'

/** Render báo cáo Diễn biến thị trường VN (chỉ số + các mục). */
export function MarketReviewView({ payload }: { payload: MarketReviewPayload }) {
  const title = (payload.rootTitle || payload.title || 'Diễn biến thị trường').replace(/^#+\s*/, '').replace(/^🎯\s*/, '')
  const indices = payload.indices || []
  const sections = (payload.sections || []).filter((s) => s.markdown?.trim())

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          <BarChart3 className="h-3.5 w-3.5" /> DIỄN BIẾN THỊ TRƯỜNG
        </div>
        <h2 className="font-heading text-2xl font-bold text-foreground">{title}</h2>
        {payload.date ? <p className="mt-1 text-xs text-muted-foreground">{payload.date}</p> : null}
      </Card>

      {indices.length ? (
        <Card className="overflow-hidden p-4">
          <h3 className="mb-3 text-base font-semibold text-foreground">Chỉ số chính</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase text-muted-foreground">
                  <th className="px-2 py-2 font-medium">Chỉ số</th>
                  <th className="px-2 py-2 text-right font-medium">Mới nhất</th>
                  <th className="px-2 py-2 text-right font-medium">Thay đổi</th>
                  <th className="px-2 py-2 text-right font-medium">Cao / Thấp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {indices.map((idx) => (
                  <tr key={idx.code || idx.name}>
                    <td className="px-2 py-2 font-medium text-foreground">{idx.name}</td>
                    <td className="px-2 py-2 text-right font-mono tabular-nums text-foreground">{fmtPrice(idx.current)}</td>
                    <td className={`px-2 py-2 text-right font-mono tabular-nums ${priceToneClass(idx.changePct)}`}>{fmtPct(idx.changePct)}</td>
                    <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-muted-foreground">
                      {fmtPrice(idx.high)} / {fmtPrice(idx.low)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {sections.length
        ? sections.map((s) => (
            <Card key={s.key || s.title} className="p-4">
              <h3 className="mb-2 text-base font-semibold text-foreground">{s.title}</h3>
              <ReportMarkdown content={s.markdown} />
            </Card>
          ))
        : payload.markdownReport
          ? (
            <Card className="p-4">
              <ReportMarkdown content={payload.markdownReport} />
            </Card>
          )
          : (
            <Card className="p-6 text-center text-sm text-muted-foreground">{VI.common.noData}</Card>
          )}
    </div>
  )
}
