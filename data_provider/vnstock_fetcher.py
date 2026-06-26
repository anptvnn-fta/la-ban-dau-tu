# -*- coding: utf-8 -*-
"""
===================================
VnstockFetcher - Vietnam market data source (HOSE/HNX/UPCOM)
===================================

Data source: vnstock (https://github.com/thinh-vu/vnstock) — VCI primary, KBS fallback.
Scope: Vietnam-listed equities addressed with the explicit ``.VN`` suffix (e.g. ``FPT.VN``).

Mirrors the YfinanceFetcher contract (a single foreign-market fetcher) but uses the
vnstock 4.x modular API. Registered for market ``vn`` only, so the DataFetcherManager
routes ``.VN`` codes here and skips all A-share / US fetchers.

Key facts (verified live against vnstock 4.0.4):
- ``Quote(symbol='FPT', source='VCI').history(start, end, interval='1D')`` ->
  columns ``['time','open','high','low','close','volume']``.
- VCI returns **equity** prices in **thousands of VND** (FPT close ~98.5 means ~98,500 VND),
  so ``_normalize_data`` multiplies equity OHLC by 1000 to absolute VND.
- VCI returns **index** values in **full points** (VNINDEX ~1349), so indices are NOT scaled.
- ``Trading(...).price_board([sym])`` realtime values ARE already in full VND.
- The high-level ``Quote`` constructor is ``Quote(source='kbs', symbol='', ...)`` —
  ``source`` is the FIRST positional arg, so this module always calls it with keywords.
"""

import logging
import os
from typing import Optional, List, Dict, Any

import pandas as pd

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float, safe_int

logger = logging.getLogger(__name__)

# Display code -> (vnstock symbol, display name). Hyphenated forms such as
# 'HNX-Index' raise ValueError in the vnstock symbol validator, so the canonical
# concatenated codes are used here.
VN_INDEX_CODES: Dict[str, str] = {
    "VNINDEX": "VNINDEX",
    "VN30": "VN30",
    "HNXINDEX": "HNXINDEX",
    "HNX30": "HNX30",
    "UPCOMINDEX": "UPCOMINDEX",
}
VN_MAIN_INDICES: Dict[str, str] = {
    "VNINDEX": "VN-Index",
    "VN30": "VN30",
    "HNXINDEX": "HNX-Index",
    "UPCOMINDEX": "UPCOM-Index",
}

# Sources tried in order for daily history (VCI primary, KBS fallback).
_HISTORY_SOURCES = ("VCI", "KBS")


class VnstockFetcher(BaseFetcher):
    """Vietnam market data source backed by the vnstock library."""

    name = "VnstockFetcher"
    priority = int(os.getenv("VNSTOCK_PRIORITY", "4"))
    allow_empty_daily_data = False

    def __init__(self):
        """Lightweight init; vnstock submodules are imported lazily per call."""
        pass

    # ------------------------------------------------------------------
    # Code handling
    # ------------------------------------------------------------------
    @staticmethod
    def _is_vn_index(code: str) -> bool:
        return (code or "").strip().upper() in VN_INDEX_CODES

    def _convert_stock_code(self, stock_code: str) -> str:
        """Strip the ``.VN`` suffix for the vnstock API; pass index codes through.

        Examples:
            'FPT.VN' -> 'FPT', 'fpt.vn' -> 'FPT', 'FPT' -> 'FPT', 'VNINDEX' -> 'VNINDEX'
        """
        code = (stock_code or "").strip().upper()
        if self._is_vn_index(code):
            return VN_INDEX_CODES[code]
        if code.endswith(".VN"):
            return code[:-3]
        return code

    # ------------------------------------------------------------------
    # Daily history (abstract methods)
    # ------------------------------------------------------------------
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch raw daily OHLCV from vnstock, trying VCI then KBS."""
        from vnstock.api.quote import Quote

        symbol = self._convert_stock_code(stock_code)
        last_err: Optional[Exception] = None

        for source in _HISTORY_SOURCES:
            try:
                logger.debug(f"[Vnstock] Quote(symbol={symbol}, source={source}).history({start_date}~{end_date})")
                quote = Quote(symbol=symbol, source=source)
                df = quote.history(start=start_date, end=end_date, interval="1D")
                if df is not None and not df.empty:
                    return df
                logger.debug(f"[Vnstock] {source} returned empty for {symbol}")
            except Exception as exc:  # noqa: BLE001 - try next source
                last_err = exc
                logger.warning(f"[Vnstock] {source} history failed for {symbol}: {exc}")

        if last_err is not None:
            raise DataFetchError(f"vnstock 获取 {stock_code} 历史数据失败: {last_err}") from last_err
        raise DataFetchError(f"vnstock 未查询到 {stock_code} 的历史数据")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """Normalize vnstock columns to STANDARD_COLUMNS.

        vnstock columns: ['time','open','high','low','close','volume'].
        Equity prices come in thousands-VND from VCI and are scaled x1000 to full VND;
        index values are already in full points and are left unscaled.
        """
        df = df.copy()
        df = df.rename(columns={
            "time": "date",
            "Date": "date",
            "datetime": "date",
        })

        is_index = self._is_vn_index(stock_code)
        price_scale = 1.0 if is_index else 1000.0

        for col in ("open", "high", "low", "close"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce") * price_scale

        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

        # Percent change (vnstock does not provide it directly)
        if "close" in df.columns:
            df["pct_chg"] = (df["close"].pct_change() * 100).fillna(0).round(2)

        # Turnover amount (synthetic: volume * close)
        if "volume" in df.columns and "close" in df.columns:
            df["amount"] = df["volume"] * df["close"]
        else:
            df["amount"] = 0

        df["code"] = stock_code

        keep_cols = ["code"] + STANDARD_COLUMNS
        existing = [c for c in keep_cols if c in df.columns]
        return df[existing]

    # ------------------------------------------------------------------
    # Realtime quote (optional capability)
    # ------------------------------------------------------------------
    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """Realtime/near-realtime quote via the vnstock price board (full VND)."""
        if self._is_vn_index(stock_code):
            return None  # index realtime handled via get_main_indices
        symbol = self._convert_stock_code(stock_code)
        try:
            from vnstock.api.trading import Trading

            board = Trading(symbol=symbol, source="VCI").price_board(symbols_list=[symbol])
            if board is None or board.empty:
                logger.debug(f"[Vnstock] price_board empty for {symbol}")
                return None
            row = board.iloc[0]

            def m(group: str, field: str):
                key = (group, field)
                try:
                    return row[key]
                except Exception:
                    return None

            price = safe_float(m("match", "match_price"))
            if price is None or price <= 0:
                price = safe_float(m("match", "avg_match_price"))
            pre_close = safe_float(m("listing", "ref_price")) or safe_float(m("match", "reference_price"))
            # Ngoài giờ giao dịch chưa có khớp lệnh (match_price = 0) → dùng giá tham chiếu
            # làm giá hiển thị để vẫn trả về báo giá thay vì None.
            if (price is None or price <= 0) and pre_close not in (None, 0):
                price = pre_close
            open_price = safe_float(m("match", "open_price"))
            high = safe_float(m("match", "highest"))
            low = safe_float(m("match", "lowest"))
            volume = safe_int(m("match", "accumulated_volume"))
            # accumulated_value is reported in millions of VND -> convert to VND
            acc_value = safe_float(m("match", "accumulated_value"))
            amount = acc_value * 1_000_000 if acc_value is not None else None
            name = str(m("listing", "organ_name") or "")

            change_amount = None
            change_pct = None
            if price is not None and pre_close not in (None, 0):
                change_amount = price - pre_close
                change_pct = (change_amount / pre_close) * 100

            amplitude = None
            if high is not None and low is not None and pre_close not in (None, 0):
                amplitude = ((high - low) / pre_close) * 100

            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=name,
                source=RealtimeSource.VNSTOCK,
                price=price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                change_amount=round(change_amount, 4) if change_amount is not None else None,
                volume=volume,
                amount=amount,
                volume_ratio=None,
                turnover_rate=None,
                amplitude=round(amplitude, 2) if amplitude is not None else None,
                open_price=open_price,
                high=high,
                low=low,
                pre_close=pre_close,
                pe_ratio=None,
                pb_ratio=None,
                total_mv=None,
                circ_mv=None,
            )
            logger.info(f"[Vnstock] realtime {symbol} ok: price={price}")
            return quote
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Vnstock] realtime quote failed for {symbol}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Stock name / list (optional capabilities)
    # ------------------------------------------------------------------
    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """Vietnamese company name via the company overview."""
        if self._is_vn_index(stock_code):
            return VN_MAIN_INDICES.get(self._convert_stock_code(stock_code))
        symbol = self._convert_stock_code(stock_code)
        try:
            from vnstock.api.company import Company

            overview = Company(symbol=symbol, source="VCI").overview()
            if overview is None or overview.empty:
                return None
            if "organ_name" in overview.columns:
                name = str(overview["organ_name"].iloc[0]).strip()
                return name or None
            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[Vnstock] get_stock_name failed for {symbol}: {exc}")
            return None

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """All VN symbols as a DataFrame with canonical ``code`` (SYMBOL.VN) and ``name``."""
        try:
            from vnstock.api.listing import Listing

            df = Listing(source="VCI").all_symbols()
            if df is None or df.empty:
                return None
            df = df.rename(columns={"symbol": "code", "organ_name": "name"})
            if "code" not in df.columns:
                return None
            df["code"] = df["code"].astype(str).str.upper() + ".VN"
            keep = [c for c in ("code", "name") if c in df.columns]
            return df[keep]
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[Vnstock] get_stock_list failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Market indices (optional capability)
    # ------------------------------------------------------------------
    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """Main Vietnam indices (VN-Index, VN30, HNX-Index, UPCOM-Index)."""
        if region not in ("vn", "cn"):  # only serve VN; ignore other regions
            return None
        from datetime import datetime, timedelta

        from vnstock.api.quote import Quote

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        results: List[Dict[str, Any]] = []
        for code, name in VN_MAIN_INDICES.items():
            try:
                df = Quote(symbol=code, source="VCI").history(start=start, end=end, interval="1D")
                if df is None or df.empty:
                    continue
                today = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else today
                # Index values are full points — no x1000 scaling.
                current = safe_float(today.get("close"))
                prev_close = safe_float(prev.get("close"))
                change = (current - prev_close) if (current is not None and prev_close is not None) else None
                change_pct = (change / prev_close * 100) if (change is not None and prev_close) else None
                results.append({
                    "code": code,
                    "name": name,
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "open": safe_float(today.get("open")),
                    "high": safe_float(today.get("high")),
                    "low": safe_float(today.get("low")),
                    "prev_close": prev_close,
                    "volume": safe_float(today.get("volume")),
                    "amount": 0.0,
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[Vnstock] index {code} failed: {exc}")
        if results:
            logger.info(f"[Vnstock] fetched {len(results)} VN indices")
            return results
        return None


def compute_vn_ta_indicators(df: "pd.DataFrame") -> dict:
    """Compute RSI-14, MACD(12,26,9), Bollinger(20,2), ADX-14, ATR-14 via vnstock_ta.

    Args:
        df: OHLCV DataFrame with columns date/open/high/low/close/volume
            (same df the pipeline passes to StockTrendAnalyzer.analyze()).
            Extra columns (amount, pct_chg, ma5 …) are ignored.
            Must have at least 26 rows for MACD; returns {} for shorter series.

    Returns:
        Compact dict ready for insertion into enhanced_context['vn_ta_indicators'].
        Returns empty dict on any failure so the caller never raises (fail-open).
    """
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from vnstock_ta import Indicator  # type: ignore

        if df is None or len(df) < 26:
            return {}

        ind = Indicator(df)

        # ── RSI(14) ──────────────────────────────────────────────────────
        rsi_s = ind.rsi(14)
        rsi_val = float(rsi_s.iloc[-1]) if rsi_s is not None and len(rsi_s) else float("nan")
        if rsi_val >= 70:
            rsi_zone = "超买 (>70)"
        elif rsi_val >= 55:
            rsi_zone = "偏强 (55-70)"
        elif rsi_val >= 45:
            rsi_zone = "中性 (45-55)"
        elif rsi_val >= 30:
            rsi_zone = "偏弱 (30-45)"
        else:
            rsi_zone = "超卖 (<30)"

        # ── MACD(12,26,9) ────────────────────────────────────────────────
        macd_df = ind.macd()
        macd_line = float(macd_df["MACD_12_26_9"].iloc[-1])
        macd_hist = float(macd_df["MACDh_12_26_9"].iloc[-1])
        macd_sig  = float(macd_df["MACDs_12_26_9"].iloc[-1])
        prev_line = float(macd_df["MACD_12_26_9"].iloc[-2]) if len(macd_df) >= 2 else macd_line
        prev_sig  = float(macd_df["MACDs_12_26_9"].iloc[-2]) if len(macd_df) >= 2 else macd_sig
        if prev_line <= prev_sig and macd_line > macd_sig:
            macd_cross = "金叉 (DIF上穿DEA)"
        elif prev_line >= prev_sig and macd_line < macd_sig:
            macd_cross = "死叉 (DIF下穿DEA)"
        elif macd_line > macd_sig:
            macd_cross = "多头排列 (DIF>DEA)"
        else:
            macd_cross = "空头排列 (DIF<DEA)"

        # ── Bollinger Bands(20,2) ─────────────────────────────────────────
        bb_df = ind.bbands(20, 2.0)
        bb_pct_b = float(bb_df["BBP_20_2.0"].iloc[-1])
        bb_upper = float(bb_df["BBU_20_2.0"].iloc[-1])
        bb_lower = float(bb_df["BBL_20_2.0"].iloc[-1])
        bb_mid   = float(bb_df["BBM_20_2.0"].iloc[-1])
        if bb_pct_b >= 1.0:
            bb_pos = "触及/突破上轨 (超买区)"
        elif bb_pct_b >= 0.8:
            bb_pos = "接近上轨 (偏强)"
        elif bb_pct_b >= 0.5:
            bb_pos = "中轨以上 (偏多)"
        elif bb_pct_b >= 0.2:
            bb_pos = "中轨以下 (偏空)"
        elif bb_pct_b >= 0.0:
            bb_pos = "接近下轨 (偏弱)"
        else:
            bb_pos = "触及/突破下轨 (超卖区)"

        # ── ADX(14) ──────────────────────────────────────────────────────
        adx_df = ind.adx(14)
        adx_val = float(adx_df["ADX_14"].iloc[-1])
        dmp     = float(adx_df["DMP_14"].iloc[-1])
        dmn     = float(adx_df["DMN_14"].iloc[-1])
        if adx_val >= 40:
            trend_strength = "极强趋势"
        elif adx_val >= 25:
            trend_strength = "强趋势"
        elif adx_val >= 20:
            trend_strength = "趋势形成"
        else:
            trend_strength = "无趋势/盘整"
        adx_dir = "多头主导 (+DI>-DI)" if dmp > dmn else "空头主导 (-DI>+DI)"

        # ── ATR(14) ───────────────────────────────────────────────────────
        atr_val = float(ind.atr(14).iloc[-1])
        close_last = float(df["close"].iloc[-1]) if "close" in df.columns else 1.0
        atr_pct = (atr_val / close_last * 100) if close_last > 0 else 0.0

        return {
            "rsi_14": round(rsi_val, 2),
            "rsi_zone": rsi_zone,
            "macd_line": round(macd_line, 4),
            "macd_signal": round(macd_sig, 4),
            "macd_hist": round(macd_hist, 4),
            "macd_cross": macd_cross,
            "bb_upper": round(bb_upper, 0),
            "bb_mid": round(bb_mid, 0),
            "bb_lower": round(bb_lower, 0),
            "bb_pct_b": round(bb_pct_b, 3),
            "bb_position": bb_pos,
            "adx_14": round(adx_val, 2),
            "adx_trend_strength": trend_strength,
            "adx_direction": adx_dir,
            "atr_14": round(atr_val, 0),
            "atr_pct": round(atr_pct, 2),
        }
    except Exception as exc:  # noqa: BLE001 — fail-open, never crash the pipeline
        import logging as _logging
        _logging.getLogger(__name__).warning("[VN-TA] vnstock_ta compute failed: %s", exc)
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = VnstockFetcher()
    df = f.get_daily_data("FPT.VN", days=10)
    print(f"rows={len(df)}")
    print(df.tail())
    print("name:", f.get_stock_name("FPT.VN"))
