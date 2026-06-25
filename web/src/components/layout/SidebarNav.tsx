import { NavLink } from 'react-router-dom'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { CandlestickChart, Moon, Sun } from 'lucide-react'
import { NAV_ITEMS } from '@/nav'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const isDark = theme !== 'light'
  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label={VI.nav.theme}
      title={VI.nav.theme}
      className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {mounted && isDark ? <Sun className="h-5 w-5 shrink-0" /> : <Moon className="h-5 w-5 shrink-0" />}
      <span className="truncate">{mounted ? (isDark ? VI.nav.themeLight : VI.nav.themeDark) : VI.nav.theme}</span>
    </button>
  )
}

export function SidebarNav() {
  return (
    <aside className="flex h-full w-[240px] shrink-0 flex-col border-r border-border bg-card/60 px-3 py-4">
      {/* Thương hiệu */}
      <div className="mb-6 flex items-center gap-2.5 px-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/15 text-primary">
          <CandlestickChart className="h-5 w-5" />
        </span>
        <div className="min-w-0 leading-tight">
          <p className="truncate font-heading text-[15px] font-bold text-foreground">{VI.app.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{VI.app.tagline}</p>
        </div>
      </div>

      {/* Điều hướng */}
      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              cn(
                'flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isActive
                  ? 'bg-primary/12 text-primary'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
              )
            }
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Chân: chuyển giao diện */}
      <div className="mt-2 border-t border-border pt-2">
        <ThemeToggle />
      </div>
    </aside>
  )
}
