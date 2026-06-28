# -*- coding: utf-8 -*-
"""Schema cho trang Xăng Dầu (giai đoạn C — đa tài sản)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PetrolFuel(BaseModel):
    """Một mặt hàng xăng dầu (đồng/lít)."""

    code: str
    name: str
    price: Optional[float] = None
    prev_price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None


class PetrolOverviewResponse(BaseModel):
    """Giá xăng dầu hiện tại + dầu thế giới + kỳ điều hành."""

    generated_at: str
    effective_date: Optional[str] = None
    next_adjustment: Optional[str] = None
    fuels: List[PetrolFuel] = Field(default_factory=list)
    brent_usd: Optional[float] = Field(None, description="Dầu Brent (USD/thùng)")
    wti_usd: Optional[float] = Field(None, description="Dầu WTI (USD/thùng)")
    cycle_note: Optional[str] = None
    data_warning: Optional[str] = None


class PetrolHistoryPoint(BaseModel):
    """Một mốc: giá xăng VN (đồng/lít) + Brent quy chiếu (USD/thùng)."""

    date: str
    e5: Optional[float] = None
    ron95: Optional[float] = None
    do: Optional[float] = None
    brent: Optional[float] = None


class PetrolHistoryResponse(BaseModel):
    """Lịch sử giá xăng dầu VN và dầu thế giới."""

    generated_at: str
    days: int = 365
    points: List[PetrolHistoryPoint] = Field(default_factory=list)
    data_warning: Optional[str] = None
