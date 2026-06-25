import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function TinHieuPage() {
  return (
    <>
      <PageHeader title={VI.signals.title} />
      <Placeholder note={VI.signals.emptyState} />
    </>
  )
}
