# -*- coding: utf-8 -*-
"""Schema cho trang Vàng (Phase A — đa tài sản)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class GoldType(BaseModel):
    """Một loại vàng trong nước (BTMC), giá VND/lượng."""

    name: str
    karat: Optional[str] = None
    buy: Optional[float] = None
    sell: Optional[float] = None


class GoldHistoryPoint(BaseModel):
    """Một mốc thời gian: giá SJC + giá thế giới quy đổi (VND/lượng)."""

    date: str
    sjc: Optional[float] = None
    world: Optional[float] = None
    premium_pct: Optional[float] = None


class GoldHistoryResponse(BaseModel):
    """Lịch sử giá vàng trong nước (SJC) và thế giới quy đổi."""

    generated_at: str
    days: int = 180
    usd_vnd: Optional[float] = None
    points: List[GoldHistoryPoint] = Field(default_factory=list)
    premium_current_pct: Optional[float] = Field(None, description="Chênh lệch hiện tại (%)")
    premium_avg_pct: Optional[float] = Field(None, description="Chênh lệch trung bình trong kỳ (%)")
    premium_min_pct: Optional[float] = None
    premium_max_pct: Optional[float] = None
    data_warning: Optional[str] = None


class GoldOverviewResponse(BaseModel):
    """Tổng hợp giá vàng + chênh lệch SJC so với thế giới quy đổi."""

    generated_at: str

    # Vàng miếng SJC trong nước (VND/lượng)
    sjc_name: Optional[str] = None
    sjc_branch: Optional[str] = None
    sjc_buy: Optional[float] = Field(None, description="Giá mua vào SJC (VND/lượng)")
    sjc_sell: Optional[float] = Field(None, description="Giá bán ra SJC (VND/lượng)")
    sjc_date: Optional[str] = None
    bid_ask_spread: Optional[float] = Field(None, description="Chênh lệch mua-bán (VND/lượng)")

    # Vàng thế giới + tỷ giá
    world_usd_oz: Optional[float] = Field(None, description="Giá vàng thế giới (USD/troy oz)")
    world_source: Optional[str] = None
    usd_vnd: Optional[float] = Field(None, description="Tỷ giá USD/VND (giá bán VCB)")

    # Quy đổi + chênh lệch
    world_per_luong_vnd: Optional[float] = Field(
        None, description="Giá vàng thế giới quy đổi (VND/lượng)"
    )
    premium_vnd: Optional[float] = Field(
        None, description="Chênh lệch SJC so với thế giới quy đổi (VND/lượng)"
    )
    premium_pct: Optional[float] = Field(None, description="Chênh lệch theo % giá thế giới")
    assessment: Optional[str] = Field(None, description="Nhận định nhanh mức chênh lệch")

    gold_types: List[GoldType] = Field(default_factory=list, description="Bảng các loại vàng trong nước")

    data_warning: Optional[str] = None
