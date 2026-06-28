# -*- coding: utf-8 -*-
"""
===================================
Công cụ ĐA TÀI SẢN cho Trợ Lý AI
===================================

Cho phép trợ lý hội thoại trả lời về các kênh đầu tư ngoài cổ phiếu:
VÀNG, TIẾT KIỆM (lãi suất ngân hàng), TRÁI PHIẾU / lãi suất điều hành, XĂNG DẦU.

Mỗi tool gọi vào service dữ liệu sẵn có và trả về dict GỌN (chỉ số liệu cần
thiết) để tiết kiệm token; mọi tool fail-open (lỗi → trả {"error": ...}).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.agent.tools.registry import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  VÀNG
# ════════════════════════════════════════════════════════════
def _handle_get_gold_price() -> Dict[str, Any]:
    """Giá vàng SJC trong nước, giá thế giới quy đổi và chênh lệch (premium)."""
    try:
        from src.services.gold_service import get_gold_overview
        d = get_gold_overview()
        return {
            "sjc_ten": d.get("sjc_name"),
            "sjc_mua_vnd_luong": d.get("sjc_buy"),
            "sjc_ban_vnd_luong": d.get("sjc_sell"),
            "gia_the_gioi_usd_oz": d.get("world_usd_oz"),
            "the_gioi_quy_doi_vnd_luong": d.get("world_per_luong_vnd"),
            "chenh_lech_premium_pct": d.get("premium_pct"),
            "nhan_dinh": d.get("assessment"),
            "cap_nhat": d.get("generated_at"),
            "ghi_chu": "Giá theo VND/lượng. Premium = SJC đắt hơn giá thế giới quy đổi bao nhiêu %.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Tool gold] lỗi: %s", exc)
        return {"error": f"Không lấy được giá vàng: {exc}"}


get_gold_price_tool = ToolDefinition(
    name="get_gold_price",
    description="Lấy giá vàng miếng SJC trong nước (mua/bán, VND/lượng), giá vàng thế giới quy đổi "
                "và mức chênh lệch (premium) của SJC so với thế giới. Dùng khi người dùng hỏi về VÀNG.",
    parameters=[],
    handler=_handle_get_gold_price,
    category="data",
)


# ════════════════════════════════════════════════════════════
#  TIẾT KIỆM (lãi suất ngân hàng)
# ════════════════════════════════════════════════════════════
def _handle_get_savings_rates(term_months: int = 12) -> Dict[str, Any]:
    """Lãi suất tiết kiệm các ngân hàng. term_months: kỳ hạn quan tâm (0 = mọi kỳ hạn tốt nhất)."""
    try:
        from src.services.savings_service import get_savings_overview
        d = get_savings_overview()
        terms = d.get("terms") or []
        out: Dict[str, Any] = {
            "lai_suat_dieu_hanh_sbv_pct": d.get("sbv_policy_rate"),
            "cap_nhat": d.get("generated_at"),
            "ghi_chu": "Lãi suất %/năm. 'tot_nhat_theo_ky_han' = ngân hàng có lãi cao nhất mỗi kỳ hạn.",
        }
        # Lãi suất tốt nhất theo từng kỳ hạn.
        out["tot_nhat_theo_ky_han"] = [
            {"ky_han_thang": b.get("term"), "ngan_hang": b.get("bank"), "lai_suat_pct": b.get("rate")}
            for b in (d.get("best") or [])
        ]
        # Nếu hỏi một kỳ hạn cụ thể → top 5 ngân hàng kỳ hạn đó.
        try:
            term_months = int(term_months)
        except Exception:  # noqa: BLE001
            term_months = 12
        if term_months and term_months in terms:
            idx = terms.index(term_months)
            ranked = [
                {"ngan_hang": b["name"], "lai_suat_pct": b["rates"][idx]}
                for b in (d.get("banks") or []) if b["rates"][idx] is not None
            ]
            ranked.sort(key=lambda x: -x["lai_suat_pct"])
            out["top_ngan_hang_ky_han"] = {"ky_han_thang": term_months, "danh_sach": ranked[:5]}
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Tool savings] lỗi: %s", exc)
        return {"error": f"Không lấy được lãi suất tiết kiệm: {exc}"}


get_savings_rates_tool = ToolDefinition(
    name="get_savings_rates",
    description="Lấy lãi suất tiết kiệm (gửi ngân hàng) của các ngân hàng Việt Nam theo kỳ hạn, "
                "kèm lãi suất điều hành SBV. Dùng khi người dùng hỏi về GỬI TIẾT KIỆM / LÃI SUẤT NGÂN HÀNG.",
    parameters=[
        ToolParameter(
            name="term_months", type="integer",
            description="Kỳ hạn quan tâm (tháng), ví dụ 6, 12, 24. Mặc định 12.",
            required=False, default=12,
        ),
    ],
    handler=_handle_get_savings_rates,
    category="data",
)


# ════════════════════════════════════════════════════════════
#  TRÁI PHIẾU / lãi suất điều hành
# ════════════════════════════════════════════════════════════
def _handle_get_bond_rates() -> Dict[str, Any]:
    """Lợi suất trái phiếu + lãi suất điều hành (SBV, Fed) + chênh lệch."""
    try:
        from src.services.bond_service import get_bond_overview
        d = get_bond_overview()
        return {
            "lai_suat_dieu_hanh_sbv_pct": d.get("sbv_policy_rate"),
            "fed_thap_pct": d.get("fed_low"),
            "fed_cao_pct": d.get("fed_high"),
            "loi_suat_trai_phieu_my_10nam_pct": d.get("us_yield"),
            "loi_suat_tpcp_vn_10nam_tham_khao_pct": d.get("vn10y_ref"),
            "chenh_lech_sbv_fed_diem_pct": d.get("spread_sbv_fed"),
            "chenh_lech_vn_us_diem_pct": d.get("spread_vn_us"),
            "cap_nhat": d.get("generated_at"),
            "ghi_chu": d.get("note") or "Lợi suất %/năm. VN10Y chỉ là mức tham khảo (chưa có nguồn live miễn phí).",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Tool bond] lỗi: %s", exc)
        return {"error": f"Không lấy được dữ liệu trái phiếu: {exc}"}


get_bond_rates_tool = ToolDefinition(
    name="get_bond_rates",
    description="Lấy lợi suất trái phiếu (Mỹ 10 năm, TPCP Việt Nam 10 năm tham khảo) và lãi suất điều hành "
                "(SBV, Fed). Dùng khi người dùng hỏi về TRÁI PHIẾU hoặc mặt bằng LÃI SUẤT chung.",
    parameters=[],
    handler=_handle_get_bond_rates,
    category="data",
)


# ════════════════════════════════════════════════════════════
#  XĂNG DẦU
# ════════════════════════════════════════════════════════════
def _handle_get_petrol_prices() -> Dict[str, Any]:
    """Giá xăng dầu trong nước hiện hành + dầu thế giới + kỳ điều hành kế."""
    try:
        from src.services.petrol_service import get_petrol_overview
        d = get_petrol_overview()
        fuels = [
            {"ten": f.get("name"), "gia_dong_lit": f.get("price"), "thay_doi_pct": f.get("change_pct")}
            for f in (d.get("fuels") or [])
        ]
        return {
            "ky_hieu_luc": d.get("effective_date"),
            "ky_dieu_hanh_ke": d.get("next_adjustment"),
            "cac_loai_xang_dau": fuels,
            "dau_brent_usd_thung": d.get("brent_usd"),
            "dau_wti_usd_thung": d.get("wti_usd"),
            "ghi_chu": d.get("cycle_note") or "Giá theo đồng/lít; thay_doi_pct so với kỳ điều hành trước.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Tool petrol] lỗi: %s", exc)
        return {"error": f"Không lấy được giá xăng dầu: {exc}"}


get_petrol_prices_tool = ToolDefinition(
    name="get_petrol_prices",
    description="Lấy giá xăng dầu trong nước hiện hành (RON95, E5, dầu DO...), giá dầu thế giới (Brent, WTI) "
                "và kỳ điều hành giá kế tiếp. Dùng khi người dùng hỏi về GIÁ XĂNG / DẦU.",
    parameters=[],
    handler=_handle_get_petrol_prices,
    category="data",
)


# Danh sách export — factory.get_tool_registry() sẽ gom vào registry chung.
ALL_OTHER_ASSET_TOOLS = [
    get_gold_price_tool,
    get_savings_rates_tool,
    get_bond_rates_tool,
    get_petrol_prices_tool,
]
