# -*- coding: utf-8 -*-
"""
===================================
Các model liên quan đến dữ liệu cổ phiếu
===================================

Trách nhiệm:
1. Định nghĩa model giá thị trường thời gian thực
2. Định nghĩa model dữ liệu nến K theo lịch sử
"""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """Giá thị trường thời gian thực của cổ phiếu"""

    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    current_price: float = Field(..., description="Giá hiện tại")
    change: Optional[float] = Field(None, description="Thay đổi giá")
    change_percent: Optional[float] = Field(None, description="Thay đổi giá (%)")
    open: Optional[float] = Field(None, description="Giá mở cửa")
    high: Optional[float] = Field(None, description="Giá cao nhất")
    low: Optional[float] = Field(None, description="Giá thấp nhất")
    prev_close: Optional[float] = Field(None, description="Giá đóng cửa phiên trước")
    volume: Optional[float] = Field(None, description="Khối lượng khớp lệnh (cổ phiếu)")
    amount: Optional[float] = Field(None, description="Giá trị khớp lệnh (VND)")
    update_time: Optional[str] = Field(None, description="Thời điểm cập nhật")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "FPT.VN",
            "stock_name": "Công ty Cổ phần FPT",
            "current_price": 120000,
            "change": 1500,
            "change_percent": 1.27,
            "open": 118500,
            "high": 121000,
            "low": 118000,
            "prev_close": 118500,
            "volume": 2500000,
            "amount": 297500000000,
            "update_time": "2024-01-01T15:00:00"
        }
    })


class KLineData(BaseModel):
    """Điểm dữ liệu nến K"""

    date: str = Field(..., description="Ngày")
    open: float = Field(..., description="Giá mở cửa")
    high: float = Field(..., description="Giá cao nhất")
    low: float = Field(..., description="Giá thấp nhất")
    close: float = Field(..., description="Giá đóng cửa")
    volume: Optional[float] = Field(None, description="Khối lượng")
    amount: Optional[float] = Field(None, description="Giá trị giao dịch")
    change_percent: Optional[float] = Field(None, description="Thay đổi (%)")
    # Chỉ báo kỹ thuật (chỉ điền khi indicators=true)
    ma5: Optional[float] = Field(None, description="MA5")
    ma10: Optional[float] = Field(None, description="MA10")
    ma20: Optional[float] = Field(None, description="MA20")
    rsi: Optional[float] = Field(None, description="RSI(14)")
    macd: Optional[float] = Field(None, description="MACD")
    macd_signal: Optional[float] = Field(None, description="Đường tín hiệu MACD")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "close": 1800.00,
            "volume": 10000000,
            "amount": 18000000000,
            "change_percent": 0.84
        }
    })


class ExtractItem(BaseModel):
    """Một kết quả trích xuất (mã, tên, độ tin cậy)"""

    code: Optional[str] = Field(None, description="Mã cổ phiếu; None nếu phân tích thất bại")
    name: Optional[str] = Field(None, description="Tên cổ phiếu (nếu có)")
    confidence: str = Field("medium", description="Độ tin cậy: high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """Phản hồi trích xuất mã cổ phiếu từ ảnh"""

    codes: List[str] = Field(..., description="Danh sách mã cổ phiếu đã trích xuất (đã khử trùng, tương thích ngược)")
    items: List[ExtractItem] = Field(default_factory=list, description="Chi tiết kết quả trích xuất (mã + tên + độ tin cậy)")
    raw_text: Optional[str] = Field(None, description="Phản hồi thô từ LLM (dùng để gỡ lỗi)")


class StockHistoryResponse(BaseModel):
    """Phản hồi lịch sử giá cổ phiếu"""

    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    period: str = Field(..., description="Chu kỳ nến K")
    data: List[KLineData] = Field(default_factory=list, description="Danh sách dữ liệu nến K")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "FPT.VN",
            "stock_name": "Công ty Cổ phần FPT",
            "period": "daily",
            "data": []
        }
    })


class ForeignFlowItem(BaseModel):
    """Giao dịch khối ngoại theo ngày."""

    date: str = Field(..., description="Ngày giao dịch")
    net_volume: Optional[float] = Field(None, description="Khối lượng mua/bán ròng (cổ phiếu)")
    net_value: Optional[float] = Field(None, description="Giá trị mua/bán ròng (VND)")
    buy_volume: Optional[float] = Field(None, description="Khối lượng mua")
    sell_volume: Optional[float] = Field(None, description="Khối lượng bán")
    room_pct: Optional[float] = Field(None, description="Tỷ lệ room còn lại")


class ForeignFlowResponse(BaseModel):
    """Chuỗi giao dịch khối ngoại của một mã."""

    stock_code: str = Field(..., description="Mã cổ phiếu")
    data: List[ForeignFlowItem] = Field(default_factory=list, description="Chuỗi theo ngày")
