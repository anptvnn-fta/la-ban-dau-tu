# -*- coding: utf-8 -*-
"""
===================================
API Tổng Quan Thị Trường (U3)
===================================

GET /api/v1/market/overview — tổng hợp đồng bộ cho trang "Tổng Quan":
  • Chỉ số chính (VN-Index, VN30, HNX-Index, UPCoM) qua vnstock.
  • Top tăng/giảm, độ rộng thị trường, hiệu suất nhóm ngành — tính từ
    bảng giá (price_board) của rổ VN30.

Mọi lệnh gọi vnstock đều fail-open: nếu một phần dữ liệu lỗi, endpoint vẫn
trả về phần lấy được (kèm cảnh báo) thay vì văng lỗi.
"""

import datetime as _dt
import logging
import math
import threading
import time
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from api.v1.schemas.market import (
    MarketBreadth,
    MarketIndexItem,
    MarketMoverItem,
    MarketOverviewResponse,
    SectorItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Rổ cổ phiếu vốn hoá lớn + phân loại ngành (tiếng Việt) dùng cho heatmap.
# Thành phần có thể đổi theo kỳ review VN30; danh sách này đại diện đủ tốt cho
# bức tranh ngành (được gắn nhãn "VN30" ở giao diện) — nên rà lại sau mỗi kỳ review.
VN30_SECTORS: Dict[str, str] = {
    "ACB": "Ngân hàng", "BID": "Ngân hàng", "CTG": "Ngân hàng", "HDB": "Ngân hàng",
    "MBB": "Ngân hàng", "SHB": "Ngân hàng", "SSB": "Ngân hàng", "STB": "Ngân hàng",
    "TCB": "Ngân hàng", "TPB": "Ngân hàng", "VCB": "Ngân hàng", "VIB": "Ngân hàng",
    "VPB": "Ngân hàng",
    "BCM": "Bất động sản", "VHM": "Bất động sản", "VIC": "Bất động sản", "VRE": "Bất động sản",
    "SSI": "Chứng khoán", "HCM": "Chứng khoán", "VND": "Chứng khoán",
    "HPG": "Thép",
    "GVR": "Cao su & KCN",
    "MWG": "Bán lẻ",
    "MSN": "Thực phẩm & Đồ uống", "SAB": "Thực phẩm & Đồ uống", "VNM": "Thực phẩm & Đồ uống",
    "GAS": "Dầu khí", "PLX": "Dầu khí",
    "POW": "Điện",
    "VJC": "Hàng không",
    "BVH": "Bảo hiểm",
    "FPT": "Công nghệ",
}
VN30 = list(VN30_SECTORS.keys())

# Cache trong tiến trình: tránh gọi vnstock mỗi request (bảng giá ~5-8s).
_CACHE_TTL_SECONDS = 60
_cache_lock = threading.Lock()      # bảo vệ đọc/ghi _cache (nhanh)
_build_lock = threading.Lock()      # đảm bảo chỉ một thread gọi vnstock tại một thời điểm
_cache: Dict[str, Any] = {"at": 0.0, "payload": None}

# Vũ trụ cổ phiếu + bản đồ ngành tải động (VN100 + ICB) — cache lâu (đổi chậm).
_UNIVERSE_TTL_SECONDS = 6 * 3600
_universe_lock = threading.Lock()
_universe_cache: Dict[str, Any] = {"at": 0.0, "symbols": None, "sectors": None, "label": "VN30"}


def _load_universe_and_sectors() -> tuple:
    """Tải rổ VN100 + bản đồ ngành ICB (cấp 2) từ vnstock, cache 6 giờ.

    Fail-open: nếu không tải được, dùng rổ VN30 cứng + bản đồ ngành cứng.
    Trả về (symbols: List[str], sectors: Dict[mã→ngành], label: str).
    """
    now = time.time()
    with _universe_lock:
        if _universe_cache["symbols"] and (now - _universe_cache["at"]) < _UNIVERSE_TTL_SECONDS:
            return _universe_cache["symbols"], _universe_cache["sectors"], _universe_cache["label"]

    symbols: list = []
    sectors: Dict[str, str] = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.api.listing import Listing  # type: ignore
        listing = Listing(source="VCI")
        symbols = [str(s).upper().strip() for s in listing.symbols_by_group("VN100") if str(s).strip()]
        ind = listing.symbols_by_industries()
        # icb_level == 2 cho tên ngành gọn (vd "Bất động sản", "Dịch vụ tài chính").
        for _, row in ind.iterrows():
            try:
                if str(row.get("icb_level")).strip() == "2":
                    sym = str(row.get("symbol") or "").upper().strip()
                    name = str(row.get("icb_name") or "").strip()
                    if sym and name:
                        sectors[sym] = name
            except Exception:  # noqa: BLE001
                continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Market] tải rổ/ngành động thất bại, dùng VN30 cứng: %s", exc)

    if not symbols:
        symbols, sectors, label = list(VN30), dict(VN30_SECTORS), "VN30"
    else:
        if not sectors:
            sectors = dict(VN30_SECTORS)
        label = "VN100"

    with _universe_lock:
        _universe_cache.update(at=time.time(), symbols=symbols, sectors=sectors, label=label)
    return symbols, sectors, label


def _safe_float(v: Any) -> Optional[float]:
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except Exception:
        return None


def _round2(v: Any) -> Optional[float]:
    f = _safe_float(v)
    return round(f, 2) if f is not None else None


def _fetch_indices() -> List[MarketIndexItem]:
    """Chỉ số chính qua DataFetcherManager (vnstock). Fail-open → []."""
    try:
        from data_provider.base import DataFetcherManager

        mgr = DataFetcherManager()
        rows = mgr.get_main_indices(region="vn") or []
        out: List[MarketIndexItem] = []
        for r in rows:
            out.append(
                MarketIndexItem(
                    code=str(r.get("code") or ""),
                    name=str(r.get("name") or r.get("code") or ""),
                    current=_safe_float(r.get("current")),
                    change=_round2(r.get("change")),
                    change_pct=_round2(r.get("change_pct")),
                    high=_safe_float(r.get("high")),
                    low=_safe_float(r.get("low")),
                    volume=_safe_float(r.get("volume")),
                )
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Market] get_main_indices failed: %s", exc)
        return []


def _fetch_board(symbols: List[str]) -> List[Dict[str, Any]]:
    """Bảng giá rổ VN30 qua vnstock price_board. Fail-open → []."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock.api.trading import Trading  # type: ignore

        board = Trading(symbol=symbols[0], source="VCI").price_board(symbols_list=symbols)
        if board is None or getattr(board, "empty", True):
            return []

        def col(group: str, field: str):
            try:
                return board[(group, field)]
            except Exception:
                return None

        sym = col("listing", "symbol")
        org = col("listing", "organ_name")
        ref = col("listing", "ref_price")
        match = col("match", "match_price")
        val = col("match", "accumulated_value")  # triệu VND

        out: List[Dict[str, Any]] = []
        for i in range(len(board)):
            code = str(sym.iloc[i]).upper() if sym is not None else ""
            if not code or code == "NAN":
                continue
            r = _safe_float(ref.iloc[i]) if ref is not None else None
            m = _safe_float(match.iloc[i]) if match is not None else None
            # Chưa khớp lệnh / ngoài giờ (match = 0) → dùng giá tham chiếu, coi như 0%
            # (tránh tính nhầm thành -100% như BVH lúc thị trường đóng cửa).
            if (m is None or m <= 0) and r:
                m = r
            pct = round((m - r) / r * 100, 2) if (r and m and r > 0) else None
            v = _safe_float(val.iloc[i]) if val is not None else None
            out.append({
                "code": code,
                "name": str(org.iloc[i]) if org is not None else None,
                "price": m,
                "change_pct": pct,
                "value": (v * 1_000_000) if v is not None else None,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Market] price_board failed: %s", exc)
        return []


def _build_overview() -> MarketOverviewResponse:
    universe, sector_map, universe_label = _load_universe_and_sectors()
    indices = _fetch_indices()
    board = _fetch_board(universe)

    breadth: Optional[MarketBreadth] = None
    gainers: List[MarketMoverItem] = []
    losers: List[MarketMoverItem] = []
    sectors: List[SectorItem] = []
    warning: Optional[str] = None

    valid = [b for b in board if b.get("change_pct") is not None]
    if valid:
        adv = sum(1 for b in valid if b["change_pct"] > 0)
        dec = sum(1 for b in valid if b["change_pct"] < 0)
        unch = sum(1 for b in valid if b["change_pct"] == 0)
        total_val = sum(b["value"] for b in board if b.get("value") is not None) or None
        breadth = MarketBreadth(
            advancers=adv, decliners=dec, unchanged=unch,
            universe_size=len(board), total_value=total_val,
        )

        ranked = sorted(valid, key=lambda b: b["change_pct"], reverse=True)
        gainers = [MarketMoverItem(**b) for b in ranked[:5]]
        losers = [MarketMoverItem(**b) for b in ranked[::-1][:5]]

        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for b in valid:
            sec = sector_map.get(b["code"])
            if sec:
                buckets[sec].append(b)
        sec_items = [
            SectorItem(
                name=name,
                change_pct=round(sum(i["change_pct"] for i in items) / len(items), 2),
                count=len(items),
                codes=[i["code"] for i in items],
            )
            for name, items in buckets.items()
        ]
        sectors = sorted(sec_items, key=lambda s: (s.change_pct if s.change_pct is not None else 0), reverse=True)
    elif not indices:
        warning = "Không lấy được dữ liệu thị trường lúc này. Vui lòng thử lại sau."
    else:
        warning = f"Chưa lấy được bảng giá {universe_label}; hiện chỉ hiển thị chỉ số."

    # Cảnh báo riêng nếu mất chỉ số nhưng vẫn có bảng giá (tránh ô chỉ số trống không lý do).
    if not indices and warning is None:
        warning = "Chưa lấy được chỉ số chính lúc này."

    return MarketOverviewResponse(
        generated_at=_dt.datetime.now().isoformat(timespec="seconds"),
        universe_label=universe_label,
        indices=indices,
        breadth=breadth,
        top_gainers=gainers,
        top_losers=losers,
        sectors=sectors,
        data_warning=warning,
    )


@router.get("/overview", response_model=MarketOverviewResponse)
def market_overview() -> MarketOverviewResponse:
    """Tổng quan thị trường (cache 60s trong tiến trình)."""
    def _fresh() -> Optional[MarketOverviewResponse]:
        with _cache_lock:
            cached = _cache.get("payload")
            if cached is not None and (time.time() - _cache["at"]) < _CACHE_TTL_SECONDS:
                return cached
        return None

    hit = _fresh()
    if hit is not None:
        return hit

    # Chỉ một thread build tại một thời điểm; thread khác chờ rồi tái dùng kết quả vừa build
    # (double-checked locking) → tránh nhiều request cùng gọi vnstock khi cache hết hạn.
    with _build_lock:
        hit = _fresh()
        if hit is not None:
            return hit
        payload = _build_overview()
        with _cache_lock:
            _cache["at"] = time.time()
            _cache["payload"] = payload
        return payload
