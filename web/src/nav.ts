import {
  LayoutDashboard, LineChart, MessageSquare, Briefcase, Activity, Target, Bell, Gauge, Settings,
  type LucideIcon,
} from 'lucide-react'
import { VI } from '@/strings/vi'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

/** Mục điều hướng chính (sidebar). Tên trang thuần tiếng Việt. */
export const NAV_ITEMS: NavItem[] = [
  { path: '/tong-quan', label: VI.nav.market, icon: LayoutDashboard },
  { path: '/', label: VI.nav.home, icon: LineChart },
  { path: '/tro-ly', label: VI.nav.chat, icon: MessageSquare },
  { path: '/danh-muc', label: VI.nav.portfolio, icon: Briefcase },
  { path: '/tin-hieu', label: VI.nav.signals, icon: Activity },
  { path: '/danh-gia', label: VI.nav.backtest, icon: Target },
  { path: '/canh-bao', label: VI.nav.alerts, icon: Bell },
  { path: '/su-dung', label: VI.nav.usage, icon: Gauge },
  { path: '/cai-dat', label: VI.nav.settings, icon: Settings },
]
