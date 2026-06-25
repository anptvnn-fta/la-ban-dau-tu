import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function PhanTichPage() {
  return (
    <>
      <PageHeader title={VI.home.title} subtitle={VI.app.tagline} />
      <Placeholder note={VI.home.emptyAnalysis} />
    </>
  )
}
