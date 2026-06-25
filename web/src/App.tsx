import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import { Loader2 } from 'lucide-react'
import { Shell } from '@/components/layout/Shell'

// Tách mã theo route (lazy) để giảm bundle ban đầu.
const PhanTichPage = lazy(() => import('@/pages/PhanTichPage'))
const TroLyAIPage = lazy(() => import('@/pages/TroLyAIPage'))
const DanhMucPage = lazy(() => import('@/pages/DanhMucPage'))
const TinHieuPage = lazy(() => import('@/pages/TinHieuPage'))
const DanhGiaDuBaoPage = lazy(() => import('@/pages/DanhGiaDuBaoPage'))
const CanhBaoPage = lazy(() => import('@/pages/CanhBaoPage'))
const SuDungTokenPage = lazy(() => import('@/pages/SuDungTokenPage'))
const CaiDatPage = lazy(() => import('@/pages/CaiDatPage'))
const DangNhapPage = lazy(() => import('@/pages/DangNhapPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

function PageFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Đang tải">
      <Loader2 className="h-7 w-7 animate-spin text-primary" />
    </div>
  )
}

function ShellRoutes() {
  return (
    <Shell>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<PhanTichPage />} />
          <Route path="/tro-ly" element={<TroLyAIPage />} />
          <Route path="/danh-muc" element={<DanhMucPage />} />
          <Route path="/tin-hieu" element={<TinHieuPage />} />
          <Route path="/danh-gia" element={<DanhGiaDuBaoPage />} />
          <Route path="/canh-bao" element={<CanhBaoPage />} />
          <Route path="/su-dung" element={<SuDungTokenPage />} />
          <Route path="/cai-dat" element={<CaiDatPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </Shell>
  )
}

export default function App() {
  return (
    <>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/dang-nhap" element={<DangNhapPage />} />
          <Route path="/*" element={<ShellRoutes />} />
        </Routes>
      </Suspense>
      <Toaster position="top-right" richColors closeButton theme="dark" />
    </>
  )
}
