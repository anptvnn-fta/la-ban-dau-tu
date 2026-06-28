# -*- coding: utf-8 -*-
"""Schema đầu vào cho Tư vấn đầu tư (26 trường hồ sơ).

Để trả thông báo lỗi tiếng Việt thân thiện, mọi trường đều Optional ở tầng
Pydantic; việc kiểm tra bắt buộc do tu_van_service đảm nhiệm.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TuVanInput(BaseModel):
    # Nhân khẩu học
    nam_sinh: Optional[int] = None
    gioi_tinh: Optional[str] = None
    hon_nhan: Optional[str] = None
    nguoi_phu_thuoc: Optional[str] = None
    hoc_van: Optional[str] = None
    nghe_nghiep: Optional[str] = None
    giai_doan_cuoc_doi: Optional[str] = None

    # Tài chính
    thu_nhap_thang: Optional[str] = None
    ty_le_chi_tieu: Optional[str] = None
    tai_san_rong: Optional[str] = None
    quy_du_phong: Optional[str] = None
    ganh_no: Optional[str] = None
    von_dau_tu: Optional[str] = None
    tai_san_dang_co: Optional[List[str]] = Field(default_factory=list)

    # Mục tiêu
    muc_tieu_cu_the: Optional[List[str]] = Field(default_factory=list)
    thoi_gian_muc_tieu_nam: Optional[int] = None

    # Rủi ro (Chương 4)
    muc_tieu_dau_tu: Optional[str] = None
    thoi_gian_dau_tu: Optional[str] = None
    kinh_nghiem: Optional[str] = None
    loi_nhuan_mong_muon: Optional[str] = None
    muc_rui_ro_chap_nhan: Optional[str] = None

    # Hành vi
    phan_ung_thi_truong_giam: Optional[str] = None
    tai_san_ua_thich: Optional[str] = None
    thoi_gian_nam_giu: Optional[str] = None
    tan_suat_theo_doi: Optional[str] = None
    hieu_biet_tai_chinh: Optional[str] = None

    @field_validator("nam_sinh", "thoi_gian_muc_tieu_nam", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        # Giao diện gửi chuỗi rỗng khi ô số trống → coi như None để tầng service
        # trả lỗi tiếng Việt thân thiện thay vì 422 của Pydantic.
        if v == "" or v is None:
            return None
        return v
