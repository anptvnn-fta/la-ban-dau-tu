# -*- coding: utf-8 -*-
"""
===================================
API Trái Phiếu & lãi suất điều hành (giai đoạn B)
===================================

GET /api/v1/bond/overview — SBV vs Fed, US10Y (live), VN10Y (tham khảo) + chênh lệch.
GET /api/v1/bond/history — lịch sử US10Y.

Logic ở src/services/bond_service.py.
"""

import logging

from fastapi import APIRouter, Query

from api.v1.schemas.bond import BondHistoryResponse, BondOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=BondOverviewResponse)
def bond_overview() -> BondOverviewResponse:
    """Tổng quan lãi suất & trái phiếu (cache 30 phút)."""
    from src.services.bond_service import get_bond_overview

    return BondOverviewResponse(**get_bond_overview())


@router.get("/history", response_model=BondHistoryResponse)
def bond_history(
    days: int = Query(365, ge=90, le=1825, description="Số ngày lịch sử"),
) -> BondHistoryResponse:
    """Lịch sử lợi suất trái phiếu Mỹ 10 năm (cache 6 giờ)."""
    from src.services.bond_service import get_bond_history

    return BondHistoryResponse(**get_bond_history(days=days))
