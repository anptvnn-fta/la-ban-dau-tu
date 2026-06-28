import {
  LayoutDashboard, LineChart, MessageSquare, Briefcase, Activity, Target, Bell, Gauge, Settings,
  Coins, Fuel, PiggyBank, Landmark, Compass,
  type LucideIcon,
} from 'lucide-react'
import { VI } from '@/strings/vi'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** Điều hướng theo NHÓM — phản ánh một hệ thống hỗ trợ đầu tư đầy đủ, không chỉ cổ phiếu. */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: VI.nav.groupMarket,
    items: [
      { path: '/tong-quan', label: VI.nav.market, icon: LayoutDashboard },
      { path: '/vang', label: VI.nav.gold, icon: Coins },
      { path: '/xang-dau', label: VI.nav.petrol, icon: Fuel },
      { path: '/tiet-kiem', label: VI.nav.savings, icon: PiggyBank },
      { path: '/trai-phieu', label: VI.nav.bond, icon: Landmark },
    ],
  },
  {
    label: VI.nav.groupAnalysis,
    items: [
      { path: '/', label: VI.nav.home, icon: LineChart },
      { path: '/tu-van-dau-tu', label: VI.nav.profile, icon: Compass },
      { path: '/tro-ly', label: VI.nav.chat, icon: MessageSquare },
    ],
  },
  {
    label: VI.nav.groupPortfolio,
    items: [
      { path: '/danh-muc', label: VI.nav.portfolio, icon: Briefcase },
      { path: '/tin-hieu', label: VI.nav.signals, icon: Activity },
      { path: '/danh-gia', label: VI.nav.backtest, icon: Target },
      { path: '/canh-bao', label: VI.nav.alerts, icon: Bell },
    ],
  },
  {
    label: VI.nav.groupSystem,
    items: [
      { path: '/su-dung', label: VI.nav.usage, icon: Gauge },
      { path: '/cai-dat', label: VI.nav.settings, icon: Settings },
    ],
  },
]

/** Danh sách phẳng (giữ để tương thích nếu nơi khác cần). */
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap(g => g.items)
