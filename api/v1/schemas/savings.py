# -*- coding: utf-8 -*-
"""Schema cho trang Tiết Kiệm (giai đoạn B — đa tài sản)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SavingsBank(BaseModel):
    """Lãi suất gửi tiết kiệm của một ngân hàng (theo thứ tự kỳ hạn `terms`)."""

    name: str
    symbol: Optional[str] = None
    rates: List[Optional[float]] = Field(default_factory=list)  # %/năm, None nếu không công bố


class SavingsBest(BaseModel):
    """Lãi suất tốt nhất cho một kỳ hạn."""

    term: int
    bank: str
    rate: float


class SavingsOverviewResponse(BaseModel):
    """Bảng lãi suất tiết kiệm theo ngân hàng × kỳ hạn."""

    generated_at: str
    terms: List[int] = Field(default_factory=list, description="Các kỳ hạn (tháng)")
    banks: List[SavingsBank] = Field(default_factory=list)
    best: List[SavingsBest] = Field(default_factory=list)
    sbv_policy_rate: Optional[float] = Field(None, description="Lãi suất điều hành SBV (%/năm)")
    note: Optional[str] = None
    data_warning: Optional[str] = None
