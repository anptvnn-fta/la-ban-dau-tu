# -*- coding: utf-8 -*-
"""
===================================
Các model liên quan đến lịch sử
===================================

Trách nhiệm:
1. Định nghĩa model danh sách và chi tiết lịch sử
2. Định nghĩa model báo cáo phân tích đầy đủ
"""

from typing import Optional, List, Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.v1.schemas.market_phase import MarketPhaseSummary
from src.schemas.decision_action import DecisionAction


class HistoryItem(BaseModel):
    """Tóm tắt bản ghi lịch sử (dùng để hiển thị trong danh sách)"""

    id: Optional[int] = Field(None, description="Khoá chính ID của bản ghi lịch sử phân tích")
    query_id: str = Field(..., description="Query_id liên kết bản ghi phân tích (có thể trùng khi phân tích hàng loạt)")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    report_type: Optional[str] = Field(None, description="Loại báo cáo")
    trend_prediction: Optional[str] = Field(None, description="Dự báo xu hướng")
    analysis_summary: Optional[str] = Field(None, description="Tóm tắt phân tích")
    sentiment_score: Optional[int] = Field(
        None,
        description="Điểm tâm lý thị trường (dữ liệu cũ có thể nằm ngoài 0-100, không ràng buộc khi đọc)",
    )
    operation_advice: Optional[str] = Field(None, description="Khuyến nghị thao tác")
    action: Optional[DecisionAction] = Field(None, description="Hành động khuyến nghị có cấu trúc (taxonomy)")
    action_label: Optional[str] = Field(None, description="Nhãn hiển thị của hành động khuyến nghị")
    current_price: Optional[float] = Field(None, description="Giá cổ phiếu tại thời điểm phân tích")
    change_pct: Optional[float] = Field(None, description="Thay đổi giá tại thời điểm phân tích (%)")
    volume_ratio: Optional[float] = Field(None, description="Tỷ lệ khối lượng tại thời điểm phân tích")
    turnover_rate: Optional[float] = Field(None, description="Tỷ lệ luân chuyển tại thời điểm phân tích")
    model_used: Optional[str] = Field(
        None,
        description="Ảnh chụp model trong bản ghi lịch sử, chỉ dùng để hiển thị metadata; không ảnh hưởng cấu hình model hay định tuyến runtime",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="Tóm tắt giai đoạn thị trường ít nhạy cảm của lần phân tích này",
    )
    created_at: Optional[str] = Field(None, description="Thời điểm tạo")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1234,
            "query_id": "abc123",
            "stock_code": "VCB.VN",
            "stock_name": "Ngân hàng Ngoại Thương",
            "report_type": "detailed",
            "sentiment_score": 75,
            "operation_advice": "Giữ",
            "created_at": "2024-01-01T12:00:00"
        }
    })


class HistoryListResponse(BaseModel):
    """Phản hồi danh sách lịch sử"""

    total: int = Field(..., description="Tổng số bản ghi")
    page: int = Field(..., description="Trang hiện tại")
    limit: int = Field(..., description="Số bản ghi mỗi trang")
    items: List[HistoryItem] = Field(default_factory=list, description="Danh sách bản ghi")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 100,
            "page": 1,
            "limit": 20,
            "items": []
        }
    })


class DeleteHistoryRequest(BaseModel):
    """Yêu cầu xóa lịch sử"""

    record_ids: List[int] = Field(default_factory=list, description="Danh sách khoá chính ID bản ghi lịch sử cần xóa")


class DeleteHistoryResponse(BaseModel):
    """Phản hồi xóa lịch sử"""

    deleted: int = Field(..., description="Số bản ghi lịch sử thực tế đã xóa")


class NewsIntelItem(BaseModel):
    """Mục tin tức/thông tin tình báo"""

    title: str = Field(..., description="Tiêu đề tin tức")
    snippet: str = Field("", description="Tóm tắt tin tức (tối đa 200 ký tự)")
    url: str = Field(..., description="Đường dẫn tin tức")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Doanh nghiệp công bố kết quả kinh doanh, doanh thu tăng 20% so với cùng kỳ",
            "snippet": "Theo thông báo của công ty, doanh thu quý tăng 20% so với cùng kỳ...",
            "url": "https://example.com/news/123"
        }
    })


class NewsIntelResponse(BaseModel):
    """Phản hồi tin tức/thông tin tình báo"""

    total: int = Field(..., description="Số tin tức")
    items: List[NewsIntelItem] = Field(default_factory=list, description="Danh sách tin tức")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 2,
            "items": []
        }
    })


class ReportMeta(BaseModel):
    """Thông tin meta của báo cáo"""

    model_config = ConfigDict(protected_namespaces=("model_validate", "model_dump"))

    id: Optional[int] = Field(None, description="Khoá chính ID bản ghi lịch sử phân tích (chỉ có với báo cáo lịch sử)")
    query_id: str = Field(..., description="Query_id liên kết bản ghi phân tích (có thể trùng khi phân tích hàng loạt)")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    report_type: Optional[str] = Field(None, description="Loại báo cáo")
    report_language: Optional[str] = Field(None, description="Ngôn ngữ báo cáo (zh/en/vi)")
    created_at: Optional[str] = Field(None, description="Thời điểm tạo")
    current_price: Optional[float] = Field(None, description="Giá cổ phiếu tại thời điểm phân tích")
    change_pct: Optional[float] = Field(None, description="Thay đổi giá tại thời điểm phân tích (%)")
    model_used: Optional[str] = Field(
        None,
        description="Ảnh chụp model trong metadata báo cáo lịch sử, chỉ dùng để hiển thị; không ảnh hưởng định tuyến Provider/Model/Base URL runtime",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="Tóm tắt giai đoạn thị trường ít nhạy cảm của lần phân tích này",
    )


class ReportSummary(BaseModel):
    """Phần tóm tắt tổng quan của báo cáo"""
    
    analysis_summary: Optional[str] = Field(None, description="Kết luận chính")
    operation_advice: Optional[str] = Field(None, description="Khuyến nghị thao tác")
    action: Optional[DecisionAction] = Field(None, description="Hành động khuyến nghị có cấu trúc (taxonomy)")
    action_label: Optional[str] = Field(None, description="Nhãn hiển thị của hành động khuyến nghị")
    trend_prediction: Optional[str] = Field(None, description="Dự báo xu hướng")
    sentiment_score: Optional[int] = Field(
        None,
        description="Điểm tâm lý thị trường (dữ liệu cũ có thể nằm ngoài 0-100, không ràng buộc khi đọc)",
    )
    sentiment_label: Optional[str] = Field(None, description="Nhãn tâm lý thị trường")


class ReportStrategy(BaseModel):
    """Phần chiến lược và mức giá mục tiêu"""
    
    ideal_buy: Optional[str] = Field(None, description="Giá mua lý tưởng")
    secondary_buy: Optional[str] = Field(None, description="Giá mua thứ hai")
    stop_loss: Optional[str] = Field(None, description="Giá cắt lỗ")
    take_profit: Optional[str] = Field(None, description="Giá chốt lời")


class AnalysisContextPackOverviewSubject(BaseModel):
    """Thông tin mã chứng khoán trong tóm tắt công khai của AnalysisContextPack"""

    code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    market: Optional[str] = Field(None, description="Thị trường")


class AnalysisContextPackOverviewBlock(BaseModel):
    """Khối dữ liệu trong tóm tắt công khai của AnalysisContextPack"""

    key: str = Field(..., description="Khoá ổn định của khối dữ liệu")
    label: str = Field(..., description="Tên hiển thị của khối dữ liệu")
    status: Literal[
        "available",
        "missing",
        "not_supported",
        "fallback",
        "stale",
        "estimated",
        "partial",
        "fetch_failed",
    ] = Field(..., description="Trạng thái chất lượng khối dữ liệu")
    source: Optional[str] = Field(None, description="Nguồn dữ liệu")
    warnings: List[str] = Field(default_factory=list, description="Mã cảnh báo của khối dữ liệu")
    missing_reasons: List[str] = Field(default_factory=list, description="Lý do thiếu dữ liệu")


class AnalysisContextPackOverviewCounts(BaseModel):
    """Đếm trạng thái trong tóm tắt công khai của AnalysisContextPack"""

    available: int = 0
    missing: int = 0
    not_supported: int = 0
    fallback: int = 0
    stale: int = 0
    estimated: int = 0
    partial: int = 0
    fetch_failed: int = 0


class AnalysisContextPackOverviewMetadata(BaseModel):
    """Metadata trong tóm tắt công khai của AnalysisContextPack"""

    trigger_source: Optional[str] = Field(None, description="Nguồn kích hoạt")
    news_result_count: Optional[int] = Field(None, description="Số lượng kết quả tin tức")


class AnalysisContextPackOverviewDataQuality(BaseModel):
    """Điểm chất lượng dữ liệu trong tóm tắt công khai của AnalysisContextPack"""

    overall_score: Optional[int] = Field(None, ge=0, le=100, description="Điểm chất lượng tổng thể dữ liệu đầu vào")
    level: Optional[Literal["good", "usable", "limited", "poor"]] = Field(
        None,
        description="Mức chất lượng dữ liệu đầu vào",
    )
    block_scores: Dict[str, int] = Field(default_factory=dict, description="Điểm chất lượng các khối dữ liệu cố định")
    limitations: List[str] = Field(default_factory=list, description="Mô tả giới hạn dữ liệu ít nhạy cảm")


class AnalysisContextPackOverview(BaseModel):
    """Tóm tắt AnalysisContextPack ít nhạy cảm, hiển thị qua lịch sử/API"""

    pack_version: str = Field(..., description="Phiên bản AnalysisContextPack")
    created_at: Optional[str] = Field(None, description="Thời điểm tạo")
    subject: AnalysisContextPackOverviewSubject
    blocks: List[AnalysisContextPackOverviewBlock] = Field(default_factory=list)
    counts: AnalysisContextPackOverviewCounts
    data_quality: Optional[AnalysisContextPackOverviewDataQuality] = Field(
        None,
        description="Tóm tắt ít nhạy cảm về chất lượng dữ liệu đầu vào lần phân tích này",
    )
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo chất lượng dữ liệu cấp cao nhất")
    metadata: AnalysisContextPackOverviewMetadata = Field(default_factory=AnalysisContextPackOverviewMetadata)


class ReportDetails(BaseModel):
    """Phần chi tiết báo cáo"""
    
    news_content: Optional[str] = Field(None, description="Tóm tắt tin tức")
    raw_result: Optional[Any] = Field(None, description="Kết quả phân tích thô (JSON)")
    context_snapshot: Optional[Any] = Field(None, description="Ảnh chụp ngữ cảnh tại thời điểm phân tích (JSON)")
    analysis_context_pack_overview: Optional[AnalysisContextPackOverview] = Field(
        None,
        description="Tóm tắt ít nhạy cảm của gói ngữ cảnh đầu vào lần phân tích này",
    )
    financial_report: Optional[Any] = Field(None, description="Tóm tắt báo cáo tài chính có cấu trúc (từ fundamental_context)")
    dividend_metrics: Optional[Any] = Field(None, description="Chỉ số cổ tức có cấu trúc (bao gồm khẩu TTM)")
    belong_boards: Optional[Any] = Field(None, description="Danh sách nhóm/ngành liên quan")
    sector_rankings: Optional[Any] = Field(None, description="Bảng xếp hạng ngành tăng/giảm (cấu trúc {top, bottom})")


class AnalysisReport(BaseModel):
    """Báo cáo phân tích đầy đủ"""

    meta: ReportMeta = Field(..., description="Thông tin meta")
    summary: ReportSummary = Field(..., description="Vùng tổng quan")
    strategy: Optional[ReportStrategy] = Field(None, description="Vùng chiến lược và mức giá")
    details: Optional[ReportDetails] = Field(None, description="Vùng chi tiết")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "meta": {
                "query_id": "abc123",
                "stock_code": "VCB.VN",
                "stock_name": "Ngân hàng Ngoại Thương",
                "report_type": "detailed",
                "report_language": "vi",
                "created_at": "2024-01-01T12:00:00"
            },
            "summary": {
                "analysis_summary": "Kỹ thuật tích cực, khuyến nghị nắm giữ",
                "operation_advice": "Giữ",
                "trend_prediction": "Tăng",
                "sentiment_score": 75,
                "sentiment_label": "Lạc quan"
            },
            "strategy": {
                "ideal_buy": "95000",
                "secondary_buy": "92000",
                "stop_loss": "88000",
                "take_profit": "110000"
            },
            "details": None
        }
    })


class MarkdownReportResponse(BaseModel):
    """Phản hồi báo cáo định dạng Markdown"""

    content: str = Field(..., description="Nội dung báo cáo đầy đủ định dạng Markdown")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "content": "# Ngân hàng Ngoại Thương (VCB.VN) — Báo cáo phân tích\n\n> Ngày phân tích: **2024-01-01**\n\n..."
        }
    })


class StockBarItem(BaseModel):
    """Mục thanh cổ phiếu (tóm tắt theo chiều cổ phiếu sau khi loại trùng)"""

    id: int = Field(..., description="Khoá chính ID của bản ghi lịch sử phân tích gần nhất cho cổ phiếu này")
    stock_code: str = Field(..., description="Mã cổ phiếu")
    stock_name: Optional[str] = Field(None, description="Tên cổ phiếu")
    report_type: Optional[str] = Field(None, description="Loại báo cáo")
    sentiment_score: Optional[int] = Field(
        None,
        description="Điểm tâm lý mới nhất",
    )
    operation_advice: Optional[str] = Field(None, description="Khuyến nghị thao tác mới nhất")
    action: Optional[DecisionAction] = Field(None, description="Hành động khuyến nghị có cấu trúc (taxonomy)")
    action_label: Optional[str] = Field(None, description="Nhãn hiển thị của hành động khuyến nghị")
    analysis_count: int = Field(..., description="Tổng số lần phân tích lịch sử của cổ phiếu này")
    last_analysis_time: Optional[str] = Field(None, description="Thời điểm phân tích gần nhất")
    model_used: Optional[str] = Field(
        None,
        description="Ảnh chụp model của lần phân tích gần nhất",
    )
    market_phase_summary: Optional[MarketPhaseSummary] = Field(
        None,
        description="Tóm tắt giai đoạn thị trường ít nhạy cảm của lần phân tích gần nhất",
    )
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1234,
            "stock_code": "VCB.VN",
            "stock_name": "Ngân hàng Ngoại Thương",
            "report_type": "detailed",
            "sentiment_score": 75,
            "operation_advice": "Giữ",
            "analysis_count": 18,
            "last_analysis_time": "2024-01-01T12:00:00",
            "model_used": "Gemini 2.5 Pro",
        }
    })


class StockBarResponse(BaseModel):
    """Phản hồi danh sách thanh cổ phiếu"""

    total: int = Field(..., description="Số cổ phiếu không trùng lặp")
    items: List[StockBarItem] = Field(default_factory=list, description="Danh sách từng cổ phiếu")


class WatchlistRequest(BaseModel):
    """Yêu cầu thao tác danh mục theo dõi"""

    stock_code: str = Field(..., description="Mã cổ phiếu", min_length=1)


class WatchlistResponse(BaseModel):
    """Phản hồi danh mục theo dõi"""

    stock_codes: List[str] = Field(default_factory=list, description="Danh sách mã cổ phiếu trong danh mục theo dõi hiện tại")
    message: str = Field(..., description="Mô tả kết quả thao tác")


class RunDiagnosticComponent(BaseModel):
    """Tóm tắt một thành phần chẩn đoán khi chạy."""

    key: str = Field(..., description="Khoá thành phần")
    label: str = Field(..., description="Tên hiển thị của thành phần")
    status: str = Field(..., description="Trạng thái thành phần: ok/degraded/failed/unknown/not_configured/skipped")
    message: str = Field(..., description="Tóm tắt có thể đọc được cho người dùng")
    details: Optional[Dict[str, Any]] = Field(None, description="Chi tiết chẩn đoán thu gọn")


class RunDiagnosticSummaryResponse(BaseModel):
    """Tóm tắt chẩn đoán chạy của báo cáo lịch sử."""

    trace_id: Optional[str] = Field(None, description="Trace ID chẩn đoán")
    task_id: Optional[str] = Field(None, description="ID tác vụ")
    query_id: Optional[str] = Field(None, description="Query ID phân tích")
    stock_code: Optional[str] = Field(None, description="Mã cổ phiếu")
    trigger_source: Optional[str] = Field(None, description="Nguồn kích hoạt")
    status: str = Field(..., description="Trạng thái tổng thể: normal/degraded/failed/unknown")
    status_label: str = Field(..., description="Nhãn trạng thái tổng thể")
    reason: str = Field(..., description="Nguyên nhân chẩn đoán chính")
    components: Dict[str, RunDiagnosticComponent] = Field(default_factory=dict, description="Các thành phần chẩn đoán chuỗi quan trọng")
    copy_text: str = Field(..., description="Văn bản chẩn đoán đã khử nhạy cảm để sao chép")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trace_id": "task_abc123",
            "query_id": "task_abc123",
            "stock_code": "VCB.VN",
            "status": "degraded",
            "status_label": "Một phần suy giảm",
            "reason": "Dữ liệu giá thời gian thực thất bại: timeout",
            "components": {},
            "copy_text": "trace_id: task_abc123\nstock_code: VCB.VN\n...",
        }
    })
