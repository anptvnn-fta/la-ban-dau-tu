# -*- coding: utf-8 -*-
"""
===================================
API Tư vấn đầu tư đa kênh
===================================

GET  /api/v1/tu-van/options  — định nghĩa 26 trường hồ sơ (dựng wizard).
POST /api/v1/tu-van/suggest  — chấm điểm 2 thang + nhóm cuối + phân bổ đa kênh + live data (nhanh, không AI).
GET  /api/v1/tu-van/stocks   — 3 rổ biến động cổ phiếu (vnstock, cache 12h).
POST /api/v1/tu-van/ai       — AI phân tích chân dung + diễn giải (fail-open).

Logic: src/services/tu_van_service.py + src/services/tu_van_ai.py.
"""

import logging

from fastapi import APIRouter, HTTPException

from api.v1.schemas.tu_van import TuVanInput

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/options")
def tu_van_options():
    """Định nghĩa 26 trường hồ sơ (nhóm theo data_group)."""
    from src.services.tu_van_service import get_options

    return get_options()


@router.post("/suggest")
def tu_van_suggest(req: TuVanInput):
    """Tính 2 thang điểm + nhóm cuối + phân bổ đa kênh + số tiền + dữ liệu live.

    Phần SỐ do luật quyết định (không gọi AI) — nhanh, dữ liệu live có cache.
    """
    from src.services.tu_van_service import build_result

    try:
        return build_result(req.model_dump(), with_market=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Tư vấn (suggest) thất bại: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tư vấn thất bại: {exc}")


@router.get("/stocks")
def tu_van_stocks():
    """3 rổ biến động cổ phiếu (Ổn định / Trung bình / Rủi ro), cache 12 giờ."""
    from src.services.tu_van_service import get_stock_buckets

    try:
        return get_stock_buckets()
    except Exception as exc:  # noqa: BLE001
        logger.error("Tư vấn (stocks) thất bại: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lấy rổ cổ phiếu thất bại: {exc}")


@router.post("/ai")
def tu_van_ai(req: TuVanInput):
    """AI phân tích chân dung + diễn giải (4 đoạn). Fail-open về văn bản mẫu."""
    from src.services.tu_van_service import build_result, labels_for_ai
    from src.services.tu_van_ai import analyze

    try:
        profile = req.model_dump()
        result = build_result(profile, with_market=True)
        labels = labels_for_ai(profile)
        return analyze(labels, result, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Tư vấn (ai) thất bại: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI tư vấn thất bại: {exc}")
