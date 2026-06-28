# -*- coding: utf-8 -*-
"""Kiểm thử dịch vụ Tư vấn đầu tư: 2 thang điểm, nguyên tắc thận trọng,
luật đặc biệt <5%, bất biến tổng phân bổ = 100% mọi tổ hợp nghiêng thời gian."""

import itertools

import pytest

from src.services import tu_van_service as tv


# Hồ sơ mẫu hợp lệ (đủ trường bắt buộc).
def _base_profile(**kw):
    p = {
        "nam_sinh": 1990,
        "nguoi_phu_thuoc": "1",
        "thu_nhap_thang": "20_50",
        "ty_le_chi_tieu": "40_60",
        "tai_san_rong": "500tr_2ty",
        "quy_du_phong": "3_6_thang",
        "ganh_no": "vay_mua_nha",
        "von_dau_tu": "100_500tr",
        "thoi_gian_muc_tieu_nam": 5,
        "muc_tieu_dau_tu": "tang_truong_on_dinh",
        "thoi_gian_dau_tu": "trung_han",
        "kinh_nghiem": "1_3_nam",
        "loi_nhuan_mong_muon": "10_15pct",
        "muc_rui_ro_chap_nhan": "10_20pct",
    }
    p.update(kw)
    return p


# ── Bất biến phân bổ ─────────────────────────────────────────────────────────

def test_base_allocation_sums_100():
    for g, a in tv.ASSET_ALLOCATION.items():
        assert sum(a.values()) == 100, f"{g} tổng != 100"


def test_time_tilt_always_sums_100():
    # 3 nhóm × nhiều mốc thời gian → tổng luôn = 100, không âm.
    for g in tv.ASSET_ALLOCATION:
        for years in [None, 1, 2, 3, 5, 10, 11, 20, 40]:
            alloc, tilt = tv.apply_time_tilt(tv.ASSET_ALLOCATION[g], years)
            assert sum(alloc.values()) == 100, f"{g}/{years} tổng={sum(alloc.values())}"
            assert all(v >= 0 for v in alloc.values()), f"{g}/{years} có giá trị âm"


def test_stock_split_sums_100():
    for g, s in tv.STOCK_SPLIT.items():
        assert sum(s.values()) == 100


# ── Thang khẩu vị (Chương 4) + luật đặc biệt ─────────────────────────────────

def test_tolerance_balanced():
    # 3+2+2+2+3 = 12 → cân bằng (không ép).
    total, group, forced = tv.compute_tolerance(_base_profile())
    assert total == 12 and group == "can_bang" and forced is False


def test_tolerance_special_rule_forces_defensive():
    # rủi ro = "duoi_5pct" nhưng mọi thứ cao → ép phòng thủ.
    p = _base_profile(muc_tieu_dau_tu="rui_ro_cao", thoi_gian_dau_tu="dai_han",
                      kinh_nghiem="tren_3_nam", loi_nhuan_mong_muon="tren_25pct",
                      muc_rui_ro_chap_nhan="duoi_5pct")
    total, group, forced = tv.compute_tolerance(p)
    assert total == 15 and group == "phong_thu" and forced is True


def test_tolerance_boundaries():
    # tổng 9 → phòng thủ; 10 → cân bằng; 15 → tấn công.
    p9 = _base_profile(muc_tieu_dau_tu="co_tuc", thoi_gian_dau_tu="trung_han", kinh_nghiem="1_3_nam",
                       loi_nhuan_mong_muon="6_8pct", muc_rui_ro_chap_nhan="5_10pct")  # 2+2+2+1+2=9
    assert tv.compute_tolerance(p9)[1] == "phong_thu"
    p17 = _base_profile(muc_tieu_dau_tu="rui_ro_cao", thoi_gian_dau_tu="dai_han", kinh_nghiem="tren_3_nam",
                        loi_nhuan_mong_muon="tren_25pct", muc_rui_ro_chap_nhan="10_20pct")  # 4+3+3+4+3=17→tấn công
    assert tv.compute_tolerance(p17)[1] == "tan_cong"


# ── Thang khả năng ───────────────────────────────────────────────────────────

def test_capacity_low_and_high():
    low = _base_profile(nguoi_phu_thuoc="3plus", thu_nhap_thang="duoi_10", ty_le_chi_tieu="tren_80",
                        tai_san_rong="duoi_100tr", quy_du_phong="chua_co", ganh_no="the_tin_dung")
    raw, norm, group = tv.compute_capacity(low)
    assert raw == 6 and norm == 4 and group == "than_trong"
    high = _base_profile(nguoi_phu_thuoc="0", thu_nhap_thang="tren_50", ty_le_chi_tieu="duoi_40",
                         tai_san_rong="tren_2ty", quy_du_phong="tren_6_thang", ganh_no="khong_no")
    raw, norm, group = tv.compute_capacity(high)
    assert raw == 24 and norm == 16 and group == "mao_hiem"


# ── Nguyên tắc thận trọng (min) ──────────────────────────────────────────────

def test_reconcile_takes_lower():
    assert tv.reconcile("tan_cong", "than_trong") == "phong_thu"   # khẩu vị cao, khả năng thấp → thấp
    assert tv.reconcile("phong_thu", "mao_hiem") == "phong_thu"    # khẩu vị thấp → thấp
    assert tv.reconcile("can_bang", "mao_hiem") == "can_bang"
    assert tv.reconcile("tan_cong", "mao_hiem") == "tan_cong"


def test_reconcile_full_matrix():
    # Mọi tổ hợp (3×3): kết quả = min rank.
    tol = ["phong_thu", "can_bang", "tan_cong"]
    cap = ["than_trong", "can_bang", "mao_hiem"]
    rank = {"phong_thu": 1, "can_bang": 2, "tan_cong": 3}
    crank = {"than_trong": 1, "can_bang": 2, "mao_hiem": 3}
    inv = {1: "phong_thu", 2: "can_bang", 3: "tan_cong"}
    for t, c in itertools.product(tol, cap):
        assert tv.reconcile(t, c) == inv[min(rank[t], crank[c])]


# ── build_result end-to-end (không gọi mạng) ─────────────────────────────────

def test_build_result_smoke():
    r = tv.build_result(_base_profile(), with_market=False)
    assert r["final_group"] in ("phong_thu", "can_bang", "tan_cong")
    assert sum(a["percent"] for a in r["allocation"]) == 100
    # số tiền theo vốn 100_500tr (đại diện 300tr) khớp %.
    tiet = next(a for a in r["allocation"] if a["asset_class"] == "tiet_kiem")
    assert tiet["amount_trieu"] == round(300 * tiet["percent"] / 100, 1)
    # 3 rổ cổ phiếu cộng đúng phần cổ phiếu.
    cp = next(a for a in r["allocation"] if a["asset_class"] == "co_phieu")["percent"]
    assert abs(sum(s["portfolio_pct"] for s in r["stock_split"]) - cp) < 0.5


def test_build_result_forced_defensive_end_to_end():
    p = _base_profile(muc_rui_ro_chap_nhan="duoi_5pct")
    r = tv.build_result(p, with_market=False)
    assert r["forced_defensive"] is True
    # khẩu vị bị ép phòng thủ → nhóm cuối tối đa là phòng thủ.
    assert r["final_group"] == "phong_thu"


def test_missing_required_raises():
    p = _base_profile()
    del p["muc_rui_ro_chap_nhan"]
    with pytest.raises(ValueError):
        tv.build_result(p, with_market=False)


def test_options_shape():
    opts = tv.get_options()
    keys = {f["key"] for f in opts["fields"]}
    assert len(opts["fields"]) == 26
    assert "muc_rui_ro_chap_nhan" in keys and "nam_sinh" in keys
    # mỗi select có options
    for f in opts["fields"]:
        if f["type"] == "select":
            assert f.get("options"), f"{f['key']} thiếu options"


def test_labels_for_ai_no_raw_keys():
    p = _base_profile(tai_san_dang_co=["tiet_kiem", "vang"])
    labels = tv.labels_for_ai(p)
    # đổi key → nhãn tiếng Việt
    assert labels["thu_nhap_thang"] == "20 – 50 triệu đồng"
    assert labels["tai_san_dang_co"] == ["Tiền gửi tiết kiệm", "Vàng (SJC / nữ trang)"]
    # KHÔNG rò rỉ năm sinh thật (PII) vào nhãn AI
    assert "nam_sinh" not in labels


def test_behavior_fields_not_scored_as_tolerance():
    # 3 trường hành vi để dimension='none' (không chấm điểm khẩu vị)
    for k in ("phan_ung_thi_truong_giam", "tai_san_ua_thich", "thoi_gian_nam_giu"):
        assert tv._FIELD_BY_KEY[k]["dimension"] == "none"
        assert k not in tv._TOLERANCE_FIELDS


def test_schema_coerces_empty_number_to_none():
    from api.v1.schemas.tu_van import TuVanInput
    m = TuVanInput(nam_sinh="", thoi_gian_muc_tieu_nam="", muc_rui_ro_chap_nhan="duoi_5pct")
    assert m.nam_sinh is None and m.thoi_gian_muc_tieu_nam is None
