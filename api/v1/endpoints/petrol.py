# -*- coding: utf-8 -*-
"""
===================================
API Xăng Dầu (giai đoạn C — đa tài sản)
===================================

GET /api/v1/petrol/overview — giá xăng dầu bán lẻ hiện tại, kỳ điều hành kế tiếp,
giá dầu thế giới (Brent/WTI) và ghi chú cơ chế điều hành.
GET /api/v1/petrol/history — lịch sử giá xăng VN + Brent quy chiếu.

Logic ở src/services/petrol_service.py.
"""

import logging

from fastapi import APIRouter, Query

from api.v1.schemas.petrol import PetrolHistoryResponse, PetrolOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=PetrolOverviewResponse)
def petrol_overview() -> PetrolOverviewResponse:
    """Tổng quan xăng dầu (cache 30 phút trong tiến trình)."""
    from src.services.petrol_service import get_petrol_overview

    return PetrolOverviewResponse(**get_petrol_overview())


@router.get("/history", response_model=PetrolHistoryResponse)
def petrol_history(
    days: int = Query(365, ge=90, le=3000, description="Số ngày lịch sử"),
) -> PetrolHistoryResponse:
    """Lịch sử giá xăng dầu VN + dầu thế giới (cache 6 giờ)."""
    from src.services.petrol_service import get_petrol_history

    return PetrolHistoryResponse(**get_petrol_history(days=days))
