# -*- coding: utf-8 -*-
"""Regression tests for Vietnam (VN) market support (mirrors test_jp_kr_market_support).

Covers the full Option-A integration:
  P1 data layer (VnstockFetcher + routing), P2 recognition + prompt semantics,
  P3 trading calendar, P4 profile/validators, P5 stock-index seed wiring.

VN is addressed only via the explicit ``.VN`` suffix (e.g. ``FPT.VN``); bare
3-letter tickers (FPT, GAS, BID) deliberately stay US to avoid ticker collision.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data_provider.base import (
    BaseFetcher,
    DataFetchError,
    DataFetcherManager,
    normalize_stock_code,
    _market_tag,
)
from src.core.market_profile import get_profile
from src.core.trading_calendar import (
    MARKET_EXCHANGE,
    MARKET_TIMEZONE,
    get_market_for_stock,
    is_market_open,
)
from src.market_context import detect_market, get_market_guidelines, get_market_role
from src.services.stock_code_utils import is_code_like, normalize_code
from src.services.portfolio_service import VALID_MARKETS
from src.services.intelligence_service import _ALLOWED_MARKETS
from src.services.stock_index_remote_service import SUPPORTED_STOCK_INDEX_MARKETS
from src.data.stock_index_loader import _is_vn_index_code, _build_stock_code_lookup


class _FakeFetcher(BaseFetcher):
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.priority = 0 if name != "VnstockFetcher" else 4
        self.calls = []
        self.should_fail = should_fail

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        self.calls.append(stock_code)
        if self.should_fail:
            raise DataFetchError(f"{self.name} should not be called for {stock_code}")
        return pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-06-25")],
                "open": [98000.0],
                "high": [99000.0],
                "low": [97000.0],
                "close": [98500.0],
                "volume": [1_000_000],
                "amount": [9.85e10],
                "pct_chg": [0.5],
            }
        )


# --------------------------------------------------------------------------- P2
def test_normalize_and_detect_vn_suffix_codes() -> None:
    assert normalize_stock_code("fpt.vn") == "FPT.VN"
    assert normalize_stock_code("VCB.VN") == "VCB.VN"
    assert normalize_stock_code("vhm.vn") == "VHM.VN"

    assert detect_market("FPT.VN") == "vn"
    assert detect_market("VCB.VN") == "vn"
    assert detect_market("fpt.vn") == "vn"

    assert get_market_for_stock("FPT.VN") == "vn"
    assert get_market_for_stock("VCB.VN") == "vn"

    assert _market_tag("FPT.VN") == "vn"

    assert is_code_like("FPT.VN") is True
    assert is_code_like("VCB.VN") is True
    assert normalize_code("fpt.vn") == "FPT.VN"
    assert normalize_code("FPT.VN") == "FPT.VN"


def test_bare_vn_tickers_stay_us_to_avoid_collision() -> None:
    # FPT / GAS / BID are real HOSE tickers but ALSO match the US pattern; bare
    # input must route to US, only the explicit .VN suffix routes to VN.
    for bare in ("FPT", "GAS", "BID", "VCB", "HPG"):
        assert detect_market(bare) == "us", bare
        assert _market_tag(bare) == "us", bare
        assert get_market_for_stock(bare) == "us", bare
    # other markets unaffected
    assert detect_market("600519") == "cn"
    assert detect_market("7203.T") == "jp"
    assert detect_market("005930.KS") == "kr"


def test_market_guidelines_for_vn_exclude_a_share_specific_context() -> None:
    assert get_market_role("FPT.VN", "zh") == "越南股"
    assert get_market_role("FPT.VN", "en") == "Vietnam stock"

    zh = get_market_guidelines("FPT.VN", "zh")
    en = get_market_guidelines("FPT.VN", "en")

    # Vietnam-specific framing
    assert "HOSE" in zh and "±7%" in zh
    assert "khối ngoại" in zh
    assert "HOSE" in en and "7%" in en
    assert "khối ngoại" in en

    # Must explicitly disavow A-share concepts (same contract as JP/KR)
    assert "不要套用 A 股" in zh
    assert "北向资金" in zh
    assert "龙虎榜" in zh
    assert "do not apply" in en.lower()


# --------------------------------------------------------------------------- P4
def test_market_profile_and_validators_include_vn() -> None:
    profile = get_profile("vn")
    assert profile.region == "vn"
    assert profile.mood_index_code == "VNINDEX"
    # VN has no A-share-style breadth / sector ranking data
    assert profile.has_market_stats is False
    assert profile.has_sector_rankings is False

    assert "vn" in VALID_MARKETS
    assert "vn" in _ALLOWED_MARKETS
    assert "VN" in SUPPORTED_STOCK_INDEX_MARKETS


# --------------------------------------------------------------------------- P1
def test_data_fetcher_manager_routes_vn_daily_only_to_vnstock() -> None:
    efinance = _FakeFetcher("EfinanceFetcher", should_fail=True)
    akshare = _FakeFetcher("AkshareFetcher", should_fail=True)
    yfinance = _FakeFetcher("YfinanceFetcher", should_fail=True)
    vnstock = _FakeFetcher("VnstockFetcher")
    manager = DataFetcherManager(fetchers=[efinance, akshare, yfinance, vnstock])

    with patch("data_provider.base.record_provider_run_started"), patch("data_provider.base.record_provider_run"):
        df, source = manager.get_daily_data("FPT.VN")

    assert source == "VnstockFetcher"
    assert not df.empty
    assert efinance.calls == []
    assert akshare.calls == []
    assert yfinance.calls == []
    assert vnstock.calls == ["FPT.VN"]


def test_vnstock_fetcher_converts_codes_and_scales_prices() -> None:
    pytest.importorskip("vnstock", reason="vnstock not installed")
    from data_provider.vnstock_fetcher import VnstockFetcher

    fetcher = VnstockFetcher()
    # .VN suffix is stripped for the vnstock API; index codes pass through
    assert fetcher._convert_stock_code("FPT.VN") == "FPT"
    assert fetcher._convert_stock_code("fpt.vn") == "FPT"
    assert fetcher._convert_stock_code("VNINDEX") == "VNINDEX"

    raw = pd.DataFrame(
        {
            "time": pd.to_datetime(["2025-06-19", "2025-06-20"]),
            "open": [98.0, 98.5],
            "high": [99.0, 99.2],
            "low": [97.5, 98.0],
            "close": [98.5, 99.0],
            "volume": [1000, 2000],
        }
    )

    # Equity: VCI thousands-VND -> absolute VND (x1000)
    eq = fetcher._normalize_data(raw.copy(), "FPT.VN")
    assert eq["close"].iloc[-1] == pytest.approx(99000.0)
    assert eq["code"].iloc[0] == "FPT.VN"
    assert "amount" in eq.columns and "pct_chg" in eq.columns
    assert set(["date", "open", "high", "low", "close", "volume"]).issubset(eq.columns)

    # Index: full points -> NOT scaled
    idx = fetcher._normalize_data(raw.copy(), "VNINDEX")
    assert idx["close"].iloc[-1] == pytest.approx(99.0)


# --------------------------------------------------------------------------- P3
def test_trading_calendar_registers_vn_exchange_and_timezone() -> None:
    assert MARKET_EXCHANGE["vn"] == "XHCM"
    assert MARKET_TIMEZONE["vn"] == "Asia/Ho_Chi_Minh"
    # exchange-calendars has no XHCM -> fail-open: VN treated as a trading day
    from datetime import date

    assert is_market_open("vn", date(2026, 6, 25)) is True


# --------------------------------------------------------------------------- P5
def test_stock_index_generation_classifies_vn_without_bare_collision() -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import generate_index_from_csv as g
    finally:
        # keep sys.path tidy but leave the entry; harmless for the test session
        pass

    assert g.determine_market("FPT.VN") == "VN"
    assert g.determine_market("GAS.VN") == "VN"
    assert g.determine_market("AAPL") == "US"
    assert g.determine_market("600519.SH") == "CN"
    assert g.extract_symbol_from_ts_code("FPT.VN", "VN") == "FPT.VN"

    parsed = g.parse_stock_row(
        {"ts_code": "FPT.VN", "symbol": "FPT.VN", "name": "Công ty Cổ phần FPT",
         "enname": "FPT Corp", "aliases": "FPT Corp"},
        "VN",
    )
    assert parsed is not None and parsed["market"] == "VN" and parsed["symbol"] == "FPT.VN"
    entry = g.build_stock_index([parsed])[0]
    assert entry["canonicalCode"] == "FPT.VN"
    assert entry["displayCode"] == "FPT.VN"
    assert entry["market"] == "VN"

    # Loader: VN resolves ONLY via explicit suffix; bare codes are not registered.
    assert _is_vn_index_code("FPT.VN") is True
    assert _is_vn_index_code("FPT") is False
    lookup = _build_stock_code_lookup(
        [
            ["FPT.VN", "FPT.VN", "FPT", "FPT", ""],
            ["GAS.VN", "GAS.VN", "PV Gas", "PV Gas", ""],
            ["7203.T", "7203.T", "Toyota", "Toyota", ""],
        ]
    )
    assert lookup.get("FPT.VN") == "FPT.VN"
    assert lookup.get("GAS.VN") == "GAS.VN"
    assert lookup.get("FPT") is None  # bare stays US (collision-free)
    assert lookup.get("GAS") is None
    assert lookup.get("7203") == "7203.T"  # JP bare resolution still works
