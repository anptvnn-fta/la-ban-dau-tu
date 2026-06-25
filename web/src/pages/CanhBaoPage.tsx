import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function CanhBaoPage() {
  return (
    <>
      <PageHeader title={VI.alerts.title} />
      <Placeholder note={VI.alerts.emptyState} />
    </>
  )
}
