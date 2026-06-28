# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ TRÁI PHIẾU & LÃI SUẤT ĐIỀU HÀNH (giai đoạn B — đa tài sản)
===================================

So sánh mặt bằng lãi suất: lãi suất điều hành SBV vs Fed, lợi suất trái phiếu
Mỹ 10 năm (US10Y) live + lịch sử. Lợi suất trái phiếu chính phủ VN (VN10Y) chỉ
ghi mức THAM KHẢO vì không có nguồn miễn phí đáng tin cho dữ liệu live.

Nguồn:
  • US10Y: yfinance ticker ^TNX (Close = lợi suất %/năm, đã hiển thị trực tiếp).
  • SBV / Fed / VN10Y: hằng số tài liệu (đổi chậm), kèm ghi chú.

Fail-open: thiếu US10Y thì vẫn trả phần hằng số kèm cảnh báo.
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
import time
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Hằng số tài liệu (cập nhật thủ công khi chính sách đổi — hiếm).
_SBV_POLICY_RATE = 4.5          # lãi suất tái cấp vốn SBV, từ 19/06/2023
_FED_LOW, _FED_HIGH = 3.5, 3.75  # khung mục tiêu Fed, FOMC 06/2026
_VN10Y_REF = 4.5               # lợi suất TPCP VN 10 năm — THAM KHẢO (không live)

_OV_TTL = 1800
_HIST_TTL = 6 * 3600
_ov_lock = threading.Lock()
_ov_cache: Dict[str, Any] = {"at": 0.0, "payload": None}
_hist_lock = threading.Lock()
_hist_cache: Dict[str, Any] = {"at": 0.0, "payload": None, "key": None}


def _tnx_series(period: str) -> Dict[str, float]:
    """Chuỗi US10Y (^TNX) theo ngày. date_iso → lợi suất %/năm."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore
        h = yf.Ticker("^TNX").history(period=period)
        out: Dict[str, float] = {}
        if h is not None and not h.empty:
            for idx, val in h["Close"].dropna().items():
                out[idx.date().isoformat()] = round(float(val), 3)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Bond] US10Y (^TNX) thất bại: %s", exc)
        return {}


def _us10y_current() -> Optional[float]:
    s = _tnx_series("5d")
    if not s:
        return None
    return s[sorted(s.keys())[-1]]


def _build_overview() -> Dict[str, Any]:
    us10y = _us10y_current()
    fed_mid = round((_FED_LOW + _FED_HIGH) / 2, 3)
    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "sbv_policy_rate": _SBV_POLICY_RATE,
        "fed_low": _FED_LOW,
        "fed_high": _FED_HIGH,
        "us_yield": us10y,
        "vn10y_ref": _VN10Y_REF,
        "spread_sbv_fed": round(_SBV_POLICY_RATE - fed_mid, 2),
        "spread_vn_us": round(_VN10Y_REF - us10y, 2) if us10y else None,
        "note": (
            "Lãi suất điều hành (tái cấp vốn) của Ngân hàng Nhà nước ~4,5%/năm, cao hơn "
            "khung của Fed (~0,9 điểm %) — phản ánh phân kỳ chính sách. VN10Y ghi ở đây là "
            "mức THAM KHẢO (~4,5%): hiện không có nguồn miễn phí đáng tin cho lợi suất TPCP VN "
            "theo thời gian thực. US10Y lấy trực tiếp từ thị trường (yfinance)."
        ),
        "data_warning": None if us10y else "Chưa lấy được lợi suất trái phiếu Mỹ lúc này.",
    }


def get_bond_overview() -> Dict[str, Any]:
    """Tổng quan lãi suất & trái phiếu (cache 30 phút)."""
    with _ov_lock:
        p = _ov_cache.get("payload")
        if p is not None and (time.time() - _ov_cache["at"]) < _OV_TTL:
            return p
    payload = _build_overview()
    with _ov_lock:
        _ov_cache.update(at=time.time(), payload=payload)
    return payload


def get_bond_history(days: int = 365) -> Dict[str, Any]:
    """Lịch sử US10Y (^TNX). Cache 6 giờ."""
    days = max(90, min(int(days), 1825))
    key = str(days)
    with _hist_lock:
        p = _hist_cache.get("payload")
        if p is not None and _hist_cache.get("key") == key and (time.time() - _hist_cache["at"]) < _HIST_TTL:
            return p

    period = "5y" if days > 730 else "2y" if days > 365 else "1y"
    series = _tnx_series(period)
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    points = [{"date": d, "us_yield": series[d]} for d in sorted(series) if d >= cutoff]

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "days": days,
        "points": points,
        "data_warning": None if points else "Chưa lấy được lịch sử lợi suất lúc này.",
    }
    with _hist_lock:
        _hist_cache.update(at=time.time(), payload=payload, key=key)
    return payload
