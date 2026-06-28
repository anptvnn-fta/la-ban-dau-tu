# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ TƯ VẤN ĐẦU TƯ ĐA KÊNH
===================================

Mở rộng tính năng gợi ý đầu tư thành một trang tư vấn đầu tư tổng thể, đúng lý
thuyết "Hồ sơ nhà đầu tư số" (Chương 6) + chấm điểm chính thức (Chương 4) +
phân bổ đa tài sản (Hướng dẫn Danh mục Cá nhân hoá).

Nguyên tắc cốt lõi: "LUẬT + TỐI ƯU quyết định CON SỐ — AI chỉ DIỄN GIẢI".
Mọi tỷ trọng, điểm số ở file này do LUẬT tính; AI (xem tu_van_ai.py) chỉ viết
lời diễn giải, không được đổi số.

Hai thang rủi ro (tách bạch theo tài liệu):
  • Khả năng chịu rủi ro (Risk Capacity)  — từ dữ liệu TÀI CHÍNH (6 trường) → 4–16.
  • Khẩu vị rủi ro       (Risk Tolerance) — 5 trường Chương 4 → 5–18 (+ luật <5%).
Nguyên tắc thận trọng: NHÓM CUỐI = mức THẤP HƠN giữa Khả năng và Khẩu vị.

Phân bổ đa kênh theo nhóm cuối: Tiết kiệm / Trái phiếu / Cổ phiếu / Vàng (tổng 100%),
có nghiêng theo thời gian mục tiêu. Phần Cổ phiếu chia tiếp 3 rổ biến động (Chương 4).
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#  ĐỊNH NGHĨA 26 TRƯỜNG HỒ SƠ (một nguồn sự thật)
# ════════════════════════════════════════════════════════════
# Mỗi trường: key, label, type(select/number/text), data_group, required,
# dimension(none/capacity/tolerance), multi(bool), options[{key,label,points}], note.

def _o(key: str, label: str, points: Optional[int] = None) -> Dict[str, Any]:
    d = {"key": key, "label": label}
    if points is not None:
        d["points"] = points
    return d


# data_group: nhan_khau | tai_chinh | muc_tieu | rui_ro | hanh_vi
FIELDS: List[Dict[str, Any]] = [
    # ── Nhân khẩu học (WHO) ──
    {"key": "nam_sinh", "label": "Năm sinh", "type": "number", "data_group": "nhan_khau",
     "required": True, "dimension": "none", "note": "Nhập 4 chữ số, ví dụ 1990 — dùng để tính tuổi và giai đoạn cuộc đời.",
     "min": 1940, "max": 2012},
    {"key": "gioi_tinh", "label": "Giới tính", "type": "select", "data_group": "nhan_khau",
     "required": False, "dimension": "none", "options": [
         _o("nam", "Nam"), _o("nu", "Nữ"), _o("khac", "Không muốn tiết lộ")]},
    {"key": "hon_nhan", "label": "Tình trạng hôn nhân", "type": "select", "data_group": "nhan_khau",
     "required": False, "dimension": "none", "options": [
         _o("doc_than", "Độc thân"), _o("da_ket_hon", "Đã kết hôn"),
         _o("ly_hon", "Ly hôn"), _o("goa", "Góa")]},
    {"key": "nguoi_phu_thuoc", "label": "Số người phụ thuộc tài chính", "type": "select", "data_group": "nhan_khau",
     "required": True, "dimension": "capacity", "note": "Người bạn phải nuôi/hỗ trợ (con, cha mẹ già...).",
     "options": [_o("0", "Không có ai", 4), _o("1", "1 người", 3), _o("2", "2 người", 2), _o("3plus", "3 người trở lên", 1)]},
    {"key": "hoc_van", "label": "Trình độ học vấn", "type": "select", "data_group": "nhan_khau",
     "required": False, "dimension": "none", "options": [
         _o("thpt", "Dưới THPT / THPT"), _o("cao_dang", "Cao đẳng"),
         _o("dai_hoc", "Đại học"), _o("sau_dai_hoc", "Sau đại học")]},
    {"key": "nghe_nghiep", "label": "Nghề nghiệp / Lĩnh vực", "type": "select", "data_group": "nhan_khau",
     "required": False, "dimension": "none", "options": [
         _o("cong_chuc", "Công chức / Viên chức nhà nước"), _o("nhan_vien_tu_nhan", "Nhân viên tư nhân / FDI"),
         _o("kinh_doanh", "Kinh doanh / Tự doanh / Chủ doanh nghiệp"), _o("tu_do", "Chuyên gia tự do"),
         _o("giao_vien_y_te", "Giáo viên / Y tế"), _o("nghi_huu", "Đã nghỉ hưu"),
         _o("sinh_vien", "Sinh viên"), _o("noi_tro", "Nội trợ"), _o("khac", "Khác")]},
    {"key": "giai_doan_cuoc_doi", "label": "Giai đoạn cuộc đời", "type": "select", "data_group": "nhan_khau",
     "required": False, "dimension": "none", "options": [
         _o("moi_di_lam", "Mới đi làm, tích lũy ban đầu"), _o("lap_nghiep", "Lập gia đình, mua nhà, sinh con"),
         _o("on_dinh", "Ổn định sự nghiệp, tối ưu tài sản"), _o("gan_nghi_huu", "Chuẩn bị nghỉ hưu (dưới 10 năm)"),
         _o("da_nghi_huu", "Đã nghỉ hưu, bảo toàn và rút dần")]},

    # ── Tài chính (HOW MUCH RISK — khả năng) ──
    {"key": "thu_nhap_thang", "label": "Tổng thu nhập hàng tháng (sau thuế)", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "capacity", "note": "Gồm lương, kinh doanh, cho thuê, cổ tức...",
     "options": [_o("duoi_10", "Dưới 10 triệu đồng", 1), _o("10_20", "10 – 20 triệu đồng", 2),
                 _o("20_50", "20 – 50 triệu đồng", 3), _o("tren_50", "Trên 50 triệu đồng", 4)]},
    {"key": "ty_le_chi_tieu", "label": "Tỷ lệ chi tiêu + trả nợ trên thu nhập", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "capacity", "note": "Ăn uống, nhà ở, đi lại, học phí, trả nợ...",
     "options": [_o("duoi_40", "Dưới 40% thu nhập", 4), _o("40_60", "40 – 60% thu nhập", 3),
                 _o("60_80", "60 – 80% thu nhập", 2), _o("tren_80", "Trên 80% thu nhập", 1)]},
    {"key": "tai_san_rong", "label": "Tài sản ròng ước tính (tài sản − nợ)", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "capacity", "note": "Tiền gửi + cổ phiếu + vàng + BĐS − các khoản vay.",
     "options": [_o("duoi_100tr", "Dưới 100 triệu (hoặc âm)", 1), _o("100tr_500tr", "100 – 500 triệu đồng", 2),
                 _o("500tr_2ty", "500 triệu – 2 tỷ đồng", 3), _o("tren_2ty", "Trên 2 tỷ đồng", 4)]},
    {"key": "quy_du_phong", "label": "Quỹ dự phòng khẩn cấp", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "capacity", "note": "Số tháng chi tiêu trụ được nếu mất thu nhập.",
     "options": [_o("chua_co", "Chưa có / Dưới 1 tháng", 1), _o("1_3_thang", "Đủ 1 – 3 tháng", 2),
                 _o("3_6_thang", "Đủ 3 – 6 tháng", 3), _o("tren_6_thang", "Trên 6 tháng", 4)]},
    {"key": "ganh_no", "label": "Gánh nặng vay nợ hiện tại", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "capacity",
     "options": [_o("khong_no", "Không có khoản nợ nào", 4), _o("vay_mua_nha", "Vay mua nhà (thế chấp, dài hạn)", 3),
                 _o("vay_tieu_dung", "Vay tiêu dùng / mua xe", 2), _o("the_tin_dung", "Nợ thẻ tín dụng / nhiều khoản nợ", 1)]},
    {"key": "von_dau_tu", "label": "Số tiền dự định đầu tư lần này", "type": "select", "data_group": "tai_chinh",
     "required": True, "dimension": "none", "note": "Dùng để ước tính số tiền cụ thể theo từng kênh.",
     "options": [_o("duoi_20tr", "Dưới 20 triệu đồng"), _o("20_100tr", "20 – 100 triệu đồng"),
                 _o("100_500tr", "100 – 500 triệu đồng"), _o("tren_500tr", "Trên 500 triệu đồng")]},
    {"key": "tai_san_dang_co", "label": "Tài sản tài chính đang nắm giữ", "type": "select", "data_group": "tai_chinh",
     "required": False, "dimension": "none", "multi": True, "note": "Chọn tất cả đang có để hệ thống gợi ý bổ sung.",
     "options": [_o("tiet_kiem", "Tiền gửi tiết kiệm"), _o("co_phieu", "Cổ phiếu niêm yết"),
                 _o("trai_phieu", "Trái phiếu / Chứng chỉ tiền gửi"), _o("vang", "Vàng (SJC / nữ trang)"),
                 _o("bds", "Bất động sản"), _o("etf_quy", "Quỹ đầu tư (ETF / chứng chỉ quỹ)"),
                 _o("ngoai_te", "Ngoại tệ"), _o("chua_co", "Chưa có tài sản tài chính nào")]},

    # ── Mục tiêu (WHY) ──
    {"key": "muc_tieu_cu_the", "label": "Mục tiêu tài chính cụ thể", "type": "select", "data_group": "muc_tieu",
     "required": False, "dimension": "none", "multi": True, "note": "Chọn tất cả phù hợp.",
     "options": [_o("mua_nha", "Mua nhà / nâng cấp nhà"), _o("mua_xe", "Mua xe"),
                 _o("du_hoc_con", "Cho con học đại học / du học"), _o("quy_huu_tri", "Chuẩn bị quỹ hưu trí"),
                 _o("tu_do_tai_chinh", "Tích lũy tự do tài chính"), _o("thu_nhap_thu_dong", "Tạo thu nhập thụ động"),
                 _o("quy_khan_cap", "Xây dựng quỹ khẩn cấp"), _o("khac", "Mục tiêu khác")]},
    {"key": "thoi_gian_muc_tieu_nam", "label": "Dự định đạt mục tiêu trong bao nhiêu năm?", "type": "number",
     "data_group": "muc_tieu", "required": True, "dimension": "none",
     "note": "Nhập số năm (1–40). Dùng để nghiêng phân bổ theo thời gian.", "min": 1, "max": 40},

    # ── Rủi ro (Chương 4 — khẩu vị) ──
    {"key": "muc_tieu_dau_tu", "label": "Mục tiêu đầu tư chính", "type": "select", "data_group": "rui_ro",
     "required": True, "dimension": "tolerance", "options": [
         _o("bao_toan_von", "Bảo toàn vốn & chống lạm phát (không muốn mất tiền)", 1),
         _o("co_tuc", "Nhận cổ tức / lãi đều đặn hàng năm", 2),
         _o("tang_truong_on_dinh", "Tăng trưởng ổn định, chấp nhận lên xuống vừa phải", 3),
         _o("rui_ro_cao", "Chấp nhận rủi ro cao để đạt lãi lớn nhất", 4)]},
    {"key": "thoi_gian_dau_tu", "label": "Thời gian để tiền đầu tư (không rút)", "type": "select", "data_group": "rui_ro",
     "required": True, "dimension": "tolerance", "options": [
         _o("ngan_han", "Ngắn hạn, dưới 1 năm", 1), _o("trung_han", "Trung hạn, 1 – 3 năm", 2),
         _o("dai_han", "Dài hạn, trên 3 năm", 3)]},
    {"key": "kinh_nghiem", "label": "Kinh nghiệm đầu tư", "type": "select", "data_group": "rui_ro",
     "required": True, "dimension": "tolerance", "options": [
         _o("chua_co", "Chưa đầu tư bao giờ / dưới 1 năm", 1), _o("1_3_nam", "1 – 3 năm", 2),
         _o("tren_3_nam", "Trên 3 năm", 3)]},
    {"key": "loi_nhuan_mong_muon", "label": "Lợi nhuận mong muốn mỗi năm", "type": "select", "data_group": "rui_ro",
     "required": True, "dimension": "tolerance", "options": [
         _o("6_8pct", "6 – 8%/năm (ngang tiết kiệm tốt)", 1), _o("10_15pct", "10 – 15%/năm", 2),
         _o("15_25pct", "15 – 25%/năm", 3), _o("tren_25pct", "Trên 25%/năm", 4)]},
    {"key": "muc_rui_ro_chap_nhan", "label": "Mức thua lỗ tối đa chấp nhận được", "type": "select", "data_group": "rui_ro",
     "required": True, "dimension": "tolerance",
     "note": "Câu này ảnh hưởng trực tiếp đến nhóm đầu tư. Chọn dưới 5% → hệ thống ưu tiên bảo toàn vốn.",
     "options": [_o("duoi_5pct", "Dưới 5% (gần như không chấp nhận mất tiền)", 1),
                 _o("5_10pct", "5 – 10% (giảm nhẹ vẫn ổn)", 2),
                 _o("10_20pct", "10 – 20% (chịu được giảm mạnh tạm thời)", 3),
                 _o("tren_20pct", "Trên 20% (sẵn sàng biến động lớn để đổi lợi nhuận)", 4)]},

    # ── Hành vi (HOW TO INVEST) ──
    # 3 trường hành vi dưới đây CHỈ dùng cho AI diễn giải chân dung, KHÔNG chấm
    # điểm khẩu vị (khẩu vị bám đúng 5 trường Chương 4) → dimension='none'.
    # Vẫn giữ điểm trong options để tham khảo định tính nếu cần về sau.
    {"key": "phan_ung_thi_truong_giam", "label": "Khi danh mục giảm 15–20% trong 1 tháng, bạn sẽ?", "type": "select",
     "data_group": "hanh_vi", "required": False, "dimension": "none", "options": [
         _o("ban_ngay", "Bán ngay để cắt lỗ, không chịu được", 1), _o("lo_lang", "Lo lắng, cân nhắc bán một phần", 2),
         _o("giu_nguyen", "Giữ nguyên, tin tưởng dài hạn", 3), _o("mua_them", "Mua thêm vì thấy là cơ hội", 4)]},
    {"key": "tai_san_ua_thich", "label": "Loại tài sản bạn an tâm và thích nhất", "type": "select",
     "data_group": "hanh_vi", "required": False, "dimension": "none", "options": [
         _o("tiet_kiem_tp", "Tiền gửi / Trái phiếu chính phủ", 1), _o("vang_bds", "Vàng / Bất động sản", 2),
         _o("co_phieu_bluechip", "Cổ phiếu ổn định, bluechip, cổ tức cao", 3),
         _o("co_phieu_tang_truong", "Cổ phiếu tăng trưởng cao / tài sản rủi ro cao", 4)]},
    {"key": "thoi_gian_nam_giu", "label": "Thường nắm giữ một khoản đầu tư bao lâu?", "type": "select",
     "data_group": "hanh_vi", "required": False, "dimension": "none", "options": [
         _o("duoi_1_thang", "Dưới 1 tháng (chốt lời/cắt lỗ nhanh)", 1), _o("1_6_thang", "1 – 6 tháng", 2),
         _o("6t_2nam", "6 tháng – 2 năm", 3), _o("tren_2_nam", "Trên 2 năm (mua và giữ)", 4)]},
    {"key": "tan_suat_theo_doi", "label": "Tần suất theo dõi danh mục", "type": "select", "data_group": "hanh_vi",
     "required": False, "dimension": "none", "options": [
         _o("hang_ngay", "Hàng ngày"), _o("hang_tuan", "Hàng tuần"),
         _o("hang_thang", "Hàng tháng"), _o("hiem_khi", "Hiếm khi, chỉ khi có tin lớn")]},
    {"key": "hieu_biet_tai_chinh", "label": "Tự đánh giá mức độ hiểu biết tài chính", "type": "select",
     "data_group": "hanh_vi", "required": False, "dimension": "none", "options": [
         _o("moi_bat_dau", "Mới bắt đầu, cần hướng dẫn từ đầu"), _o("co_ban", "Hiểu cơ bản"),
         _o("kha_tot", "Khá tốt, có kinh nghiệm thực tế"), _o("chuyen_sau", "Chuyên sâu, tự đọc báo cáo tài chính")]},
]

_FIELD_BY_KEY = {f["key"]: f for f in FIELDS}


def _points_map(field_key: str) -> Dict[str, int]:
    f = _FIELD_BY_KEY[field_key]
    return {o["key"]: o["points"] for o in f.get("options", []) if "points" in o}


def _label_of(field_key: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    f = _FIELD_BY_KEY.get(field_key)
    if not f:
        return value
    for o in f.get("options", []):
        if o["key"] == value:
            return o["label"]
    return value


# ════════════════════════════════════════════════════════════
#  THANG KHẢ NĂNG (capacity) — 6 trường tài chính → 4–16
# ════════════════════════════════════════════════════════════
_CAPACITY_FIELDS = ["nguoi_phu_thuoc", "thu_nhap_thang", "ty_le_chi_tieu", "tai_san_rong", "quy_du_phong", "ganh_no"]
# raw 6..24 → chuẩn hoá về 4..16


def compute_capacity(profile: Dict[str, Any]) -> Tuple[int, int, str]:
    """Trả (điểm thô 6–24, điểm chuẩn hoá 4–16, nhóm khả năng)."""
    raw = 0
    for k in _CAPACITY_FIELDS:
        pm = _points_map(k)
        v = profile.get(k)
        if v not in pm:
            raise ValueError(f"Thiếu hoặc sai trường tài chính bắt buộc: {k}")
        raw += pm[v]
    # chuẩn hoá tuyến tính 6..24 -> 4..16
    norm = round((raw - 6) / (24 - 6) * (16 - 4) + 4)
    norm = max(4, min(16, norm))
    if norm <= 7:
        group = "than_trong"
    elif norm <= 11:
        group = "can_bang"
    else:
        group = "mao_hiem"
    return raw, norm, group


# ════════════════════════════════════════════════════════════
#  THANG KHẨU VỊ (tolerance) — 5 trường Chương 4 → 5–18 (+ luật <5%)
# ════════════════════════════════════════════════════════════
_TOLERANCE_FIELDS = ["muc_tieu_dau_tu", "thoi_gian_dau_tu", "kinh_nghiem", "loi_nhuan_mong_muon", "muc_rui_ro_chap_nhan"]


def compute_tolerance(profile: Dict[str, Any]) -> Tuple[int, str, bool]:
    """Trả (tổng điểm 5–18, nhóm khẩu vị Chương 4, luật-đặc-biệt-kích-hoạt)."""
    total = 0
    for k in _TOLERANCE_FIELDS:
        pm = _points_map(k)
        v = profile.get(k)
        if v not in pm:
            raise ValueError(f"Thiếu hoặc sai trường khẩu vị bắt buộc: {k}")
        total += pm[v]

    # LUẬT ĐẶC BIỆT — KHÔNG XÓA: rủi ro chấp nhận "Dưới 5%" (1đ) → ép Phòng thủ.
    forced = profile.get("muc_rui_ro_chap_nhan") == "duoi_5pct"
    if forced:
        return total, "phong_thu", True
    if total <= 9:
        group = "phong_thu"
    elif total <= 14:
        group = "can_bang"
    else:
        group = "tan_cong"
    return total, group, False


# ════════════════════════════════════════════════════════════
#  NGUYÊN TẮC THẬN TRỌNG — nhóm cuối = min(khả năng, khẩu vị)
# ════════════════════════════════════════════════════════════
# rank thống nhất: 1 = thấp (phòng thủ/thận trọng), 3 = cao (tấn công/mạo hiểm).
_TOL_RANK = {"phong_thu": 1, "can_bang": 2, "tan_cong": 3}
_CAP_RANK = {"than_trong": 1, "can_bang": 2, "mao_hiem": 3}
_FINAL_KEY = {1: "phong_thu", 2: "can_bang", 3: "tan_cong"}

GROUP_LABEL = {"phong_thu": "Thận trọng", "can_bang": "Cân bằng", "tan_cong": "Mạo hiểm"}
GROUP_EN = {"phong_thu": "Conservative", "can_bang": "Balanced", "tan_cong": "Aggressive"}
# Nhãn riêng cho thang khẩu vị Chương 4 (để hiển thị đúng nguyên văn tài liệu).
TOLERANCE_LABEL = {"phong_thu": "Phòng thủ", "can_bang": "Cân bằng", "tan_cong": "Tấn công"}
CAPACITY_LABEL = {"than_trong": "Thận trọng", "can_bang": "Cân bằng", "mao_hiem": "Mạo hiểm"}

GROUP_DESC = {
    "phong_thu": "Ưu tiên an toàn và bảo toàn vốn; chấp nhận lợi nhuận thấp để đổi lấy sự yên tâm.",
    "can_bang": "Cân bằng giữa tăng trưởng và an toàn; vẫn giữ một phần đệm phòng thủ.",
    "tan_cong": "Ưu tiên tăng trưởng mạnh, chấp nhận biến động lớn để đạt lợi nhuận cao.",
}


def reconcile(tolerance_group: str, capacity_group: str) -> str:
    """Nhóm cuối = mức THẤP HƠN giữa khẩu vị và khả năng (nguyên tắc thận trọng)."""
    final_rank = min(_TOL_RANK[tolerance_group], _CAP_RANK[capacity_group])
    return _FINAL_KEY[final_rank]


# ════════════════════════════════════════════════════════════
#  PHÂN BỔ ĐA TÀI SẢN theo nhóm cuối + nghiêng theo thời gian
# ════════════════════════════════════════════════════════════
# 4 lớp: tiet_kiem (tiền gửi/tiền mặt), trai_phieu, co_phieu, vang. Tổng = 100.
# Gốc tài liệu có thêm lớp ETF (5/10/20%). App chưa có dữ liệu ETF live nên gộp
# phần ETF (bản chất "tăng trưởng + đa dạng hoá") vào Cổ phiếu cho đủ 100%.
ASSET_ALLOCATION: Dict[str, Dict[str, int]] = {
    "phong_thu": {"tiet_kiem": 35, "trai_phieu": 40, "co_phieu": 20, "vang": 5},   # 15 CP + 5 ETF
    "can_bang":  {"tiet_kiem": 20, "trai_phieu": 30, "co_phieu": 45, "vang": 5},   # 35 CP + 10 ETF
    "tan_cong":  {"tiet_kiem": 5,  "trai_phieu": 5,  "co_phieu": 85, "vang": 5},   # 65 CP + 20 ETF
}

ASSET_LABEL = {"tiet_kiem": "Tiết kiệm", "trai_phieu": "Trái phiếu", "co_phieu": "Cổ phiếu", "vang": "Vàng"}
ASSET_ROLE = {
    "tiet_kiem": "Đệm an toàn, thanh khoản cao",
    "trai_phieu": "Thu nhập ổn định, biến động thấp",
    "co_phieu": "Động lực tăng trưởng chính",
    "vang": "Phòng thủ, ít tương quan cổ phiếu",
}

# Tỷ lệ chia 3 rổ biến động TRONG phần cổ phiếu (Chương 4: 70-20-10 / 40-40-20 / 10-30-60).
STOCK_SPLIT = {
    "phong_thu": {"on_dinh": 70, "trung_binh": 20, "rui_ro": 10},
    "can_bang":  {"on_dinh": 40, "trung_binh": 40, "rui_ro": 20},
    "tan_cong":  {"on_dinh": 10, "trung_binh": 30, "rui_ro": 60},
}


def apply_time_tilt(alloc: Dict[str, int], years: Optional[int]) -> Tuple[Dict[str, int], str]:
    """Nghiêng phân bổ theo thời gian mục tiêu. Trả (phân bổ mới tổng=100, nhãn nghiêng).

    <3 năm: Cổ phiếu −10 → Tiết kiệm +5, Trái phiếu +5.
    >10 năm: Tiết kiệm −10 → Cổ phiếu +10.
    Còn lại giữ nguyên. Có chặn âm + chuẩn hoá tổng về đúng 100.
    """
    a = dict(alloc)
    tilt = "giu_nguyen"
    if years is not None and years < 3:
        tilt = "ngan_han"
        move = min(10, a["co_phieu"])  # không để cổ phiếu âm
        a["co_phieu"] -= move
        a["tiet_kiem"] += move // 2 + move % 2
        a["trai_phieu"] += move // 2
    elif years is not None and years > 10:
        tilt = "dai_han"
        move = min(10, a["tiet_kiem"])  # không để tiết kiệm âm
        a["tiet_kiem"] -= move
        a["co_phieu"] += move

    # Chặn âm + chuẩn hoá tổng = 100 (bù/trừ vào lớp lớn nhất).
    for k in a:
        a[k] = max(0, a[k])
    diff = 100 - sum(a.values())
    if diff != 0:
        biggest = max(a, key=lambda k: a[k])
        a[biggest] = max(0, a[biggest] + diff)
    return a, tilt


# Số tiền đại diện theo khoảng vốn (triệu đồng) — để ước tính số tiền mỗi kênh.
VON_MIDPOINT = {"duoi_20tr": 10, "20_100tr": 60, "100_500tr": 300, "tren_500tr": 750}


# ════════════════════════════════════════════════════════════
#  PHÂN LOẠI CỔ PHIẾU theo biến động 252 phiên (vũ trụ đa ngành)
# ════════════════════════════════════════════════════════════
# Vũ trụ cổ phiếu thanh khoản, đa ngành — phân loại theo biến động thực tế.
STOCK_UNIVERSE = [
    # Ngân hàng / tài chính
    "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "STB", "HDB", "SSI", "VND",
    # Tiêu dùng / bán lẻ
    "VNM", "SAB", "MWG", "PNJ", "MSN",
    # Công nghiệp / vật liệu / năng lượng
    "HPG", "GAS", "PLX", "BSR", "DGC", "DCM",
    # Công nghệ / tiện ích / BĐS
    "FPT", "REE", "POW", "VIC", "VHM", "VRE", "KDH",
]

_SESSIONS = 252
_STOCK_TTL = 12 * 3600
_stock_lock = threading.Lock()
_stock_cache: Dict[str, Any] = {"at": 0.0, "payload": None}


def _bucket_of(vol_pct: float) -> str:
    """Phân rổ theo ngưỡng tài liệu: <30 ổn định, 30–60 trung bình, >60 rủi ro."""
    if vol_pct < 30:
        return "on_dinh"
    if vol_pct <= 60:
        return "trung_binh"
    return "rui_ro"


def _stock_volatility(symbol: str) -> Optional[float]:
    """% biến động 252 phiên = (max high − min low)/min low × 100. Fail → None."""
    end = _dt.date.today()
    start = end - _dt.timedelta(days=420)  # dư ngày lịch để gom đủ 252 phiên
    for src in ("VCI", "KBS"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from vnstock.api.quote import Quote  # type: ignore

            df = Quote(symbol=symbol, source=src).history(
                start=start.isoformat(), end=end.isoformat(), interval="1D"
            )
            if df is None or getattr(df, "empty", True):
                continue
            df = df.tail(_SESSIONS)
            hi = float(df["high"].max())
            lo = float(df["low"].min())
            if lo <= 0 or hi <= 0:
                continue
            return round((hi - lo) / lo * 100, 1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[TuVan] biến động %s (%s) lỗi: %s", symbol, src, exc)
            continue
    return None


def classify_universe() -> Dict[str, Any]:
    """Phân loại toàn bộ vũ trụ cổ phiếu thành 3 rổ biến động (cache 12 giờ)."""
    with _stock_lock:
        c = _stock_cache.get("payload")
        if c is not None and (time.time() - _stock_cache["at"]) < _STOCK_TTL:
            return {**c, "from_cache": True}

    stocks: List[Dict[str, Any]] = []
    missing: List[str] = []
    for sym in STOCK_UNIVERSE:
        vol = _stock_volatility(sym)
        if vol is None:
            missing.append(sym)
            continue
        stocks.append({"symbol": sym, "volatility_pct": vol, "bucket": _bucket_of(vol)})
    payload = {"stocks": stocks, "missing": missing,
               "generated_at": _dt.datetime.now().isoformat(timespec="seconds")}
    with _stock_lock:
        _stock_cache.update(at=time.time(), payload=payload)
    return {**payload, "from_cache": False}


def get_stock_buckets() -> Dict[str, Any]:
    """Gom vũ trụ cổ phiếu theo 3 rổ, mỗi rổ tối đa 6 mã."""
    cls = classify_universe()
    by: Dict[str, List[Dict[str, Any]]] = {"on_dinh": [], "trung_binh": [], "rui_ro": []}
    for s in cls["stocks"]:
        by[s["bucket"]].append(s)
    by["on_dinh"].sort(key=lambda x: x["volatility_pct"])
    by["trung_binh"].sort(key=lambda x: x["volatility_pct"])
    by["rui_ro"].sort(key=lambda x: -x["volatility_pct"])
    buckets = []
    for b in ("on_dinh", "trung_binh", "rui_ro"):
        buckets.append({
            "bucket": b,
            "label": {"on_dinh": "Ổn định", "trung_binh": "Trung bình", "rui_ro": "Rủi ro"}[b],
            "stocks": by[b][:6],
        })
    return {
        "generated_at": cls["generated_at"],
        "buckets": buckets,
        "data_warning": ("Chưa lấy được giá: " + ", ".join(cls["missing"]) + ".") if cls["missing"] else None,
    }


# ════════════════════════════════════════════════════════════
#  DỮ LIỆU LIVE từng kênh (tiết kiệm / trái phiếu / vàng)
# ════════════════════════════════════════════════════════════
def _term_for_horizon(thoi_gian_dau_tu: Optional[str], years: Optional[int]) -> int:
    """Chọn kỳ hạn tiết kiệm (tháng) phù hợp thời gian đầu tư."""
    if years is not None:
        if years < 1:
            return 6
        if years <= 3:
            return 12
        return 24
    return {"ngan_han": 6, "trung_han": 12, "dai_han": 24}.get(thoi_gian_dau_tu or "", 12)


def get_market_data(thoi_gian_dau_tu: Optional[str] = None, years: Optional[int] = None) -> Dict[str, Any]:
    """Gộp dữ liệu live: tiết kiệm (top NH theo kỳ hạn), trái phiếu, vàng. Fail-open từng phần."""
    out: Dict[str, Any] = {"warnings": []}

    # Tiết kiệm
    term = _term_for_horizon(thoi_gian_dau_tu, years)
    try:
        from src.services.savings_service import get_savings_overview
        sv = get_savings_overview()
        terms = sv.get("terms") or []
        idx = terms.index(term) if term in terms else (terms.index(12) if 12 in terms else 0)
        ranked = [
            {"bank": b["name"], "rate": b["rates"][idx]}
            for b in (sv.get("banks") or []) if b["rates"][idx] is not None
        ]
        ranked.sort(key=lambda x: -x["rate"])
        out["tiet_kiem"] = {"term_months": term, "top": ranked[:5], "sbv_policy_rate": sv.get("sbv_policy_rate")}
        if not ranked:
            out["warnings"].append("Chưa lấy được lãi suất tiết kiệm.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TuVan] tiết kiệm lỗi: %s", exc)
        out["tiet_kiem"] = None
        out["warnings"].append("Chưa lấy được lãi suất tiết kiệm.")

    # Trái phiếu
    try:
        from src.services.bond_service import get_bond_overview
        bd = get_bond_overview()
        out["trai_phieu"] = {
            "sbv_policy_rate": bd.get("sbv_policy_rate"),
            "us_yield": bd.get("us_yield"),
            "vn10y_ref": bd.get("vn10y_ref"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TuVan] trái phiếu lỗi: %s", exc)
        out["trai_phieu"] = None

    # Vàng
    try:
        from src.services.gold_service import get_gold_overview
        gd = get_gold_overview()
        out["vang"] = {
            "sjc_buy": gd.get("sjc_buy"),
            "sjc_sell": gd.get("sjc_sell"),
            "world_per_luong_vnd": gd.get("world_per_luong_vnd"),
            "premium_pct": gd.get("premium_pct"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TuVan] vàng lỗi: %s", exc)
        out["vang"] = None

    return out


# ════════════════════════════════════════════════════════════
#  TỔNG HỢP KẾT QUẢ SỐ (không gọi AI)
# ════════════════════════════════════════════════════════════
def _validate_required(profile: Dict[str, Any]) -> None:
    for f in FIELDS:
        if not f.get("required"):
            continue
        v = profile.get(f["key"])
        if v in (None, "", []):
            raise ValueError(f"Thiếu trường bắt buộc: {f['label']}")


def _age_from(nam_sinh: Any) -> Optional[int]:
    try:
        y = int(nam_sinh)
        age = _dt.date.today().year - y
        return age if 5 <= age <= 110 else None
    except Exception:  # noqa: BLE001
        return None


def build_result(profile: Dict[str, Any], *, with_market: bool = True) -> Dict[str, Any]:
    """Tính toàn bộ phần SỐ: 2 thang điểm, nhóm cuối, phân bổ đa kênh, số tiền, live data."""
    _validate_required(profile)

    cap_raw, cap_norm, cap_group = compute_capacity(profile)
    tol_total, tol_group, forced = compute_tolerance(profile)
    final_group = reconcile(tol_group, cap_group)

    years = None
    try:
        years = int(profile.get("thoi_gian_muc_tieu_nam")) if profile.get("thoi_gian_muc_tieu_nam") not in (None, "") else None
        if years is not None:
            years = max(1, min(40, years))  # chặn trong khoảng hợp lệ 1–40 năm
    except Exception:  # noqa: BLE001
        years = None

    base_alloc = ASSET_ALLOCATION[final_group]
    alloc, tilt = apply_time_tilt(base_alloc, years)

    # Số tiền ước tính mỗi kênh (triệu đồng).
    von_mid = VON_MIDPOINT.get(profile.get("von_dau_tu") or "", 0)
    allocation = []
    for cls in ("tiet_kiem", "trai_phieu", "co_phieu", "vang"):
        pct = alloc[cls]
        allocation.append({
            "asset_class": cls,
            "label": ASSET_LABEL[cls],
            "percent": pct,
            "amount_trieu": round(von_mid * pct / 100, 1) if von_mid else None,
            "role": ASSET_ROLE[cls],
        })

    # Chia 3 rổ trong phần cổ phiếu (theo nhóm cuối).
    split = STOCK_SPLIT[final_group]
    co_phieu_pct = alloc["co_phieu"]
    stock_split = [
        {"bucket": b, "label": {"on_dinh": "Ổn định", "trung_binh": "Trung bình", "rui_ro": "Rủi ro"}[b],
         "within_stock_pct": split[b],
         "portfolio_pct": round(co_phieu_pct * split[b] / 100, 1)}
        for b in ("on_dinh", "trung_binh", "rui_ro")
    ]

    age = _age_from(profile.get("nam_sinh"))

    result = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "age": age,
        "von_midpoint_trieu": von_mid or None,
        "capacity": {"raw": cap_raw, "score": cap_norm, "group": cap_group, "label": CAPACITY_LABEL[cap_group]},
        "tolerance": {"total": tol_total, "group": tol_group, "label": TOLERANCE_LABEL[tol_group], "forced_defensive": forced},
        "final_group": final_group,
        "final_label": GROUP_LABEL[final_group],
        "final_en": GROUP_EN[final_group],
        "final_desc": GROUP_DESC[final_group],
        "forced_defensive": forced,
        "time_tilt": tilt,
        "years": years,
        "allocation": allocation,
        "stock_split": stock_split,
    }
    if with_market:
        result["market_data"] = get_market_data(profile.get("thoi_gian_dau_tu"), years)
    return result


# ════════════════════════════════════════════════════════════
#  Bộ tuỳ chọn cho giao diện
# ════════════════════════════════════════════════════════════
def get_options() -> Dict[str, Any]:
    """Trả định nghĩa 26 trường (nhóm theo data_group) để giao diện dựng wizard."""
    fields = []
    for f in FIELDS:
        item = {
            "key": f["key"], "label": f["label"], "type": f["type"],
            "data_group": f["data_group"], "required": f["required"],
            "dimension": f["dimension"], "multi": bool(f.get("multi")),
            "note": f.get("note"),
        }
        if "options" in f:
            item["options"] = [{"key": o["key"], "label": o["label"]} for o in f["options"]]
        for mk in ("min", "max"):
            if mk in f:
                item[mk] = f[mk]
        fields.append(item)
    return {"fields": fields}


def labels_for_ai(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Đổi key lựa chọn → NHÃN tiếng Việt để đưa vào AI (KHÔNG đưa số tuyệt đối PII)."""
    out: Dict[str, Any] = {}
    for f in FIELDS:
        k = f["key"]
        # KHÔNG đưa NĂM SINH thật vào prompt (PII) — AI chỉ cần TUỔI, đã có sẵn
        # trong ai_input (xem tu_van_ai._build_ai_input).
        if k == "nam_sinh":
            continue
        v = profile.get(k)
        if v in (None, "", []):
            continue
        if f.get("multi") and isinstance(v, list):
            out[k] = [_label_of(k, x) for x in v]
        elif f["type"] == "number":
            out[k] = v  # chỉ còn số năm mục tiêu (không nhạy cảm)
        else:
            out[k] = _label_of(k, v)
    return out
