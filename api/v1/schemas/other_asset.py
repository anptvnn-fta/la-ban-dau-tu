# -*- coding: utf-8 -*-
"""Schema cho Tài sản khác trong danh mục (vàng / tiết kiệm / trái phiếu)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class OtherAssetCreateRequest(BaseModel):
    account_id: int
    asset_class: str = Field(..., description="vang | tiet_kiem | trai_phieu")
    label: str = Field(..., description="Tên/nhãn tài sản")
    value: float = Field(..., ge=0, description="Giá trị hiện tại (VND)")
    interest_rate: Optional[float] = Field(None, description="Lãi suất %/năm (tiết kiệm/trái phiếu)")
    maturity_date: Optional[str] = Field(None, description="Ngày đáo hạn YYYY-MM-DD")
    note: Optional[str] = None


class OtherAssetUpdateRequest(BaseModel):
    asset_class: Optional[str] = None
    label: Optional[str] = None
    value: Optional[float] = Field(None, ge=0)
    interest_rate: Optional[float] = None
    maturity_date: Optional[str] = None
    note: Optional[str] = None


class OtherAssetItem(BaseModel):
    id: int
    account_id: int
    asset_class: str
    asset_class_label: str
    label: str
    value: float
    interest_rate: Optional[float] = None
    maturity_date: Optional[str] = None
    note: Optional[str] = None
    updated_at: Optional[str] = None


class OtherAssetClassTotal(BaseModel):
    asset_class: str
    label: str
    value: float


class OtherAssetListResponse(BaseModel):
    account_id: int
    items: List[OtherAssetItem] = Field(default_factory=list)
    total_value: float = 0.0
    by_class: List[OtherAssetClassTotal] = Field(default_factory=list)
