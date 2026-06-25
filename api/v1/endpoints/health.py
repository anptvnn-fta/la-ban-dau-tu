# -*- coding: utf-8 -*-
"""
===================================
API kiểm tra sức khỏe dịch vụ
===================================

Trách nhiệm:
1. Cung cấp endpoint /api/v1/health để kiểm tra sức khỏe
2. Phục vụ bộ cân bằng tải và hệ thống giám sát
"""

from datetime import datetime

from fastapi import APIRouter

from api.v1.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Endpoint kiểm tra sức khỏe dịch vụ

    Dùng cho bộ cân bằng tải hoặc hệ thống giám sát kiểm tra trạng thái dịch vụ

    Returns:
        HealthResponse: Chứa trạng thái dịch vụ và timestamp
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )
