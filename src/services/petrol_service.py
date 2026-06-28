# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ dữ liệu XĂNG DẦU (giai đoạn C — đa tài sản)
===================================

Giá xăng dầu bán lẻ Việt Nam do Nhà nước điều hành (7 ngày/kỳ — thứ Năm,
Nghị định 80/2023), bám giá xăng thành phẩm Singapore (MOPS) + thuế + quỹ
bình ổn, KHÁC giá dầu thô thế giới.

Nguồn:
  • Giá xăng VN (hiện tại + lịch sử từ 2018): API JSON giaxanghomnay.com/api/chart
    → list {date, a=RON95-III, b=E5 RON92, c=DO 0,05S, d=Dầu hỏa}, đơn vị nghìn đồng/lít.
  • Dầu thô thế giới: yfinance Brent (BZ=F), WTI (CL=F) — CHỈ tham chiếu xu hướng.

Mọi nguồn fail-open: thiếu phần nào thì trả phần lấy được kèm cảnh báo.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import threading
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CHART_URL = "https://giaxanghomnay.com/api/chart"          # lịch sử dài (từ 2018)
_GOCTIENICH_URL = "https://goctienich.io.vn/gia-xang-dau"   # giá hiện tại (gồm E10)
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Mặt hàng hiển thị giá hiện tại (tên trên goctienich → mã + tên hiển thị).
_GOC_DISPLAY = [
    ("Xăng E10 RON 95-III", "e10_ron95", "Xăng E10 RON 95-III"),
    ("Xăng E5 RON 92-II", "e5", "Xăng E5 RON 92-II"),
    ("Dầu DO 0,05S-II", "do", "Dầu DO 0,05S-II"),
    ("Dầu hỏa 2-K", "dau_hoa", "Dầu hỏa 2-K"),
]

# Ánh xạ field → mã + tên hiển thị (đơn vị: đồng/lít).
_FUELS = [
    {"field": "a", "code": "ron95", "name": "Xăng RON 95-III"},
    {"field": "b", "code": "e5", "name": "Xăng E5 RON 92-II"},
    {"field": "c", "code": "do", "name": "Dầu DO 0,05S-II"},
    {"field": "d", "code": "dau_hoa", "name": "Dầu hỏa 2-K"},
]

_OVERVIEW_TTL = 1800        # giá đổi theo kỳ (~tuần) → 30 phút là đủ
_HISTORY_TTL = 6 * 3600
_ov_lock = threading.Lock()
_ov_cache: Dict[str, Any] = {"at": 0.0, "payload": None}
_hist_lock = threading.Lock()
_hist_cache: Dict[str, Any] = {"at": 0.0, "payload": None, "key": None}


def _to_dong(v: Any) -> Optional[float]:
    """Nghìn đồng/lít → đồng/lít. 0/None coi là thiếu."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0 or f != f:  # 0 hoặc NaN = thiếu (vd RON95-III ngừng niêm yết)
        return None
    return f * 1000.0


def _fetch_chart() -> List[Dict[str, Any]]:
    """Lấy chuỗi giá xăng VN từ giaxanghomnay (đã đổi sang đồng/lít)."""
    try:
        import requests  # type: ignore

        r = requests.get(_CHART_URL, headers=_UA, timeout=20)
        raw = r.json()
        out = []
        for row in raw:
            out.append({
                "date": str(row.get("date") or ""),
                "ron95": _to_dong(row.get("a")),
                "e5": _to_dong(row.get("b")),
                "do": _to_dong(row.get("c")),
                "dau_hoa": _to_dong(row.get("d")),
            })
        out = [r for r in out if r["date"]]
        out.sort(key=lambda r: r["date"])
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Petrol] lấy chuỗi giá xăng thất bại: %s", exc)
        return []


def _fetch_goctienich_board() -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """Giá xăng dầu HIỆN TẠI (gồm E10) từ goctienich. Trả ({tên: {price,change,change_pct}}, updatedAt)."""
    try:
        import requests  # type: ignore

        txt = requests.get(_GOCTIENICH_URL, headers=_UA, timeout=20).text.replace('\\"', '"')
        out: Dict[str, Dict[str, Any]] = {}
        # Mỗi mặt hàng: {"name":"...","price":NNNN,"trend":"...","history":[...]}
        for m in re.finditer(r'"name":"([^"]+)","price":(\d{3,7}),"trend":"\w+","history":\[([\d,]+)\]', txt):
            name = m.group(1)
            price = float(m.group(2))
            hist = [int(x) for x in m.group(3).split(",") if x.strip()]
            # thay đổi = giá hiện tại - giá trị khác gần nhất (kỳ trước)
            prev = None
            scan = hist[:-1] if (hist and hist[-1] == price) else hist
            for v in reversed(scan):
                if v != price:
                    prev = float(v)
                    break
            change = (price - prev) if prev is not None else None
            change_pct = round(change / prev * 100, 2) if (change is not None and prev) else None
            out[name] = {"price": price, "change": change, "change_pct": change_pct}
        mu = re.search(r'"updatedAt":"([^"]+)"', txt)
        return out, (mu.group(1) if mu else None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Petrol] goctienich (giá hiện tại) thất bại: %s", exc)
        return {}, None


def _world_oil() -> Dict[str, Optional[float]]:
    """Giá dầu thô thế giới hiện tại (USD/thùng): Brent + WTI."""
    out: Dict[str, Optional[float]] = {"brent": None, "wti": None}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore
        for key, sym in (("brent", "BZ=F"), ("wti", "CL=F")):
            try:
                h = yf.Ticker(sym).history(period="5d")
                if h is not None and not h.empty:
                    out[key] = round(float(h["Close"].dropna().iloc[-1]), 2)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Petrol] giá dầu thế giới thất bại: %s", exc)
    return out


def _brent_series(days: int) -> Dict[str, float]:
    """Chuỗi Brent USD/thùng theo ngày. date_iso → giá."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore
        period = "5y" if days > 730 else "2y" if days > 365 else "1y"
        h = yf.Ticker("BZ=F").history(period=period)
        out: Dict[str, float] = {}
        if h is not None and not h.empty:
            for idx, val in h["Close"].dropna().items():
                out[idx.date().isoformat()] = round(float(val), 2)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Petrol] chuỗi Brent thất bại: %s", exc)
        return {}


def _nearest(series: Dict[str, float], date_iso: str) -> Optional[float]:
    if not series:
        return None
    keys = sorted(series.keys())
    le = [k for k in keys if k <= date_iso]
    return series.get(le[-1] if le else keys[0])


def _next_adjustment(today: _dt.date) -> str:
    """Kỳ điều hành kế tiếp (thứ Năm hàng tuần — Nghị định 80/2023)."""
    ahead = (3 - today.weekday()) % 7  # thứ Năm = 3
    if ahead == 0:
        ahead = 7
    return (today + _dt.timedelta(days=ahead)).isoformat()


def _prev_changed(series: List[Dict[str, Any]], code: str, current: Optional[float]) -> Optional[float]:
    """Giá kỳ TRƯỚC (giá trị khác current gần nhất khi đi ngược chuỗi)."""
    if current is None:
        return None
    for row in reversed(series[:-1]):
        v = row.get(code)
        if v is not None and v != current:
            return v
    return None


def _build_overview() -> Dict[str, Any]:
    oil = _world_oil()
    warnings_list = []
    fuels: List[Dict[str, Any]] = []
    effective_date = None

    # Nguồn CHÍNH: goctienich (có E10 RON95 + giá tươi + thay đổi).
    board, updated = _fetch_goctienich_board()
    if board:
        if updated:
            m = re.search(r'(\d{2})/(\d{2})/(\d{4})', updated)
            if m:
                effective_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        for goc_name, code, disp in _GOC_DISPLAY:
            row = board.get(goc_name)
            if row:
                fuels.append({
                    "code": code, "name": disp, "price": row["price"],
                    "prev_price": None, "change": row["change"], "change_pct": row["change_pct"],
                })

    # DỰ PHÒNG: giaxanghomnay (nếu goctienich lỗi). Không có E10.
    if not fuels:
        series = _fetch_chart()
        if series:
            latest = series[-1]
            effective_date = latest["date"]
            for f in _FUELS:
                cur = latest.get(f["code"])
                prev = _prev_changed(series, f["code"], cur)
                change = (cur - prev) if (cur is not None and prev is not None) else None
                change_pct = round(change / prev * 100, 2) if (change is not None and prev) else None
                fuels.append({
                    "code": f["code"], "name": f["name"],
                    "price": cur, "prev_price": prev,
                    "change": change, "change_pct": change_pct,
                })
        else:
            warnings_list.append("Chưa lấy được giá xăng dầu trong nước.")

    if oil.get("brent") is None and oil.get("wti") is None:
        warnings_list.append("Chưa lấy được giá dầu thế giới.")

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "effective_date": effective_date,
        "next_adjustment": _next_adjustment(_dt.date.today()),
        "fuels": fuels,
        "brent_usd": oil.get("brent"),
        "wti_usd": oil.get("wti"),
        "cycle_note": (
            "Giá bán lẻ do Liên Bộ Công Thương – Tài Chính điều hành 7 ngày/kỳ (thứ Năm, "
            "Nghị định 80/2023), bám giá xăng thành phẩm Singapore (MOPS) cộng thuế, phí và "
            "quỹ bình ổn — nên không bám sát giá dầu thô Brent/WTI."
        ),
        "data_warning": " ".join(warnings_list) if warnings_list else None,
    }


def get_petrol_overview() -> Dict[str, Any]:
    """Tổng quan xăng dầu (cache 30 phút)."""
    with _ov_lock:
        p = _ov_cache.get("payload")
        if p is not None and (time.time() - _ov_cache["at"]) < _OVERVIEW_TTL:
            return p
    payload = _build_overview()
    with _ov_lock:
        _ov_cache.update(at=time.time(), payload=payload)
    return payload


def get_petrol_history(days: int = 365) -> Dict[str, Any]:
    """Lịch sử giá xăng VN (E5, RON95, DO) + Brent quy chiếu. Cache 6 giờ."""
    days = max(90, min(int(days), 3000))
    key = str(days)
    with _hist_lock:
        p = _hist_cache.get("payload")
        if p is not None and _hist_cache.get("key") == key and (time.time() - _hist_cache["at"]) < _HISTORY_TTL:
            return p

    series = _fetch_chart()
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    series = [r for r in series if r["date"] >= cutoff]
    brent = _brent_series(days)

    points = []
    for r in series:
        points.append({
            "date": r["date"],
            "e5": r.get("e5"),
            "ron95": r.get("ron95"),
            "do": r.get("do"),
            "brent": _nearest(brent, r["date"]),
        })

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "days": days,
        "points": points,
        "data_warning": None if points else "Chưa lấy được lịch sử giá xăng dầu lúc này.",
    }
    with _hist_lock:
        _hist_cache.update(at=time.time(), payload=payload, key=key)
    return payload
