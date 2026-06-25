import { Hammer } from 'lucide-react'

/** Khối tạm thời cho các trang đang được xây dựng (Phase 3-4). */
export function Placeholder({ note }: { note?: string }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center">
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <Hammer className="h-6 w-6" />
      </span>
      <p className="text-sm text-muted-foreground">{note ?? 'Trang này đang được xây dựng.'}</p>
    </div>
  )
}
