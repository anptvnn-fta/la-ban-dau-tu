# -*- coding: utf-8 -*-
"""
===================================
Schema cho Tổng Quan Thị Trường (U3)
===================================

Dữ liệu hiển thị ở trang "Tổng Quan": chỉ số chính, top tăng/giảm,
độ rộng thị trường và hiệu suất nhóm ngành (trong rổ VN30).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class MarketIndexItem(BaseModel):
    """Một chỉ số thị trường (VN-Index, VN30, HNX-Index, UPCoM)."""

    code: str
    name: str
    current: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None


class MarketMoverItem(BaseModel):
    """Một mã trong bảng top tăng/giảm."""

    code: str
    name: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    value: Optional[float] = None  # Giá trị khớp luỹ kế (VND)


class SectorItem(BaseModel):
    """Hiệu suất bình quân một nhóm ngành (trong rổ VN30)."""

    name: str
    change_pct: Optional[float] = None
    count: int = 0
    codes: List[str] = Field(default_factory=list)


class MarketBreadth(BaseModel):
    """Độ rộng thị trường trong rổ tham chiếu."""

    advancers: int = 0
    decliners: int = 0
    unchanged: int = 0
    universe_size: int = 0
    total_value: Optional[float] = None  # Tổng giá trị khớp (VND)


class MarketOverviewResponse(BaseModel):
    """Phản hồi tổng hợp cho trang Tổng Quan Thị Trường."""

    generated_at: str
    universe_label: str = "VN30"
    indices: List[MarketIndexItem] = Field(default_factory=list)
    breadth: Optional[MarketBreadth] = None
    top_gainers: List[MarketMoverItem] = Field(default_factory=list)
    top_losers: List[MarketMoverItem] = Field(default_factory=list)
    sectors: List[SectorItem] = Field(default_factory=list)
    data_warning: Optional[str] = None  # Thông báo nếu một phần dữ liệu không lấy được
