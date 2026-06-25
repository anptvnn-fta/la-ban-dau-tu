import { PageHeader } from '@/components/common/PageHeader'
import { Placeholder } from '@/components/common/Placeholder'
import { VI } from '@/strings/vi'

export default function TroLyAIPage() {
  return (
    <>
      <PageHeader title={VI.chat.title} />
      <Placeholder note={VI.chat.emptyState} />
    </>
  )
}
