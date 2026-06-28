# -*- coding: utf-8 -*-
"""Kiểm thử dịch vụ Xăng Dầu: đổi đơn vị, giá hiện tại + thay đổi, kỳ điều hành, lịch sử."""

import datetime as _dt

from src.services import petrol_service as ps


def _reset():
    ps._ov_cache.update(at=0.0, payload=None)
    ps._hist_cache.update(at=0.0, payload=None, key=None)


def test_to_dong_converts_and_treats_zero_as_missing():
    assert ps._to_dong(19.35) == 19350.0      # nghìn đồng/lít → đồng/lít
    assert ps._to_dong(0) is None             # 0 = ngừng niêm yết
    assert ps._to_dong(None) is None
    assert ps._to_dong("abc") is None


def test_next_adjustment_is_a_thursday():
    for d in ["2026-06-27", "2026-07-02", "2026-07-01"]:
        nxt = ps._next_adjustment(_dt.date.fromisoformat(d))
        assert _dt.date.fromisoformat(nxt).weekday() == 3  # thứ Năm
        assert nxt > d


def test_overview_current_price_and_change(monkeypatch):
    _reset()
    series = [
        {"date": "2026-06-01", "ron95": 20000.0, "e5": 19000.0, "do": 18000.0, "dau_hoa": 17000.0},
        {"date": "2026-06-08", "ron95": 20000.0, "e5": 20120.0, "do": 18000.0, "dau_hoa": 17000.0},
        {"date": "2026-06-15", "ron95": 0.0,     "e5": 19350.0, "do": 21860.0, "dau_hoa": 20890.0},
    ]
    # _to_dong đã được áp dụng trong _fetch_chart; ở đây mock trả thẳng giá đồng/lít (0→None ở RON95).
    series[2]["ron95"] = None
    monkeypatch.setattr(ps, "_fetch_goctienich_board", lambda: ({}, None))  # ép dùng dự phòng giaxanghomnay
    monkeypatch.setattr(ps, "_fetch_chart", lambda: series)
    monkeypatch.setattr(ps, "_world_oil", lambda: {"brent": 73.5, "wti": 70.2})

    ov = ps._build_overview()
    fuels = {f["code"]: f for f in ov["fuels"]}
    # E5 hiện 19.350; kỳ trước (khác giá trị) là 20.120 → giảm 770
    assert fuels["e5"]["price"] == 19350.0
    assert fuels["e5"]["change"] == 19350.0 - 20120.0
    assert fuels["e5"]["change_pct"] == round((19350.0 - 20120.0) / 20120.0 * 100, 2)
    # RON95-III ngừng niêm yết → price None
    assert fuels["ron95"]["price"] is None
    assert ov["brent_usd"] == 73.5
    assert ov["effective_date"] == "2026-06-15"


def test_overview_uses_goctienich_e10_as_primary(monkeypatch):
    _reset()
    board = {
        "Xăng E10 RON 95-III": {"price": 19910.0, "change": -840.0, "change_pct": -4.05},
        "Xăng E5 RON 92-II": {"price": 19350.0, "change": -770.0, "change_pct": -3.83},
        "Dầu DO 0,05S-II": {"price": 21860.0, "change": -1670.0, "change_pct": -7.1},
        "Dầu hỏa 2-K": {"price": 20890.0, "change": -1800.0, "change_pct": -7.93},
    }
    monkeypatch.setattr(ps, "_fetch_goctienich_board", lambda: (board, "06:00:02 27/06/2026"))
    monkeypatch.setattr(ps, "_world_oil", lambda: {"brent": 73.5, "wti": 70.2})

    ov = ps._build_overview()
    fuels = {f["code"]: f for f in ov["fuels"]}
    assert "e10_ron95" in fuels                      # đã có giá E10
    assert fuels["e10_ron95"]["price"] == 19910.0
    assert fuels["e10_ron95"]["change"] == -840.0
    assert "ron95" not in fuels                       # không còn RON95-III "—"
    assert ov["effective_date"] == "2026-06-27"       # parse từ updatedAt


def test_history_filters_range_and_attaches_brent(monkeypatch):
    _reset()
    today = _dt.date.today()
    old = (today - _dt.timedelta(days=900)).isoformat()
    recent = (today - _dt.timedelta(days=10)).isoformat()
    series = [
        {"date": old, "ron95": 30000.0, "e5": 29000.0, "do": 28000.0, "dau_hoa": 27000.0},
        {"date": recent, "ron95": None, "e5": 19350.0, "do": 21860.0, "dau_hoa": 20890.0},
    ]
    monkeypatch.setattr(ps, "_fetch_chart", lambda: series)
    monkeypatch.setattr(ps, "_brent_series", lambda days: {recent: 73.5})

    h = ps.get_petrol_history(days=365)   # chỉ lấy trong 1 năm → loại điểm 900 ngày trước
    dates = [p["date"] for p in h["points"]]
    assert old not in dates and recent in dates
    pt = next(p for p in h["points"] if p["date"] == recent)
    assert pt["e5"] == 19350.0 and pt["brent"] == 73.5
