# -*- coding: utf-8 -*-
"""
===================================
Các model liên quan đến phân tích
===================================

Trách nhiệm:
1. Định nghĩa model yêu cầu và phản hồi phân tích
2. Định nghĩa model trạng thái tác vụ
3. Định nghĩa các model liên quan đến hàng đợi tác vụ bất đồng bộ
"""

from typing import Optional, List, Any, Literal
from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN


class TaskStatusEnum(str, Enum):
    """Enum trạng thái tác vụ"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


AnalysisPhase = Literal["auto", "premarket", "intraday", "postmarket"]


class AnalyzeRequest(BaseModel):
    """Tham số yêu cầu phân tích"""

    stock_code: Optional[str] = Field(
        None,
        description="Mã một cổ phiếu đơn lẻ",
        json_schema_extra={"example": "VCB.VN"},
    )
    stock_codes: Optional[List[str]] = Field(
        None,
        description="Danh sách nhiều mã cổ phiếu (chọn một trong hai: stock_code hoặc stock_codes)",
        json_schema_extra={"example": ["VCB.VN", "FPT.VN"]},
    )
    report_type: str = Field(
        "detailed",
        description="Loại báo cáo: simple(tóm tắt) / detailed(đầy đủ) / full(đầy đủ) / brief(ngắn gọn)",
        pattern="^(simple|detailed|full|brief)$",
    )
    force_refresh: bool = Field(
        False,
        description="Bắt buộc làm mới dữ liệu (bỏ qua cache)"
    )
    async_mode: bool = Field(
        False,
        description="Sử dụng chế độ bất đồng bộ"
    )
    analysis_phase: AnalysisPhase = Field(
        "auto",
        description="Giai đoạn phân tích: auto(tự động) / premarket(trước giờ) / intraday(trong giờ) / postmarket(sau giờ)",
    )
    stock_name: Optional[str] = Field(
        None,
        description="Tên cổ phiếu người dùng đã chọn (cung cấp khi dùng tự động hoàn thành)",
        json_schema_extra={"example": "Ngân hàng Ngoại Thương"},
    )
    original_query: Optional[str] = Field(
        None,
        description="Chuỗi gốc người dùng nhập (ví dụ: vcb, ngoaiThuong, VCB.VN)",
        json_schema_extra={"example": "vcb"},
    )
    selection_source: Optional[str] = Field(
        None,
        description="Nguồn chọn cổ phiếu: manual(nhập tay) | autocomplete(tự động hoàn thành) | import(nhập khẩu) | image(nhận dạng ảnh)",
        pattern=SELECTION_SOURCE_PATTERN,
        json_schema_extra={"example": "autocomplete"},
    )
    notify: bool = Field(
        True,
        description="Gửi thông báo đẩy sau khi phân tích xong (Telegram/email...)"
    )
    report_language: Optional[Literal["zh", "en", "vi"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="Ngôn ngữ báo cáo cho lần phân tích này; không truyền thì dùng REPORT_LANGUAGE toàn cục",
    )
    skills: Optional[List[str]] = Field(
        None,
        validation_alias=AliasChoices("skills", "strategies"),
        description="Danh sách ID chiến lược (skill) dùng cho lần phân tích này; tương thích trường legacy strategies",
        json_schema_extra={"example": ["bull_trend", "growth_quality"]},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "VCB.VN",
            "report_type": "detailed",
            "force_refresh": False,
            "async_mode": False,
            "analysis_phase": "auto",
            "stock_name": "Ngân hàng Ngoại Thương",
            "original_query": "vcb",
            "selection_source": "autocomplete",
            "notify": True,
            "report_language": "vi",
            "skills": ["bull_trend"]
        }
    })


class MarketReviewRequest(BaseModel):
    """Tham số kích hoạt tổng kết thị trường."""

    send_notification: bool = Field(
        True,
        description="Gửi thông báo đẩy sau khi hoàn thành tổng kết thị trường",
    )
    report_language: Optional[Literal["zh", "en", "vi"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="Ngôn ngữ báo cáo tổng kết thị trường lần này; không truyền thì dùng REPORT_LANGUAGE toàn cục",
    )


class MarketReviewAccepted(BaseModel):
    """Phản hồi xác nhận nhận tác vụ tổng kết thị trường nền."""

    status: str = Field("accepted", description="Trạng thái gửi tác vụ")
    message: str = Field(..., description="Thông báo kết quả")
    send_notification: bool = Field(..., description="Có gửi thông báo sau khi hoàn thành không")
    trace_id: Optional[str] = Field(
        None,
        description="Trace ID chẩn đoán của tác vụ nền này",
    )
    task_id: Optional[str] = Field(
        None,
        description="ID tác vụ (chỉ trả về khi tác vụ thực sự được gửi)",
    )


class AnalysisResultResponse(BaseModel):
    """Model phản hồi kết quả phân tích"""

    query_id: str = Field(..., description="Định danh duy nhất của bản ghi phân tích")
    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    report: Optional[Any] = Field(None, description="Báo cáo phân tích")
    diagnostic_summary: Optional[Any] = Field(None, description="Tóm tắt chẩn đoán quá trình chạy")
    created_at: str = Field(..., description="Thời điểm tạo")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_id": "abc123def456",
            "stock_code": "VCB.VN",
            "stock_name": "Ngân hàng Ngoại Thương",
            "report": {
                "summary": {
                    "sentiment_score": 75,
                    "operation_advice": "Giữ"
                }
            },
            "created_at": "2024-01-01T12:00:00"
        }
    })


class TaskAccepted(BaseModel):
    """Phản hồi xác nhận nhận tác vụ bất đồng bộ"""

    task_id: str = Field(..., description="ID tác vụ, dùng để truy vấn trạng thái")
    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    status: str = Field(
        ...,
        description="Trạng thái tác vụ",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="Thông báo gợi ý")
    analysis_phase: AnalysisPhase = Field("auto", description="Giai đoạn phân tích được yêu cầu")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "pending",
            "message": "Đã nhận tác vụ phân tích",
            "analysis_phase": "auto"
        }
    })


class BatchTaskAcceptedItem(BaseModel):
    """Mục được gửi thành công trong tác vụ bất đồng bộ hàng loạt."""

    task_id: str = Field(..., description="ID tác vụ, dùng để truy vấn trạng thái")
    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    status: str = Field(
        ...,
        description="Trạng thái tác vụ",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="Thông báo gợi ý")
    analysis_phase: AnalysisPhase = Field("auto", description="Giai đoạn phân tích được yêu cầu")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "stock_code": "VCB.VN",
            "status": "pending",
            "message": "Đã thêm vào hàng đợi phân tích: VCB.VN",
            "analysis_phase": "auto"
        }
    })


class BatchDuplicateTaskItem(BaseModel):
    """Mục gửi trùng lặp trong tác vụ bất đồng bộ hàng loạt."""

    stock_code: str = Field(..., description="Mã cổ phiếu")
    existing_task_id: str = Field(..., description="ID tác vụ đang tồn tại")
    message: str = Field(..., description="Thông báo lỗi")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "VCB.VN",
            "existing_task_id": "task_existing_123",
            "message": "Cổ phiếu VCB.VN đang được phân tích (task_id: task_existing_123)"
        }
    })


class BatchTaskAcceptedResponse(BaseModel):
    """Phản hồi xác nhận nhận tác vụ bất đồng bộ hàng loạt."""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="Danh sách tác vụ đã gửi thành công")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="Danh sách tác vụ bị bỏ qua do trùng lặp")
    message: str = Field(..., description="Thông tin tổng hợp")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "accepted": [
                {
                    "task_id": "task_abc123",
                    "stock_code": "VCB.VN",
                    "status": "pending",
                    "message": "Đã thêm vào hàng đợi phân tích: VCB.VN",
                    "analysis_phase": "auto"
                }
            ],
            "duplicates": [
                {
                    "stock_code": "FPT.VN",
                    "existing_task_id": "task_existing_456",
                    "message": "Cổ phiếu FPT.VN đang được phân tích (task_id: task_existing_456)"
                }
            ],
            "message": "Đã gửi 1 tác vụ, bỏ qua 1 trùng lặp"
        }
    })


class TaskStatus(BaseModel):
    """Model trạng thái tác vụ"""

    task_id: str = Field(..., description="ID tác vụ")
    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    status: TaskStatusEnum = Field(
        ...,
        description="Trạng thái tác vụ",
    )
    progress: Optional[int] = Field(
        None,
        description="Tiến độ hoàn thành (%): 0-100",
        ge=0,
        le=100
    )
    result: Optional[AnalysisResultResponse] = Field(
        None,
        description="Kết quả phân tích (chỉ có khi trạng thái là completed)"
    )
    market_review_report: Optional[str] = Field(
        None,
        description="Nội dung báo cáo tổng kết thị trường (chỉ có với tác vụ tổng kết thị trường)",
    )
    market_review_payload: Optional[Any] = Field(
        None,
        description="Payload tổng kết thị trường có cấu trúc dành cho API/Web.",
    )
    error: Optional[str] = Field(
        None,
        description="Thông báo lỗi (chỉ có khi trạng thái là failed)"
    )
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    original_query: Optional[str] = Field(None, description="Chuỗi gốc người dùng nhập")
    selection_source: Optional[str] = Field(
        None,
        description="Nguồn chọn cổ phiếu",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: Optional[AnalysisPhase] = Field(
        None,
        description="Giai đoạn phân tích được yêu cầu; có thể rỗng với bản ghi lịch sử DB cũ không có trường này",
    )
    skills: Optional[List[str]] = Field(None, description="Danh sách ID chiến lược (skill) dùng trong tác vụ này")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "completed",
            "progress": 100,
            "result": None,
            "market_review_report": None,
            "error": None,
            "stock_name": "Ngân hàng Ngoại Thương",
            "original_query": "vcb",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskInfo(BaseModel):
    """
    Model chi tiết tác vụ

    Dùng trong danh sách tác vụ và giao sự kiện SSE
    """

    task_id: str = Field(..., description="ID tác vụ")
    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    status: TaskStatusEnum = Field(..., description="Trạng thái tác vụ")
    progress: int = Field(0, description="Tiến độ hoàn thành (%): 0-100", ge=0, le=100)
    message: Optional[str] = Field(None, description="Thông báo trạng thái")
    report_type: str = Field("detailed", description="Loại báo cáo")
    created_at: str = Field(..., description="Thời điểm tạo")
    started_at: Optional[str] = Field(None, description="Thời điểm bắt đầu thực thi")
    completed_at: Optional[str] = Field(None, description="Thời điểm hoàn thành")
    error: Optional[str] = Field(None, description="Thông báo lỗi (chỉ có khi trạng thái là failed)")
    original_query: Optional[str] = Field(None, description="Chuỗi gốc người dùng nhập")
    selection_source: Optional[str] = Field(
        None,
        description="Nguồn chọn cổ phiếu",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: AnalysisPhase = Field("auto", description="Giai đoạn phân tích được yêu cầu")
    skills: Optional[List[str]] = Field(None, description="Danh sách ID chiến lược (skill) dùng trong tác vụ này")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "abc123def456",
            "stock_code": "VCB.VN",
            "stock_name": "Ngân hàng Ngoại Thương",
            "status": "processing",
            "progress": 50,
            "message": "Đang phân tích...",
            "report_type": "detailed",
            "created_at": "2026-02-05T10:30:00",
            "started_at": "2026-02-05T10:30:01",
            "completed_at": None,
            "error": None,
            "original_query": "vcb",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskListResponse(BaseModel):
    """Model phản hồi danh sách tác vụ"""

    total: int = Field(..., description="Tổng số tác vụ")
    pending: int = Field(..., description="Số tác vụ đang chờ")
    processing: int = Field(..., description="Số tác vụ đang xử lý")
    tasks: List[TaskInfo] = Field(..., description="Danh sách tác vụ")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 3,
            "pending": 1,
            "processing": 2,
            "tasks": []
        }
    })


class DuplicateTaskErrorResponse(BaseModel):
    """Model phản hồi lỗi tác vụ trùng lặp"""

    error: str = Field("duplicate_task", description="Loại lỗi")
    message: str = Field(..., description="Thông báo lỗi")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    existing_task_id: str = Field(..., description="ID tác vụ đang tồn tại")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "duplicate_task",
            "message": "Cổ phiếu VCB.VN đang được phân tích",
            "stock_code": "VCB.VN",
            "existing_task_id": "abc123def456"
        }
    })
