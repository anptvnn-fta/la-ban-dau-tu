# -*- coding: utf-8 -*-
"""
===================================
AI phân tích CHÂN DUNG khách hàng (Tư vấn đầu tư)
===================================

Vai trò AI = DIỄN GIẢI, không quyết định con số. Mọi tỷ trọng/điểm số do
tu_van_service tính theo luật; AI chỉ viết 4 đoạn văn:
  [CHAN_DUNG]      — mô tả chân dung nhà đầu tư
  [LY_DO_NHOM]     — vì sao xếp vào nhóm này
  [DIEN_GIAI_KENH] — vì sao phân bổ từng kênh phù hợp (dẫn số liệu live)
  [LUU_Y]          — lưu ý + bước tiếp theo (kèm cảnh báo bắt buộc)

Fail-open: AI lỗi/timeout → trả văn bản mẫu theo nhóm (vẫn có cảnh báo bắt buộc).
KHÔNG đưa số tuyệt đối PII vào prompt — chỉ đưa nhãn (vd "20 – 50 triệu đồng").
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SECTIONS = ["chan_dung", "ly_do_nhom", "dien_giai_kenh", "luu_y"]
_TAGS = {
    "chan_dung": "CHAN_DUNG",
    "ly_do_nhom": "LY_DO_NHOM",
    "dien_giai_kenh": "DIEN_GIAI_KENH",
    "luu_y": "LUU_Y",
}


def _mandatory_warnings(profile_raw: Dict[str, Any], market: Optional[Dict[str, Any]]) -> List[str]:
    """Cảnh báo BẮT BUỘC theo hồ sơ. So theo KEY GỐC (bền vững khi nhãn đổi)."""
    w: List[str] = []
    if (profile_raw or {}).get("quy_du_phong") == "chua_co":
        w.append("Bạn chưa có quỹ dự phòng khẩn cấp — hãy ưu tiên tích lũy 3–6 tháng chi tiêu trước khi đầu tư mạnh.")
    if (profile_raw or {}).get("ganh_no") == "the_tin_dung":
        w.append("Bạn đang có nợ lãi cao (thẻ tín dụng) — nên ưu tiên trả hết nợ này trước khi đầu tư cổ phiếu.")
    try:
        prem = (market or {}).get("vang", {}) if market else {}
        pp = prem.get("premium_pct") if isinstance(prem, dict) else None
        if pp is not None and pp > 15:
            w.append(f"Giá vàng SJC đang cao hơn thế giới khoảng {pp}% — cân nhắc rủi ro mua ở vùng chênh lệch cao.")
    except Exception:  # noqa: BLE001
        pass
    return w


def _build_ai_input(profile_labels: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Gộp input cho AI: nhãn hồ sơ + kết quả số (đọc-chỉ) + dữ liệu live."""
    alloc = {a["asset_class"]: a["percent"] for a in result.get("allocation", [])}
    market = result.get("market_data") or {}
    return {
        "ho_so": profile_labels,
        "tuoi": result.get("age"),
        "ket_qua_do_luat_tinh": {
            "nhom_kha_nang": result["capacity"]["label"],
            "nhom_khau_vi_chuong4": result["tolerance"]["label"],
            "luat_dac_biet_kich_hoat": result["forced_defensive"],
            "nhom_cuoi_cung": result["final_label"],
            "nghieng_thoi_gian": result["time_tilt"],
        },
        "phan_bo_pct": alloc,
        "chia_co_phieu": {s["bucket"]: s["within_stock_pct"] for s in result.get("stock_split", [])},
        "du_lieu_live": market,
    }


_SYSTEM_PROMPT = (
    "Bạn là chuyên gia tư vấn tài chính cá nhân tại Việt Nam, giúp khách hàng hiểu rõ hồ sơ đầu tư "
    "và kế hoạch phù hợp. Nguyên tắc BẮT BUỘC:\n"
    "- Viết bằng tiếng Việt dễ hiểu, xưng hô \"bạn\", KHÔNG chèn thuật ngữ tiếng Anh.\n"
    "- KHÔNG bịa hay thay đổi bất kỳ con số tỷ trọng/điểm nào. Mọi số đã được hệ thống tính sẵn — bạn chỉ diễn giải.\n"
    "- Giọng thân thiện, gần gũi như chuyên gia ngồi cạnh tư vấn.\n"
    "- Tuân thủ độ dài từng phần, không lan man.\n"
    "- BẮT ĐẦU phản hồi NGAY bằng nhãn [CHAN_DUNG], TUYỆT ĐỐI không viết câu chào hay lời mở đầu nào trước đó."
)


def _user_prompt(ai_input: Dict[str, Any], warnings: List[str]) -> str:
    forced = ai_input["ket_qua_do_luat_tinh"]["luat_dac_biet_kich_hoat"]
    nhom = ai_input["ket_qua_do_luat_tinh"]["nhom_cuoi_cung"]
    extra_force = " Nêu rõ rằng vì khách chọn mức chịu lỗ dưới 5% nên hệ thống tự xếp nhóm Thận trọng để bảo vệ vốn." if forced else ""
    warn_txt = ""
    if warnings:
        warn_txt = "\n\nCÁC CẢNH BÁO BẮT BUỘC phải đưa vào phần [LUU_Y] (diễn đạt lại tự nhiên):\n- " + "\n- ".join(warnings)
    return (
        "Dưới đây là hồ sơ và kết quả phân tích do hệ thống tính toán (JSON):\n\n"
        + json.dumps(ai_input, ensure_ascii=False, indent=2)
        + warn_txt
        + "\n\nHãy viết đúng 4 đoạn theo thứ tự, mỗi đoạn bắt đầu bằng nhãn trong ngoặc vuông:\n\n"
        + "[CHAN_DUNG] Mô tả chân dung nhà đầu tư này (100–150 chữ). Không nêu điểm số. Nếu thấy mâu thuẫn (vd kỳ vọng lợi nhuận cao nhưng không chịu được sụt giảm) thì chỉ ra nhẹ nhàng.\n\n"
        + f"[LY_DO_NHOM] Giải thích vì sao được xếp vào nhóm \"{nhom}\" (80–120 chữ), so sánh Khả năng và Khẩu vị nếu khác nhau.{extra_force}\n\n"
        + "[DIEN_GIAI_KENH] Giải thích vì sao phân bổ từng kênh (tiết kiệm/trái phiếu/cổ phiếu/vàng) phù hợp với hồ sơ cụ thể này (150–250 chữ). Dẫn số liệu live trong du_lieu_live (lãi suất tiết kiệm, giá vàng...). KHÔNG bịa hay đổi số tỷ trọng.\n\n"
        + "[LUU_Y] Lưu ý và bước tiếp theo thực tế (60–120 chữ). Bắt buộc lồng đủ các cảnh báo nêu trên nếu có."
    )


def _parse_sections(text: str) -> Dict[str, str]:
    """Tách 4 đoạn theo nhãn [TAG]. Phần nào thiếu → chuỗi rỗng."""
    out = {k: "" for k in _SECTIONS}
    # vị trí từng nhãn
    positions = []
    for key, tag in _TAGS.items():
        m = re.search(r"\[" + tag + r"\]", text)
        if m:
            positions.append((m.start(), m.end(), key))
    positions.sort()
    for i, (_, end, key) in enumerate(positions):
        nxt = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[key] = text[end:nxt].strip()
    return out


def _fallback_text(result: Dict[str, Any], warnings: List[str]) -> Dict[str, str]:
    """Văn bản mẫu khi AI lỗi/timeout — vẫn đầy đủ ý + cảnh báo."""
    nhom = result["final_label"]
    cap = result["capacity"]["label"]
    tol = result["tolerance"]["label"]
    alloc = {a["asset_class"]: a["percent"] for a in result.get("allocation", [])}
    forced = result["forced_defensive"]
    chan = (f"Dựa trên hồ sơ bạn cung cấp, bạn thuộc nhóm nhà đầu tư {nhom}. "
            f"Khả năng tài chính của bạn ở mức {cap}, còn khẩu vị rủi ro ở mức {tol}. "
            "Đây là bức tranh tổng quan giúp bạn chọn kênh đầu tư phù hợp với hoàn cảnh thực tế.")
    ly_do = (f"Theo nguyên tắc thận trọng, hệ thống lấy mức thấp hơn giữa khả năng tài chính và khẩu vị rủi ro để xếp bạn vào nhóm {nhom}, "
             "nhằm tránh để bạn chịu rủi ro vượt quá sức của mình.")
    if forced:
        ly_do += " Vì bạn chọn mức chịu lỗ dưới 5%, hệ thống ưu tiên bảo toàn vốn tối đa."
    dien_giai = (f"Phân bổ gợi ý: Tiết kiệm {alloc.get('tiet_kiem',0)}%, Trái phiếu {alloc.get('trai_phieu',0)}%, "
                 f"Cổ phiếu {alloc.get('co_phieu',0)}%, Vàng {alloc.get('vang',0)}%. "
                 "Tỷ trọng này cân đối giữa an toàn (tiết kiệm, trái phiếu), tăng trưởng (cổ phiếu) và phòng thủ (vàng) theo đúng nhóm của bạn.")
    luu_y = " ".join(warnings) if warnings else "Hãy rà soát lại quỹ dự phòng và đa dạng hóa trước khi xuống tiền; xem lại danh mục định kỳ."
    return {"chan_dung": chan, "ly_do_nhom": ly_do, "dien_giai_kenh": dien_giai, "luu_y": luu_y}


def analyze(profile_labels: Dict[str, Any], result: Dict[str, Any],
            profile_raw: Optional[Dict[str, Any]] = None, *, timeout: int = 25) -> Dict[str, Any]:
    """Gọi AI diễn giải hồ sơ. Trả {sections, source, warnings}. Fail-open về template.

    profile_raw: hồ sơ key gốc để tính cảnh báo bắt buộc (bền vững hơn so theo nhãn).
    """
    warnings = _mandatory_warnings(profile_raw if profile_raw is not None else {}, result.get("market_data"))
    ai_input = _build_ai_input(profile_labels, result)

    try:
        import litellm  # type: ignore
        from src.config import get_config
        cfg = get_config()
        model = getattr(cfg, "litellm_model", None) or "gemini/gemini-2.5-flash"
        if model.startswith(("gemini/", "vertex_ai/")):
            keys = [k for k in getattr(cfg, "gemini_api_keys", []) if k]
        elif model.startswith("anthropic/"):
            keys = [k for k in getattr(cfg, "anthropic_api_keys", []) if k]
        else:
            keys = [k for k in getattr(cfg, "openai_api_keys", []) if k]

        kwargs: Dict[str, Any] = {
            "model": model,
            # gemini-2.5-flash tiêu RẤT NHIỀU "thinking tokens" ẩn TRƯỚC khi xuất nội dung;
            # phải để max_tokens thật lớn nếu không 4 đoạn sẽ bị cắt (finish_reason=length).
            "max_tokens": 6000,
            "temperature": 0.4,
            "timeout": timeout,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(ai_input, warnings)},
            ],
        }
        if keys:
            kwargs["api_key"] = keys[0]
        if not model.startswith(("gemini/", "anthropic/", "vertex_ai/")) and getattr(cfg, "openai_base_url", None):
            kwargs["api_base"] = cfg.openai_base_url

        resp = litellm.completion(**kwargs)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        # Quan sát: nếu bị cắt do hết token (thinking ăn hết) thì ghi log để dễ chỉnh.
        finish = getattr(choice, "finish_reason", None)
        if finish == "length":
            logger.warning("[TuVanAI] phản hồi bị cắt (finish_reason=length, len=%d) — cân nhắc tăng max_tokens.", len(text))
        sections = _parse_sections(text)
        # Nếu trống hết (parse fail) → fallback.
        if not any(sections.values()):
            return {"sections": _fallback_text(result, warnings), "source": "fallback", "warnings": warnings}
        # Vá phần nào trống bằng template để UI không bị khoảng trắng.
        fb = _fallback_text(result, warnings)
        for k in _SECTIONS:
            if not sections.get(k):
                sections[k] = fb[k]
        return {"sections": sections, "source": "ai", "warnings": warnings}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TuVanAI] AI lỗi, dùng văn bản mẫu: %s", exc)
        return {"sections": _fallback_text(result, warnings), "source": "fallback", "warnings": warnings}
