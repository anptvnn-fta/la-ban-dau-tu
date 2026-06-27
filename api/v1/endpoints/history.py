# -*- coding: utf-8 -*-
"""
===================================
API lịch sử phân tích
===================================

Trách nhiệm:
1. Cung cấp GET /api/v1/history để truy vấn danh sách lịch sử
2. Cung cấp GET /api/v1/history/{query_id} để truy vấn chi tiết lịch sử
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Body

from api.deps import get_database_manager
from api.v1.schemas.history import (
    HistoryListResponse,
    HistoryItem,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    NewsIntelItem,
    NewsIntelResponse,
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
    MarkdownReportResponse,
    RunDiagnosticSummaryResponse,
    StockBarItem,
    StockBarResponse,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.run_flow import RunFlowSnapshot
from src.storage import DatabaseManager
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.services.history_service import HistoryService, MarkdownReportGenerationError
from src.schemas.decision_action import build_action_fields
from src.utils.data_processing import (
    normalize_model_used,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
    extract_realtime_detail_fields,
)
from src.analysis_context_pack_overview import (
    extract_analysis_context_pack_overview,
    sanitize_context_snapshot_for_api,
)
from src.market_phase_summary import extract_market_phase_summary

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_code_for_grouping(code: str) -> str:
    """Normalize stock code for deduplication grouping.

    Delegates to data_provider.base.normalize_stock_code which handles
    SH600519, 600519.SH, HK00700, 00700.HK, BJ920748, etc.
    """
    from data_provider.base import normalize_stock_code
    return normalize_stock_code(code or "")


@router.get(
    "",
    response_model=HistoryListResponse,
    responses={
        200: {"description": "Danh sách bản ghi lịch sử"},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy danh sách lịch sử phân tích",
    description="Lấy tóm tắt bản ghi lịch sử phân tích theo phân trang, hỗ trợ lọc theo mã cổ phiếu và khoảng thời gian"
)
def get_history_list(
    stock_code: Optional[str] = Query(None, description="Lọc theo mã cổ phiếu"),
    report_type: Optional[str] = Query(None, description="Lọc theo loại báo cáo, ví dụ: market_review"),
    start_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> HistoryListResponse:
    """
    Lấy danh sách lịch sử phân tích

    Lấy tóm tắt bản ghi lịch sử phân tích theo phân trang, hỗ trợ lọc theo mã cổ phiếu và khoảng thời gian

    Args:
        stock_code: Lọc theo mã cổ phiếu
        report_type: Lọc theo loại báo cáo
        start_date: Ngày bắt đầu
        end_date: Ngày kết thúc
        page: Số trang
        limit: Số lượng mỗi trang
        db_manager: Dependency quản lý cơ sở dữ liệu

    Returns:
        HistoryListResponse: Danh sách bản ghi lịch sử
    """
    try:
        service = HistoryService(db_manager)

        # Dùng def thay vì async def, FastAPI tự chạy trong thread pool
        result = service.get_history_list(
            stock_code=stock_code,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        
        # Chuyển đổi sang response model
        items = [
            HistoryItem(
                id=item.get("id"),
                query_id=item.get("query_id", ""),
                stock_code=item.get("stock_code", ""),
                stock_name=item.get("stock_name"),
                report_type=item.get("report_type"),
                trend_prediction=item.get("trend_prediction"),
                analysis_summary=item.get("analysis_summary"),
                sentiment_score=item.get("sentiment_score"),
                operation_advice=item.get("operation_advice"),
                action=item.get("action"),
                action_label=item.get("action_label"),
                current_price=item.get("current_price"),
                change_pct=item.get("change_pct"),
                volume_ratio=item.get("volume_ratio"),
                turnover_rate=item.get("turnover_rate"),
                model_used=item.get("model_used"),
                created_at=item.get("created_at"),
                market_phase_summary=item.get("market_phase_summary"),
            )
            for item in result.get("items", [])
        ]
        
        return HistoryListResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
            items=items
        )
        
    except Exception as e:
        logger.error(f"Truy vấn danh sách lịch sử thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn danh sách lịch sử thất bại: {str(e)}"
            }
        )


@router.delete(
    "/by-code/{stock_code}",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Xóa thành công"},
        404: {"description": "Không tìm thấy bản ghi", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Xóa lịch sử phân tích theo mã cổ phiếu",
    description="Xóa tất cả bản ghi lịch sử phân tích của mã cổ phiếu chỉ định (hỗ trợ so khớp chuẩn hóa biến thể mã).",
)
def delete_history_by_code(
    stock_code: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> DeleteHistoryResponse:
    try:
        candidates = HistoryService._history_code_filter_candidates(stock_code)
        records, _ = db_manager.get_analysis_history_paginated(code=candidates, limit=10000)
        record_ids = [r.id for r in records if r.id is not None]
        if not record_ids:
            return DeleteHistoryResponse(deleted=0)
        deleted = db_manager.delete_analysis_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except Exception as e:
        logger.error(f"Xóa lịch sử theo mã cổ phiếu thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Xóa thất bại: {str(e)}"},
        )


@router.delete(
    "",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Xóa thành công"},
        400: {"description": "Tham số yêu cầu không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Xóa bản ghi lịch sử phân tích",
    description="Xóa hàng loạt bản ghi lịch sử phân tích theo khóa chính ID"
)
def delete_history_records(
    request: DeleteHistoryRequest = Body(...),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DeleteHistoryResponse:
    """
    Xóa hàng loạt bản ghi lịch sử phân tích theo khóa chính ID.
    """
    record_ids = sorted({record_id for record_id in request.record_ids if record_id is not None})
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "record_ids không được để trống"
            }
        )

    try:
        service = HistoryService(db_manager)
        deleted = service.delete_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xóa lịch sử phân tích thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Xóa lịch sử phân tích thất bại: {str(e)}"
            }
        )


@router.get(
    "/stocks",
    response_model=StockBarResponse,
    responses={
        200: {"description": "Danh sách cổ phiếu không trùng lặp"},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy danh sách cổ phiếu không trùng lặp",
    description="Trả về tóm tắt phân tích mới nhất của mỗi cổ phiếu trong lịch sử, không bao gồm tổng kết thị trường (code=MARKET).",
)
def get_stock_bar(
    start_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    limit: int = Query(200, ge=1, le=500, description="Số lượng trả về tối đa"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> StockBarResponse:
    try:
        from datetime import date as date_type
        from src.utils.data_processing import parse_json_field

        service = HistoryService(db_manager)
        start = date_type.fromisoformat(start_date) if start_date else None
        end = date_type.fromisoformat(end_date) if end_date else None

        # Fetch more than limit to compensate for normalization dedup shrinkage
        # (e.g. 002460 + 002460.SZ both initially counted but merged to one)
        fetch_limit = min(limit * 3, 500)
        records = db_manager.get_distinct_stocks_from_history(
            start_date=start,
            end_date=end,
            limit=fetch_limit,
        )

        # Deduplicate by normalized code, keeping the record with highest id
        seen: dict = {}
        for record in records:
            display_code = service._display_stock_code(record.code or "")
            norm_code = _normalize_code_for_grouping(display_code)
            if norm_code not in seen or record.id > seen[norm_code].id:
                seen[norm_code] = record

        items = []
        for norm_code in seen:
            record = seen[norm_code]
            raw_result = parse_json_field(getattr(record, "raw_result", None))
            model_used = raw_result.get("model_used") if isinstance(raw_result, dict) else None
            action_fields = build_action_fields(
                operation_advice=(
                    raw_result.get("operation_advice") if isinstance(raw_result, dict) else None
                )
                or record.operation_advice,
                explicit_action=raw_result.get("action") if isinstance(raw_result, dict) else None,
                report_type=record.report_type,
                report_language=normalize_report_language(
                    raw_result.get("report_language") if isinstance(raw_result, dict) else None
                ),
            )

            display_stock_code = service._display_stock_code(record.code)
            analysis_count = db_manager.get_analysis_history_paginated(
                code=HistoryService._history_code_filter_candidates(display_stock_code),
                limit=1,
            )[1]
            items.append(
                StockBarItem(
                    id=record.id,
                    stock_code=display_stock_code,
                    stock_name=record.name,
                    report_type=record.report_type,
                    sentiment_score=record.sentiment_score,
                    operation_advice=record.operation_advice,
                    action=action_fields["action"],
                    action_label=action_fields["action_label"],
                    analysis_count=analysis_count,
                    last_analysis_time=(
                        record.created_at.isoformat() if record.created_at else None
                    ),
                    model_used=normalize_model_used(model_used),
                    market_phase_summary=service._display_market_phase_summary(
                        record.code,
                        getattr(record, "context_snapshot", None),
                    ),
                )
            )

        items = items[:limit]
        return StockBarResponse(total=len(items), items=items)

    except Exception as e:
        logger.error(f"Truy vấn danh sách cổ phiếu thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn danh sách cổ phiếu thất bại: {str(e)}",
            },
        )


@router.get(
    "/{record_id}",
    response_model=AnalysisReport,
    responses={
        200: {"description": "Chi tiết báo cáo"},
        404: {"description": "Báo cáo không tồn tại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy chi tiết báo cáo lịch sử",
    description="Lấy báo cáo phân tích lịch sử đầy đủ theo ID bản ghi lịch sử phân tích hoặc query_id"
)
def get_history_detail(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AnalysisReport:
    """
    Lấy chi tiết báo cáo lịch sử

    Lấy báo cáo phân tích lịch sử đầy đủ theo khóa chính ID hoặc query_id.
    Ưu tiên truy vấn theo khóa chính ID (số nguyên); nếu tham số không phải số nguyên hợp lệ thì truy vấn theo query_id.

    Args:
        record_id: Khóa chính ID (số nguyên) hoặc query_id (chuỗi) của bản ghi lịch sử phân tích
        db_manager: Dependency quản lý cơ sở dữ liệu

    Returns:
        AnalysisReport: Báo cáo phân tích đầy đủ

    Raises:
        HTTPException: 404 - Báo cáo không tồn tại
    """
    try:
        service = HistoryService(db_manager)

        # Try integer ID first, fall back to query_id string lookup
        result = service.resolve_and_get_detail(record_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Không tìm thấy bản ghi phân tích id/query_id={record_id}"
                }
            )

        # Trích xuất thông tin giá từ context_snapshot
        # Lưu ý: dùng `is None` thay vì `or` để tránh nhầm 0.0 (giá đứng) là thiếu dữ liệu;
        # đồng thời không dùng `change_60d` (tăng/giảm lũy kế 60 ngày) làm dự phòng cho change_pct trong ngày.
        context_snapshot = result.get("context_snapshot")
        analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
        market_phase_summary = result.get("market_phase_summary")
        if market_phase_summary is None:
            market_phase_summary = extract_market_phase_summary(context_snapshot)
        api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
        realtime_fields = extract_realtime_detail_fields(context_snapshot)
        current_price = realtime_fields.get("current_price")
        change_pct = realtime_fields.get("change_pct")
        
        raw_result = result.get("raw_result")
        if not isinstance(raw_result, dict):
            raw_result = {}
        report_language = normalize_report_language(
            result.get("report_language")
            or raw_result.get("report_language")
            or (
                context_snapshot.get("report_language")
                if isinstance(context_snapshot, dict)
                else None
            )
        )
        stock_name = get_localized_stock_name(
            result.get("stock_name"),
            result.get("stock_code", ""),
            report_language,
        )

        # Xây dựng response model
        meta = ReportMeta(
            id=result.get("id"),
            query_id=result.get("query_id", ""),
            stock_code=result.get("stock_code", ""),
            stock_name=stock_name,
            report_type=result.get("report_type"),
            report_language=report_language,
            created_at=result.get("created_at"),
            current_price=current_price,
            change_pct=change_pct,
            model_used=normalize_model_used(result.get("model_used")),
            market_phase_summary=market_phase_summary,
        )
        
        summary = ReportSummary(
            analysis_summary=result.get("analysis_summary"),
            operation_advice=localize_operation_advice(
                result.get("operation_advice"),
                report_language,
            ),
            action=result.get("action"),
            action_label=result.get("action_label"),
            trend_prediction=localize_trend_prediction(
                result.get("trend_prediction"),
                report_language,
            ),
            sentiment_score=result.get("sentiment_score"),
            sentiment_label=(
                get_sentiment_label(result.get("sentiment_score"), report_language)
                if result.get("sentiment_score") is not None
                else result.get("sentiment_label")
            )
        )
        
        strategy = ReportStrategy(
            ideal_buy=result.get("ideal_buy"),
            secondary_buy=result.get("secondary_buy"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit")
        )
        
        fallback_fundamental = db_manager.get_latest_fundamental_snapshot(
            query_id=result.get("query_id", ""),
            code=result.get("storage_stock_code") or result.get("stock_code", ""),
        )
        extracted_fundamental = extract_fundamental_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        extracted_boards = extract_board_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )

        details = ReportDetails(
            news_content=result.get("news_content"),
            raw_result=result.get("raw_result"),
            context_snapshot=api_context_snapshot,
            analysis_context_pack_overview=analysis_context_pack_overview,
            financial_report=extracted_fundamental.get("financial_report"),
            dividend_metrics=extracted_fundamental.get("dividend_metrics"),
            belong_boards=extracted_boards.get("belong_boards"),
            sector_rankings=extracted_boards.get("sector_rankings"),
        )
        
        return AnalysisReport(
            meta=meta,
            summary=summary,
            strategy=strategy,
            details=details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Truy vấn chi tiết lịch sử thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn chi tiết lịch sử thất bại: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/diagnostics",
    response_model=RunDiagnosticSummaryResponse,
    responses={
        200: {"description": "Tóm tắt chẩn đoán chạy"},
        404: {"description": "Báo cáo không tồn tại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy tóm tắt chẩn đoán chạy của báo cáo lịch sử",
    description="Lấy tóm tắt chẩn đoán có thể đọc được cho người dùng và văn bản khử nhạy cảm để sao chép theo ID bản ghi hoặc query_id.",
)
def get_history_diagnostics(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunDiagnosticSummaryResponse:
    """
    Lấy tóm tắt chẩn đoán chạy của báo cáo lịch sử.
    """
    try:
        service = HistoryService(db_manager)
        summary = service.resolve_and_get_diagnostics(record_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Không tìm thấy bản ghi phân tích id/query_id={record_id}",
                },
            )
        return RunDiagnosticSummaryResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Truy vấn tóm tắt chẩn đoán thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn tóm tắt chẩn đoán thất bại: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/flow",
    response_model=RunFlowSnapshot,
    responses={
        200: {"description": "Ảnh chụp luồng chạy"},
        404: {"description": "Báo cáo không tồn tại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy luồng chạy của báo cáo lịch sử",
    description="Lấy ảnh chụp luồng dữ liệu/thông tin theo ID bản ghi lịch sử phân tích hoặc query_id.",
)
def get_history_run_flow(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunFlowSnapshot:
    """
    Lấy luồng chạy của báo cáo lịch sử.
    """
    try:
        service = HistoryService(db_manager)
        snapshot = service.resolve_and_get_run_flow(record_id)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Không tìm thấy bản ghi phân tích id/query_id={record_id}",
                },
            )
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Truy vấn ảnh chụp luồng chạy thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn ảnh chụp luồng chạy thất bại: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/news",
    response_model=NewsIntelResponse,
    responses={
        200: {"description": "Danh sách tin tức tình báo"},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy tin tức liên quan đến báo cáo lịch sử",
    description="Lấy danh sách tin tức tình báo liên quan theo ID bản ghi lịch sử phân tích (trả về 200 ngay cả khi không có tin tức)"
)
def get_history_news(
    record_id: str,
    limit: int = Query(20, ge=1, le=100, description="Giới hạn số lượng trả về"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> NewsIntelResponse:
    """
    Lấy tin tức liên quan đến báo cáo lịch sử

    Lấy danh sách tin tức tình báo liên quan theo ID hoặc query_id của bản ghi lịch sử phân tích.
    Nội bộ thực hiện giải mã record_id → query_id.

    Args:
        record_id: Khóa chính ID (số nguyên) hoặc query_id (chuỗi) của bản ghi lịch sử phân tích
        limit: Giới hạn số lượng trả về
        db_manager: Dependency quản lý cơ sở dữ liệu

    Returns:
        NewsIntelResponse: Danh sách tin tức tình báo
    """
    try:
        service = HistoryService(db_manager)
        items = service.resolve_and_get_news(record_id=record_id, limit=limit)

        response_items = [
            NewsIntelItem(
                title=item.get("title", ""),
                snippet=item.get("snippet"),
                url=item.get("url", "")
            )
            for item in items
        ]

        return NewsIntelResponse(
            total=len(response_items),
            items=response_items
        )

    except Exception as e:
        logger.error(f"Truy vấn tin tức thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Truy vấn tin tức thất bại: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/markdown",
    response_model=MarkdownReportResponse,
    responses={
        200: {"description": "Báo cáo định dạng Markdown"},
        404: {"description": "Báo cáo không tồn tại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy báo cáo lịch sử định dạng Markdown",
    description="Lấy báo cáo phân tích đầy đủ định dạng Markdown theo ID bản ghi lịch sử phân tích"
)
def get_history_markdown(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> MarkdownReportResponse:
    """
    Lấy nội dung báo cáo lịch sử định dạng Markdown

    Tạo báo cáo Markdown nhất quán với định dạng thông báo đẩy theo ID hoặc query_id của bản ghi lịch sử phân tích.

    Args:
        record_id: Khóa chính ID (số nguyên) hoặc query_id (chuỗi) của bản ghi lịch sử phân tích
        db_manager: Dependency quản lý cơ sở dữ liệu

    Returns:
        MarkdownReportResponse: Báo cáo đầy đủ định dạng Markdown

    Raises:
        HTTPException: 404 - Báo cáo không tồn tại
        HTTPException: 500 - Tạo báo cáo thất bại (lỗi máy chủ nội bộ)
    """
    service = HistoryService(db_manager)

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as e:
        logger.error(f"Markdown report generation failed for {record_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"Tạo báo cáo Markdown thất bại: {e.message}"
            }
        )
    except Exception as e:
        logger.error(f"Lấy báo cáo Markdown thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Lấy báo cáo Markdown thất bại: {str(e)}"
            }
        )

    if markdown_content is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Không tìm thấy bản ghi phân tích id/query_id={record_id}"
            }
        )

    return MarkdownReportResponse(content=markdown_content)
