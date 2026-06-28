# -*- coding: utf-8 -*-
"""
===================================
API Vàng (Phase A — đa tài sản)
===================================

GET /api/v1/gold/overview — giá vàng SJC, giá vàng thế giới, tỷ giá USD/VND
và chênh lệch (premium) SJC so với thế giới quy đổi sang VND/lượng.

Logic lấy dữ liệu + tính toán + cache nằm ở src/services/gold_service.py.
"""

import logging

from fastapi import APIRouter, Query

from api.v1.schemas.gold import GoldHistoryResponse, GoldOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview", response_model=GoldOverviewResponse)
def gold_overview() -> GoldOverviewResponse:
    """Tổng quan vàng + bảng loại vàng (cache 5 phút trong tiến trình)."""
    from src.services.gold_service import get_gold_overview

    return GoldOverviewResponse(**get_gold_overview())


@router.get("/history", response_model=GoldHistoryResponse)
def gold_history(
    days: int = Query(180, ge=30, le=365, description="Số ngày lịch sử"),
    step_days: int = Query(14, ge=7, le=30, description="Khoảng cách giữa các mốc"),
) -> GoldHistoryResponse:
    """Lịch sử giá vàng SJC + thế giới quy đổi (VND/lượng). Cache 6 giờ.

    Lần gọi nguội lấy dữ liệu nhiều mốc nên có thể mất vài giây.
    """
    from src.services.gold_service import get_gold_history

    return GoldHistoryResponse(**get_gold_history(days=days, step_days=step_days))
