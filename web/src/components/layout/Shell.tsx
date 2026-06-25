import type { ReactNode } from 'react'
import { SidebarNav } from './SidebarNav'

/** Khung bố cục chính: sidebar trái + vùng nội dung cuộn. */
export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      <SidebarNav />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1400px] px-5 py-6 lg:px-8">{children}</div>
      </main>
    </div>
  )
}
