# -*- coding: utf-8 -*-
"""Kiểm thử dịch vụ Trái Phiếu: chênh lệch SBV/Fed, US10Y, VN10Y tham khảo."""

from src.services import bond_service as bs


def _reset():
    bs._ov_cache.update(at=0.0, payload=None)
    bs._hist_cache.update(at=0.0, payload=None, key=None)


def test_overview_spreads(monkeypatch):
    _reset()
    monkeypatch.setattr(bs, "_us10y_current", lambda: 4.37)
    o = bs._build_overview()
    assert o["sbv_policy_rate"] == 4.5
    assert o["us_yield"] == 4.37
    assert o["vn10y_ref"] == 4.5
    # SBV − Fed(trung điểm 3.625) = 0.875 → làm tròn 0.88
    assert o["spread_sbv_fed"] == 0.88
    # VN10Y(4.5) − US10Y(4.37) = 0.13
    assert o["spread_vn_us"] == 0.13
    assert o["data_warning"] is None


def test_overview_warns_when_us10y_missing(monkeypatch):
    _reset()
    monkeypatch.setattr(bs, "_us10y_current", lambda: None)
    o = bs._build_overview()
    assert o["us_yield"] is None
    assert o["spread_vn_us"] is None
    assert o["data_warning"]


def test_history_filters_range(monkeypatch):
    _reset()
    import datetime as dt
    today = dt.date.today()
    series = {
        (today - dt.timedelta(days=500)).isoformat(): 4.0,
        (today - dt.timedelta(days=10)).isoformat(): 4.37,
    }
    monkeypatch.setattr(bs, "_tnx_series", lambda period: series)
    h = bs.get_bond_history(days=365)
    dates = [p["date"] for p in h["points"]]
    assert (today - dt.timedelta(days=10)).isoformat() in dates
    assert (today - dt.timedelta(days=500)).isoformat() not in dates  # ngoài 1 năm
