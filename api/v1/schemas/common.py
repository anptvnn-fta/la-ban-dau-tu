# -*- coding: utf-8 -*-
"""
===================================
Các model phản hồi chung
===================================

Trách nhiệm:
1. Định nghĩa các model phản hồi chung (HealthResponse, ErrorResponse, ...)
2. Cung cấp định dạng phản hồi thống nhất
"""

from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field


class RootResponse(BaseModel):
    """Phản hồi của route gốc API"""
    
    message: str = Field(..., description="Trạng thái hoạt động của API", json_schema_extra={"example": "Daily Stock Analysis API is running"})
    version: Optional[str] = Field(None, description="Phiên bản API", json_schema_extra={"example": "1.0.0"})
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "message": "Daily Stock Analysis API is running",
            "version": "1.0.0"
        }
    })


class HealthResponse(BaseModel):
    """Phản hồi kiểm tra sức khỏe dịch vụ"""
    
    status: str = Field(..., description="Trạng thái dịch vụ", json_schema_extra={"example": "ok"})
    timestamp: Optional[str] = Field(None, description="Dấu thời gian")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "ok",
            "timestamp": "2024-01-01T12:00:00"
        }
    })


class ErrorResponse(BaseModel):
    """Phản hồi lỗi"""
    
    error: str = Field(..., description="Loại lỗi", json_schema_extra={"example": "validation_error"})
    message: str = Field(..., description="Chi tiết lỗi", json_schema_extra={"example": "Tham số yêu cầu không hợp lệ"})
    detail: Optional[Any] = Field(None, description="Thông tin lỗi bổ sung")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "not_found",
            "message": "Tài nguyên không tồn tại",
            "detail": None
        }
    })


class SuccessResponse(BaseModel):
    """Phản hồi thành công chung"""
    
    success: bool = Field(True, description="Thao tác có thành công không")
    message: Optional[str] = Field(None, description="Thông báo thành công")
    data: Optional[Any] = Field(None, description="Dữ liệu phản hồi")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "Thao tác thành công",
            "data": None
        }
    })
