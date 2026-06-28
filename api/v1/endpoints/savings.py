# -*- coding: utf-8 -*-
"""
===================================
API Tiết Kiệm (giai đoạn B — đa tài sản)
===================================

GET /api/v1/savings/overview — bảng lãi suất gửi tiết kiệm theo ngân hàng × kỳ hạn,
lãi suất tốt nhất từng kỳ hạn và bối cảnh lãi suất điều hành SBV.

Logic ở src/services/savings_service.py.
"""

import logging

from fastapi import APIRouter

from api.v1.schemas.savings import SavingsOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=SavingsOverviewResponse)
def savings_overview() -> SavingsOverviewResponse:
    """Bảng lãi suất tiết kiệm (cache 1 giờ trong tiến trình)."""
    from src.services.savings_service import get_savings_overview

    return SavingsOverviewResponse(**get_savings_overview())
