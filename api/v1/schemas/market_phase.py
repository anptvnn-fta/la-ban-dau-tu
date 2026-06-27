# -*- coding: utf-8 -*-
"""Market phase summary schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarketPhaseValue = Literal[
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
]


class MarketPhaseSummary(BaseModel):
    """Low-sensitivity market phase metadata exposed on report meta."""

    market: Optional[str] = Field(None, description="Khu vực thị trường")
    phase: MarketPhaseValue = Field(..., description="Giai đoạn thị trường")
    market_local_time: Optional[str] = Field(None, description="Giờ địa phương của thị trường")
    session_date: Optional[str] = Field(None, description="Ngày giao dịch theo giờ địa phương")
    effective_daily_bar_date: Optional[str] = Field(None, description="Ngày nến ngày hoàn chỉnh gần nhất có thể tái sử dụng")
    is_trading_day: Optional[bool] = Field(None, description="Có phải ngày giao dịch không")
    is_market_open_now: Optional[bool] = Field(None, description="Thị trường hiện có đang mở cửa không")
    is_partial_bar: Optional[bool] = Field(None, description="Nến ngày gần nhất có thể chưa hoàn chỉnh không")
    minutes_to_open: Optional[int] = Field(None, description="Số phút đến khi thị trường mở cửa")
    minutes_to_close: Optional[int] = Field(None, description="Số phút đến khi thị trường đóng cửa")
    trigger_source: Optional[str] = Field(None, description="Nguồn kích hoạt")
    analysis_intent: Optional[str] = Field(None, description="Mục đích phân tích")
    warnings: List[str] = Field(default_factory=list, description="Mã cảnh báo suy giảm suy luận giai đoạn")
