# -*- coding: utf-8 -*-
"""Schema cho trang Trái Phiếu & lãi suất điều hành (giai đoạn B)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class BondOverviewResponse(BaseModel):
    """Lãi suất điều hành (SBV/Fed) + lợi suất trái phiếu (US10Y live, VN10Y tham khảo)."""

    generated_at: str
    sbv_policy_rate: Optional[float] = Field(None, description="Lãi suất điều hành SBV (%/năm)")
    fed_low: Optional[float] = None
    fed_high: Optional[float] = None
    us_yield: Optional[float] = Field(None, description="Lợi suất trái phiếu Mỹ 10 năm (%/năm)")
    vn10y_ref: Optional[float] = Field(None, description="Lợi suất TPCP VN 10 năm — THAM KHẢO")
    spread_sbv_fed: Optional[float] = None
    spread_vn_us: Optional[float] = None
    note: Optional[str] = None
    data_warning: Optional[str] = None


class BondHistoryPoint(BaseModel):
    date: str
    us_yield: Optional[float] = None


class BondHistoryResponse(BaseModel):
    """Lịch sử lợi suất trái phiếu Mỹ 10 năm."""

    generated_at: str
    days: int = 365
    points: List[BondHistoryPoint] = Field(default_factory=list)
    data_warning: Optional[str] = None
