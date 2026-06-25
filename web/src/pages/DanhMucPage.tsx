import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function DanhMucPage() {
  return (
    <>
      <PageHeader title={VI.portfolio.title} />
      <Placeholder note={VI.portfolio.emptyState} />
    </>
  )
}
