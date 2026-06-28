# -*- coding: utf-8 -*-
"""Kiểm thử dịch vụ Tiết Kiệm: chọn lãi suất tốt nhất + sắp xếp ngân hàng."""

from src.services import savings_service as ss


def _reset():
    ss._cache.update(at=0.0, payload=None)


def test_overview_picks_best_per_term_and_sorts(monkeypatch):
    _reset()
    banks = [
        {"name": "Vietcombank", "symbol": "VCB", "rates": {1: 2.1, 3: 2.4, 6: 3.5, 12: 5.9, 24: 6.0}},
        {"name": "Shinhan Bank", "symbol": "SHB", "rates": {6: 7.0, 12: 7.5, 24: 6.6}},
        {"name": "MB Bank", "symbol": "MBB", "rates": {1: 3.7, 3: 4.1, 6: 4.6, 12: 6.2, 24: 7.0}},
    ]
    monkeypatch.setattr(ss, "_fetch_banks", lambda: banks)

    o = ss._build_overview()
    assert o["terms"] == [1, 3, 6, 12, 24]
    assert o["sbv_policy_rate"] == 4.5

    best = {b["term"]: b for b in o["best"]}
    assert best[12]["rate"] == 7.5 and best[12]["bank"] == "Shinhan Bank"
    assert best[24]["rate"] == 7.0 and best[24]["bank"] == "MB Bank"

    # Sắp theo lãi suất 12 tháng giảm dần → Shinhan (7.5) đầu tiên.
    assert o["banks"][0]["name"] == "Shinhan Bank"
    # Shinhan không công bố kỳ 1/3 tháng → None ở đầu danh sách rates.
    assert o["banks"][0]["rates"][0] is None


def test_empty_source_yields_warning(monkeypatch):
    _reset()
    monkeypatch.setattr(ss, "_fetch_banks", lambda: [])
    o = ss._build_overview()
    assert o["banks"] == []
    assert o["data_warning"]
