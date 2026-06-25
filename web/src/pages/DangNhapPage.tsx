import { CandlestickChart } from 'lucide-react'
import { VI } from '@/strings/vi'

export default function DangNhapPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
            <CandlestickChart className="h-6 w-6" />
          </span>
          <h1 className="font-heading text-xl font-bold text-foreground">{VI.app.name}</h1>
          <p className="text-xs text-muted-foreground">{VI.app.tagline}</p>
        </div>
        <p className="text-center text-sm text-muted-foreground">{VI.auth.login}</p>
      </div>
    </div>
  )
}
