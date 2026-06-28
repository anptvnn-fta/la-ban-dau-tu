# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ LÃI SUẤT TIẾT KIỆM (giai đoạn B — đa tài sản)
===================================

Bảng lãi suất gửi tiết kiệm theo ngân hàng × kỳ hạn, để người gửi so sánh và
chọn nơi gửi tốt nhất.

Nguồn: API JSON CafeF
  https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/Liveboard/all_banks_interest_rates.json
  → {Data: [{name, symbol, interestRates: [{deposit(tháng), value(%/năm)}]}]}
  (28 ngân hàng, không cần auth, cập nhật theo ngày).

Lãi suất điều hành SBV (tái cấp vốn) ~4,5%/năm — giữ nguyên từ 6/2023.

Fail-open: thiếu nguồn thì trả cảnh báo.
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CAFEF_URL = "https://cafefnew.mediacdn.vn/Images/Uploaded/DuLieuDownload/Liveboard/all_banks_interest_rates.json"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Kỳ hạn hiển thị (tháng).
_TERMS = [1, 3, 6, 12, 24]
# Lãi suất tái cấp vốn của Ngân hàng Nhà nước (giữ nguyên từ 19/06/2023).
_SBV_POLICY_RATE = 4.5

_CACHE_TTL = 3600  # lãi suất đổi chậm → 1 giờ
_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "payload": None}


def _fetch_banks() -> List[Dict[str, Any]]:
    """Lấy lãi suất từ CafeF → list {name, symbol, rates: {tháng: %/năm}}."""
    try:
        import requests  # type: ignore

        r = requests.get(_CAFEF_URL, headers=_UA, timeout=20)
        data = r.json().get("Data") or []
        out = []
        for b in data:
            rates: Dict[int, float] = {}
            for ir in b.get("interestRates") or []:
                m = ir.get("deposit")
                v = ir.get("value")
                if isinstance(m, int) and isinstance(v, (int, float)) and v and v > 0.1:
                    rates[m] = float(v)
            if rates:
                out.append({
                    "name": str(b.get("name") or "").strip(),
                    "symbol": str(b.get("symbol") or "").strip(),
                    "rates": rates,
                })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Savings] lấy lãi suất CafeF thất bại: %s", exc)
        return []


def _build_overview() -> Dict[str, Any]:
    raw = _fetch_banks()
    banks: List[Dict[str, Any]] = []
    for b in raw:
        banks.append({
            "name": b["name"],
            "symbol": b["symbol"],
            # danh sách lãi suất theo đúng thứ tự _TERMS (None nếu ngân hàng không công bố).
            "rates": [b["rates"].get(t) for t in _TERMS],
        })
    # Sắp xếp theo lãi suất 12 tháng giảm dần (ngân hàng cao nhất lên đầu).
    idx12 = _TERMS.index(12)
    banks.sort(key=lambda x: (x["rates"][idx12] is None, -(x["rates"][idx12] or 0)))

    # Lãi suất tốt nhất theo từng kỳ hạn.
    best = []
    for i, t in enumerate(_TERMS):
        candidates = [(b["name"], b["rates"][i]) for b in banks if b["rates"][i] is not None]
        if candidates:
            name, rate = max(candidates, key=lambda c: c[1])
            best.append({"term": t, "bank": name, "rate": rate})

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "terms": _TERMS,
        "banks": banks,
        "best": best,
        "sbv_policy_rate": _SBV_POLICY_RATE,
        "note": (
            "Lãi suất điều hành (tái cấp vốn) của Ngân hàng Nhà nước hiện ~4,5%/năm. "
            "Lãi suất thực = lãi suất gửi − lạm phát; nên so sánh kèm CPI khi cân nhắc kênh gửi."
        ),
        "data_warning": None if banks else "Chưa lấy được bảng lãi suất tiết kiệm lúc này.",
    }


def get_savings_overview() -> Dict[str, Any]:
    """Bảng lãi suất tiết kiệm (cache 1 giờ)."""
    with _lock:
        p = _cache.get("payload")
        if p is not None and (time.time() - _cache["at"]) < _CACHE_TTL:
            return p
    payload = _build_overview()
    with _lock:
        _cache.update(at=time.time(), payload=payload)
    return payload
