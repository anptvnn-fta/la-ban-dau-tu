# -*- coding: utf-8 -*-
"""Quét tín hiệu kỹ thuật hàng loạt cho một danh sách mã (watchlist / danh mục).

Với mỗi mã: lấy lịch sử giá → tính tín hiệu kỹ thuật (StockTrendAnalyzer, không gọi
LLM) → tạo một DecisionSignal. Nhanh, dùng để lấp đầy trang Tín Hiệu theo danh mục
theo dõi hoặc cổ phiếu đang nắm giữ.
"""

import datetime
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_BUY_TO_ACTION = {
    "STRONG_BUY": "buy", "BUY": "buy",
    "HOLD": "hold", "WAIT": "watch",
    "SELL": "sell", "STRONG_SELL": "sell",
}

_BARE_VN = re.compile(r"^[A-Z]{2,3}$")


def _to_vn(code: str) -> str:
    c = (code or "").strip().upper()
    return f"{c}.VN" if _BARE_VN.match(c) else c


_MAX_SCAN_CODES = 100  # chặn quét quá nhiều mã (tránh treo / cạn tài nguyên)


def scan_technical_signals(codes: List[str]) -> Dict[str, Any]:
    """Tạo tín hiệu kỹ thuật cho danh sách mã. Trả về {scanned, created, failed}."""
    codes = list(codes or [])[:_MAX_SCAN_CODES]
    from data_provider.base import DataFetcherManager
    from src.stock_analyzer import StockTrendAnalyzer
    from src.services.decision_signal_service import DecisionSignalService
    from src.schemas.decision_action import localize_action_label

    mgr = DataFetcherManager()
    analyzer = StockTrendAnalyzer()
    svc = DecisionSignalService()
    today = datetime.date.today().isoformat()

    scanned = 0
    created = 0
    failed: List[str] = []
    seen: set = set()

    for raw in codes:
        code = _to_vn(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            df, _src = mgr.get_daily_data(code, days=120)
            if df is None or getattr(df, "empty", True) or len(df) < 30:
                failed.append(code)
                continue
            df = df.sort_values("date").reset_index(drop=True)
            trend = analyzer.analyze(df, code)
            sig = getattr(trend.buy_signal, "name", str(trend.buy_signal))
            action = _BUY_TO_ACTION.get(sig, "watch")
            price = float(df.iloc[-1]["close"])
            scanned += 1
            payload = {
                "market": "vn",
                "stock_code": code,
                "action": action,
                "action_label": localize_action_label(action, "vi"),
                "score": int(getattr(trend, "signal_score", 0) or 0),
                "reason": (
                    f"Tín hiệu kỹ thuật: {getattr(trend, 'trend_status', '')}"
                    f" · MACD {getattr(trend, 'macd_status', '')}"
                    f" · RSI12 {getattr(trend, 'rsi_12', '')}."
                ),
                "source_type": "manual",
                "trigger_source": "scan",
                "report_language": "vi",
                "trace_id": f"scan-{code}-{today}",
                "entry_low": price,
                "entry_high": price,
            }
            res = svc.create_signal(payload)
            if res.get("created"):
                created += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SignalScan] %s lỗi: %s", code, exc)
            failed.append(code)

    return {"scanned": scanned, "created": created, "failed": failed}


def resolve_scan_codes(source: str, account_id: Any = None) -> List[str]:
    """Lấy danh sách mã theo nguồn: 'watchlist' (STOCK_LIST) hoặc 'portfolio' (đang nắm giữ)."""
    source = (source or "watchlist").strip().lower()
    if source == "portfolio":
        try:
            from src.repositories.portfolio_repo import PortfolioRepository
            from src.storage import get_db
            ids = PortfolioRepository(get_db()).list_cached_position_identities(account_id=account_id)
            return [c for (_m, c) in ids if str(c or "").strip()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SignalScan] đọc holdings lỗi: %s", exc)
            return []
    # watchlist
    try:
        from src.config import get_config
        return list(get_config().stock_list or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SignalScan] đọc STOCK_LIST lỗi: %s", exc)
        return []
