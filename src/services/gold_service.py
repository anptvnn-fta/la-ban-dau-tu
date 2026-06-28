# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ dữ liệu VÀNG (Phase A — đa tài sản)
===================================

Tổng hợp một bức tranh giá vàng cho trang "Vàng":
  • Giá vàng miếng SJC trong nước (VND/lượng) qua vnstock.
  • Giá vàng thế giới (USD/oz) qua yfinance (GC=F), dự phòng BTMC.
  • Tỷ giá USD/VND (bán) của Vietcombank.
  • CHÊNH LỆCH (premium) SJC so với giá thế giới quy đổi.

Phép quy đổi quan trọng: giá thế giới yết theo **troy ounce** (31,1035 g),
giá trong nước yết theo **lượng** (37,5 g). 1 lượng = 1,20565 troy oz.
  giá_TG_quy_đổi (VND/lượng) = giá_USD_oz × 1,20565 × tỷ_giá_USDVND
  premium = giá_SJC_bán − giá_TG_quy_đổi

Mọi nguồn đều fail-open: thiếu phần nào thì trả phần lấy được kèm cảnh báo.
"""

from __future__ import annotations

import datetime as _dt
import logging
import threading
import time
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 1 lượng (37,5 g) / 1 troy oz (31,1034768 g)
OZ_PER_LUONG = 1.20565

# Vàng đổi giá vài lần/ngày → cache 5 phút là đủ.
_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_build_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "payload": None}


def _safe_float(v: Any) -> Optional[float]:
    try:
        f = float(str(v).replace(",", "").strip())
        return f if f == f else None  # loại NaN
    except Exception:
        return None


def _fetch_sjc() -> Optional[Dict[str, Any]]:
    """Giá vàng miếng SJC (ưu tiên chi nhánh Hồ Chí Minh). VND/lượng."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.explorer.misc.gold_price import sjc_gold_price  # type: ignore

        df = sjc_gold_price()
        if df is None or getattr(df, "empty", True):
            return None
        hcm = df[df["branch"].astype(str).str.contains("Hồ Chí Minh", na=False)]
        row = hcm.iloc[0] if len(hcm) else df.iloc[0]
        buy = _safe_float(row.get("buy_price"))
        sell = _safe_float(row.get("sell_price"))
        if buy is None and sell is None:
            return None
        return {
            "name": str(row.get("name") or "Vàng SJC"),
            "branch": str(row.get("branch") or ""),
            "buy": buy,
            "sell": sell,
            "date": str(row.get("date") or ""),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] lấy giá SJC thất bại: %s", exc)
        return None


def _fetch_world_usd_oz() -> Optional[Dict[str, Any]]:
    """Giá vàng thế giới USD/oz. Ưu tiên yfinance GC=F, dự phòng BTMC."""
    # yfinance (chuẩn quốc tế)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore

        hist = yf.Ticker("GC=F").history(period="5d")
        if hist is not None and not hist.empty:
            price = _safe_float(hist["Close"].dropna().iloc[-1])
            if price:
                return {"price": price, "source": "yfinance (GC=F)"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] yfinance GC=F thất bại, thử BTMC: %s", exc)

    # Dự phòng: cột world_price của BTMC
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.explorer.misc.gold_price import btmc_goldprice  # type: ignore
            import pandas as pd  # type: ignore

        df = btmc_goldprice()
        wp = pd.to_numeric(df["world_price"], errors="coerce").dropna()
        if len(wp):
            return {"price": float(wp.iloc[0]), "source": "BTMC"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] BTMC world_price thất bại: %s", exc)
    return None


def _fetch_usd_vnd() -> Optional[float]:
    """Tỷ giá USD/VND (giá bán Vietcombank)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.explorer.misc.exchange_rate import vcb_exchange_rate  # type: ignore

        df = vcb_exchange_rate(date=_dt.date.today().isoformat())
        if df is None or getattr(df, "empty", True):
            return None
        usd = df[df["currency_code"].astype(str).str.upper() == "USD"]
        if not len(usd):
            return None
        return _safe_float(usd.iloc[0].get("sell"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] tỷ giá VCB thất bại: %s", exc)
        return None


# ════════════════════════════════════════════════════════════
#  Bảng các loại vàng (BTMC) — giá theo "chỉ", quy đổi ×10 ra "lượng"
# ════════════════════════════════════════════════════════════
_CHI_PER_LUONG = 10  # 1 lượng = 10 chỉ

_types_lock = threading.Lock()
_types_cache: Dict[str, Any] = {"at": 0.0, "payload": None}


def _fetch_gold_types() -> list:
    """Các loại vàng trong nước từ BTMC (lấy bản ghi mới nhất theo từng loại)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.explorer.misc.gold_price import btmc_goldprice  # type: ignore
            import pandas as pd  # type: ignore

        df = btmc_goldprice()
        df = df.copy()
        df["ts"] = pd.to_datetime(df["time"], format="%d/%m/%Y %H:%M", errors="coerce")
        gold = df[df["name"].astype(str).str.upper().str.startswith("VÀNG")]
        if gold.empty:
            return []
        latest = gold.sort_values("ts").groupby("name", as_index=False).last()
        out = []
        for _, r in latest.iterrows():
            buy = _safe_float(r.get("buy_price"))
            sell = _safe_float(r.get("sell_price"))
            out.append({
                # Rút gọn: bỏ phần mô tả trong ngoặc cho tên gọn (vd "VÀNG MIẾNG SJC").
                "name": str(r.get("name") or "").split("(")[0].strip(),
                "karat": str(r.get("karat") or "").strip(),
                # BTMC yết theo chỉ → quy đổi sang lượng cho đồng nhất với SJC.
                "buy": buy * _CHI_PER_LUONG if buy else None,
                "sell": sell * _CHI_PER_LUONG if sell else None,
            })
        out.sort(key=lambda x: (x["sell"] is None, -(x["sell"] or 0)))
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] lấy bảng loại vàng (BTMC) thất bại: %s", exc)
        return []


def get_gold_types() -> list:
    """Bảng loại vàng trong nước (cache 5 phút)."""
    with _types_lock:
        p = _types_cache.get("payload")
        if p is not None and (time.time() - _types_cache["at"]) < _CACHE_TTL_SECONDS:
            return p
    data = _fetch_gold_types()
    with _types_lock:
        _types_cache.update(at=time.time(), payload=data)
    return data


# ════════════════════════════════════════════════════════════
#  Lịch sử giá vàng trong nước (scrape giavangonline) + thế giới (yfinance)
# ════════════════════════════════════════════════════════════
_HISTORY_TTL_SECONDS = 6 * 3600
_history_lock = threading.Lock()
_history_cache: Dict[str, Any] = {"at": 0.0, "payload": None, "key": None}
_GIAVANG_URL = "https://giavangonline.com/goldhistory.php"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
import re as _re  # noqa: E402


def _scrape_sjc_on(date_iso: str) -> Optional[float]:
    """Giá BÁN SJC 1L (VND/lượng) tại một ngày, từ giavangonline. Fail → None."""
    try:
        import requests  # type: ignore
        from bs4 import BeautifulSoup  # type: ignore

        r = requests.get(_GIAVANG_URL, params={"date": date_iso}, headers=_UA, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for tb in soup.find_all("table"):
            if "SJC 1L" not in tb.get_text():
                continue
            for tr in tb.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all("td")]
                if cells and "SJC 1L" in cells[0] and len(cells) >= 2:
                    nums = _re.findall(r"[\d,]+", cells[1])
                    if len(nums) >= 2:
                        # cột "mua / bán" theo CHỈ → lấy bán, ×10 ra lượng
                        sell_chi = int(nums[1].replace(",", ""))
                        return float(sell_chi * _CHI_PER_LUONG)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] scrape SJC %s thất bại: %s", date_iso, exc)
        return None


def _world_usd_series(days: int) -> Dict[str, float]:
    """Chuỗi giá vàng thế giới USD/oz theo ngày (yfinance GC=F). date_iso → giá."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore

        period = "1y" if days > 180 else "6mo"
        hist = yf.Ticker("GC=F").history(period=period)
        out: Dict[str, float] = {}
        if hist is not None and not hist.empty:
            for idx, val in hist["Close"].dropna().items():
                out[idx.date().isoformat()] = float(val)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] chuỗi vàng thế giới thất bại: %s", exc)
        return {}


def _usdvnd_series(days: int) -> Dict[str, float]:
    """Chuỗi tỷ giá USD/VND theo ngày (yfinance USDVND=X). date_iso → giá."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf  # type: ignore

        period = "1y" if days > 180 else "6mo"
        hist = yf.Ticker("USDVND=X").history(period=period)
        out: Dict[str, float] = {}
        if hist is not None and not hist.empty:
            for idx, val in hist["Close"].dropna().items():
                out[idx.date().isoformat()] = float(val)
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Gold] chuỗi tỷ giá USD/VND thất bại: %s", exc)
        return {}


def _nearest(series: Dict[str, float], date_iso: str) -> Optional[float]:
    """Giá gần ngày date_iso nhất (ưu tiên ≤ ngày đó)."""
    if not series:
        return None
    keys = sorted(series.keys())
    le = [k for k in keys if k <= date_iso]
    pick = le[-1] if le else keys[0]
    return series.get(pick)


# Giữ tên cũ để tương thích.
_nearest_world = _nearest


def get_gold_history(days: int = 180, step_days: int = 14) -> Dict[str, Any]:
    """Lịch sử giá vàng trong nước (SJC) + thế giới quy đổi (VND/lượng).

    Cache 6 giờ. Trục thời gian sinh đều mỗi step_days; mỗi mốc lấy SJC (scrape)
    và vàng thế giới (yfinance). Quy đổi thế giới dùng tỷ giá USD/VND HIỆN TẠI
    (xấp xỉ — FX biến động chậm hơn nhiều so với vàng).
    """
    days = max(30, min(int(days), 365))
    step_days = max(7, min(int(step_days), 30))
    key = f"{days}:{step_days}"

    with _history_lock:
        p = _history_cache.get("payload")
        if p is not None and _history_cache.get("key") == key and (time.time() - _history_cache["at"]) < _HISTORY_TTL_SECONDS:
            return p

    today = _dt.date.today()
    n = days // step_days
    dates = [(today - _dt.timedelta(days=step_days * i)) for i in range(n, -1, -1)]

    world = _world_usd_series(days)
    fx_series = _usdvnd_series(days)       # tỷ giá theo ngày (chính xác hơn cho quá khứ)
    usd_vnd_now = _fetch_usd_vnd() or 26000.0  # tỷ giá hiện tại (dự phòng cho ngày thiếu)

    points = []
    prem_pcts = []
    for d in dates:
        diso = d.isoformat()
        sjc = _scrape_sjc_on(diso)
        wp = _nearest(world, diso)
        fx = _nearest(fx_series, diso) or usd_vnd_now  # tỷ giá đúng ngày, thiếu thì dùng hiện tại
        world_luong = wp * OZ_PER_LUONG * fx if (wp and fx) else None
        if sjc is None and world_luong is None:
            continue
        prem_pct = None
        if sjc and world_luong:
            prem_pct = round((sjc - world_luong) / world_luong * 100, 2)
            prem_pcts.append(prem_pct)
        points.append({
            "date": diso,
            "sjc": round(sjc) if sjc else None,
            "world": round(world_luong) if world_luong else None,
            "premium_pct": prem_pct,
        })

    # Dải chênh lệch trong kỳ → để nhận định "cao/thấp so với trung bình".
    prem_avg = round(sum(prem_pcts) / len(prem_pcts), 2) if prem_pcts else None
    prem_min = round(min(prem_pcts), 2) if prem_pcts else None
    prem_max = round(max(prem_pcts), 2) if prem_pcts else None
    prem_cur = prem_pcts[-1] if prem_pcts else None

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "days": days,
        "usd_vnd": usd_vnd_now,
        "points": points,
        "premium_current_pct": prem_cur,
        "premium_avg_pct": prem_avg,
        "premium_min_pct": prem_min,
        "premium_max_pct": prem_max,
        "data_warning": None if points else "Chưa lấy được lịch sử giá vàng lúc này.",
    }
    with _history_lock:
        _history_cache.update(at=time.time(), payload=payload, key=key)
    return payload


def _assess_premium(pct: Optional[float]) -> Optional[str]:
    """Nhận định nhanh mức chênh lệch (chưa có dải lịch sử → phân ngưỡng tĩnh)."""
    if pct is None:
        return None
    if pct < 5:
        return "Chênh lệch THẤP so với giá thế giới — tương đối hợp lý."
    if pct < 10:
        return "Chênh lệch TRUNG BÌNH — mức phổ biến nhiều năm qua."
    return ("Chênh lệch CAO — giá trong nước đắt hơn đáng kể so với thế giới. "
            "Cân nhắc rủi ro mua ở vùng premium cao (do hạn chế nguồn cung theo Nghị định 24).")


def _build_snapshot() -> Dict[str, Any]:
    """Tổng hợp snapshot vàng + tính premium. Fail-open từng phần."""
    sjc = _fetch_sjc()
    world = _fetch_world_usd_oz()
    usd_vnd = _fetch_usd_vnd()

    world_per_luong: Optional[float] = None
    premium_vnd: Optional[float] = None
    premium_pct: Optional[float] = None
    warnings_list = []

    world_price = world.get("price") if world else None
    if world_price and usd_vnd:
        world_per_luong = world_price * OZ_PER_LUONG * usd_vnd
        if sjc and sjc.get("sell"):
            premium_vnd = sjc["sell"] - world_per_luong
            if world_per_luong:
                premium_pct = round(premium_vnd / world_per_luong * 100, 2)

    if not sjc:
        warnings_list.append("Chưa lấy được giá vàng SJC.")
    if not world:
        warnings_list.append("Chưa lấy được giá vàng thế giới.")
    if not usd_vnd:
        warnings_list.append("Chưa lấy được tỷ giá USD/VND.")

    spread = None
    if sjc and sjc.get("buy") is not None and sjc.get("sell") is not None:
        spread = sjc["sell"] - sjc["buy"]

    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "sjc_name": sjc["name"] if sjc else None,
        "sjc_branch": sjc["branch"] if sjc else None,
        "sjc_buy": sjc["buy"] if sjc else None,
        "sjc_sell": sjc["sell"] if sjc else None,
        "sjc_date": sjc["date"] if sjc else None,
        "bid_ask_spread": spread,
        "world_usd_oz": world_price,
        "world_source": world.get("source") if world else None,
        "usd_vnd": usd_vnd,
        "world_per_luong_vnd": round(world_per_luong) if world_per_luong else None,
        "premium_vnd": round(premium_vnd) if premium_vnd is not None else None,
        "premium_pct": premium_pct,
        "assessment": _assess_premium(premium_pct),
        "gold_types": get_gold_types(),
        "data_warning": " ".join(warnings_list) if warnings_list else None,
    }


def get_gold_overview() -> Dict[str, Any]:
    """Snapshot vàng (cache 5 phút trong tiến trình, double-checked locking)."""
    def _fresh() -> Optional[Dict[str, Any]]:
        with _cache_lock:
            payload = _cache.get("payload")
            if payload is not None and (time.time() - _cache["at"]) < _CACHE_TTL_SECONDS:
                return payload
        return None

    hit = _fresh()
    if hit is not None:
        return hit

    with _build_lock:
        hit = _fresh()
        if hit is not None:
            return hit
        payload = _build_snapshot()
        with _cache_lock:
            _cache["at"] = time.time()
            _cache["payload"] = payload
        return payload
