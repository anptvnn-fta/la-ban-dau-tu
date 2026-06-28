# -*- coding: utf-8 -*-
"""Kiểm thử dịch vụ Vàng: phép tính chênh lệch, dải lịch sử, parse số."""

from src.services import gold_service as gs


def _reset_caches():
    gs._cache.update(at=0.0, payload=None)
    gs._types_cache.update(at=0.0, payload=None)
    gs._history_cache.update(at=0.0, payload=None, key=None)


def test_safe_float_parses_comma_and_handles_garbage():
    assert gs._safe_float("26,454") == 26454.0
    assert gs._safe_float("147000000.0") == 147000000.0
    assert gs._safe_float("abc") is None
    assert gs._safe_float(None) is None


def test_premium_calc_uses_oz_to_luong_and_fx(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(gs, "_fetch_sjc", lambda: {
        "name": "Vàng SJC", "branch": "Hồ Chí Minh",
        "buy": 144_000_000.0, "sell": 147_000_000.0, "date": "2026-06-27",
    })
    monkeypatch.setattr(gs, "_fetch_world_usd_oz", lambda: {"price": 4000.0, "source": "test"})
    monkeypatch.setattr(gs, "_fetch_usd_vnd", lambda: 26000.0)
    monkeypatch.setattr(gs, "get_gold_types", lambda: [])

    snap = gs._build_snapshot()
    expected_world = round(4000.0 * gs.OZ_PER_LUONG * 26000.0)
    assert snap["world_per_luong_vnd"] == expected_world
    assert snap["premium_vnd"] == 147_000_000 - expected_world
    assert snap["bid_ask_spread"] == 3_000_000.0
    assert snap["premium_pct"] == round((147_000_000 - expected_world) / expected_world * 100, 2)
    assert snap["data_warning"] is None


def test_partial_data_yields_warning_and_no_premium(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(gs, "_fetch_sjc", lambda: {
        "name": "x", "branch": "y", "buy": 1.0, "sell": 2.0, "date": "",
    })
    monkeypatch.setattr(gs, "_fetch_world_usd_oz", lambda: None)
    monkeypatch.setattr(gs, "_fetch_usd_vnd", lambda: None)
    monkeypatch.setattr(gs, "get_gold_types", lambda: [])

    snap = gs._build_snapshot()
    assert snap["premium_vnd"] is None
    assert snap["data_warning"] and "thế giới" in snap["data_warning"]


def test_history_computes_premium_band(monkeypatch):
    _reset_caches()
    # SJC cố định 150tr/lượng; thế giới 4000$/oz; FX 26000 → premium giống nhau mọi điểm.
    monkeypatch.setattr(gs, "_scrape_sjc_on", lambda d: 150_000_000.0)
    monkeypatch.setattr(gs, "_world_usd_series", lambda days: {"2026-01-01": 4000.0})
    monkeypatch.setattr(gs, "_usdvnd_series", lambda days: {"2026-01-01": 26000.0})
    monkeypatch.setattr(gs, "_fetch_usd_vnd", lambda: 26000.0)

    h = gs.get_gold_history(days=60, step_days=30)
    assert len(h["points"]) >= 2
    assert all(p["premium_pct"] is not None for p in h["points"])
    assert h["premium_avg_pct"] is not None
    assert h["premium_min_pct"] <= h["premium_avg_pct"] <= h["premium_max_pct"]
    # premium = (150tr - 4000*1.20565*26000) / world * 100
    world = 4000.0 * gs.OZ_PER_LUONG * 26000.0
    assert h["premium_current_pct"] == round((150_000_000 - world) / world * 100, 2)


def test_type_name_is_shortened(monkeypatch):
    _reset_caches()
    import pandas as pd
    fake = pd.DataFrame([
        {"name": "VÀNG MIẾNG SJC (Vàng SJC)", "karat": "24k",
         "buy_price": 14_300_000, "sell_price": 14_700_000, "time": "26/06/2026 17:18"},
    ])
    import vnstock.explorer.misc.gold_price as gp
    monkeypatch.setattr(gp, "btmc_goldprice", lambda *a, **k: fake)

    types = gs._fetch_gold_types()
    assert types and types[0]["name"] == "VÀNG MIẾNG SJC"   # đã bỏ phần trong ngoặc
    assert types[0]["sell"] == 147_000_000.0                 # 14,7tr/chỉ × 10 = /lượng
