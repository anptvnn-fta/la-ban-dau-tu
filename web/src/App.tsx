import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'sonner'
import { Shell } from '@/components/layout/Shell'
import PhanTichPage from '@/pages/PhanTichPage'
import TroLyAIPage from '@/pages/TroLyAIPage'
import DanhMucPage from '@/pages/DanhMucPage'
import TinHieuPage from '@/pages/TinHieuPage'
import DanhGiaDuBaoPage from '@/pages/DanhGiaDuBaoPage'
import CanhBaoPage from '@/pages/CanhBaoPage'
import SuDungTokenPage from '@/pages/SuDungTokenPage'
import CaiDatPage from '@/pages/CaiDatPage'
import DangNhapPage from '@/pages/DangNhapPage'
import NotFoundPage from '@/pages/NotFoundPage'

function ShellRoutes() {
  return (
    <Shell>
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
    </Shell>
  )
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/dang-nhap" element={<DangNhapPage />} />
        <Route path="/*" element={<ShellRoutes />} />
      </Routes>
      <Toaster position="top-right" richColors closeButton theme="dark" />
    </>
  )
}
