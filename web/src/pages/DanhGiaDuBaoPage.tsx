import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function DanhGiaDuBaoPage() {
  return (
    <>
      <PageHeader title={VI.backtest.title} subtitle={VI.backtest.subtitle} />
      <Placeholder note={VI.backtest.emptyState} />
    </>
  )
}
