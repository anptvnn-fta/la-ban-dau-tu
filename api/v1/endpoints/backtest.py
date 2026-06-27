# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestResultItem,
    BacktestResultsResponse,
    PerformanceMetrics,
    WalkForwardRequest,
    WalkForwardResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

BacktestAnalysisPhaseQuery = Literal["premarket", "intraday", "postmarket", "unknown"]


def _validate_analysis_date_range(
    analysis_date_from: Optional[date],
    analysis_date_to: Optional[date],
) -> None:
    if analysis_date_from and analysis_date_to and analysis_date_from > analysis_date_to:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_params",
                "message": "analysis_date_from cannot be after analysis_date_to",
            },
        )


def _save_walk_forward(result: dict, mode: str) -> None:
    """Lưu kết quả walk-forward (chỉ khi có điểm đánh giá) để lần sau khỏi chạy lại."""
    try:
        if result and result.get("evaluated"):
            from src.storage import get_db
            get_db().save_walk_forward_run(
                code=result.get("code", ""),
                mode=mode,
                eval_window_days=int(result.get("eval_window_days") or 10),
                payload=result,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Lưu walk-forward thất bại: %s", exc)


@router.get(
    "/walk-forward/saved",
    response_model=WalkForwardResponse,
    summary="Lấy kết quả kiểm định trượt tiến đã lưu",
)
def get_saved_walk_forward(code: str, eval_window_days: int = 10, mode: str = "tech") -> WalkForwardResponse:
    from src.services.walk_forward_backtest import _to_vn

    norm = _to_vn(code)
    safe_mode = mode if mode in ("tech", "ai") else "tech"
    try:
        from src.storage import get_db
        data = get_db().get_walk_forward_run(norm, safe_mode, eval_window_days)
        if data:
            return WalkForwardResponse(**data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Đọc walk-forward đã lưu lỗi: %s", exc)
    return WalkForwardResponse(code=norm, evaluated=0, eval_window_days=eval_window_days)


@router.post(
    "/walk-forward",
    response_model=WalkForwardResponse,
    summary="Kiểm định trượt tiến",
    description="Đánh giá tín hiệu kỹ thuật trên dữ liệu lịch sử (không cần báo cáo AI cũ, không gọi LLM).",
)
def run_walk_forward_backtest(request: WalkForwardRequest) -> WalkForwardResponse:
    try:
        from src.services.walk_forward_backtest import run_walk_forward

        result = run_walk_forward(
            request.code,
            days=request.days,
            eval_window_days=request.eval_window_days,
        )
        _save_walk_forward(result, "tech")
        return WalkForwardResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Walk-forward backtest failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "walk_forward_failed", "message": "Kiểm định trượt tiến thất bại. Vui lòng thử lại."},
        )


@router.post(
    "/walk-forward-ai",
    response_model=WalkForwardResponse,
    summary="Kiểm định trượt tiến bằng AI",
    description="Cho AI quyết định tại các mốc quá khứ (dữ liệu kỹ thuật point-in-time) rồi đối chiếu giá thực tế. Tốn một ít lượt LLM.",
)
def run_walk_forward_ai_backtest(request: WalkForwardRequest) -> WalkForwardResponse:
    try:
        from src.services.walk_forward_backtest import run_walk_forward_ai

        result = run_walk_forward_ai(
            request.code,
            days=request.days,
            eval_window_days=request.eval_window_days,
        )
        _save_walk_forward(result, "ai")
        return WalkForwardResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Walk-forward AI backtest failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "walk_forward_ai_failed", "message": "Kiểm định AI thất bại. Vui lòng thử lại."},
        )


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "Kiểm tra ngược hoàn thành"},
        400: {"description": "Tham số yêu cầu không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Kích hoạt kiểm tra ngược",
    description="Đánh giá kiểm tra ngược trên bản ghi lịch sử phân tích và ghi vào backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunResponse:
    try:
        _validate_analysis_date_range(request.analysis_date_from, request.analysis_date_to)
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            analysis_date_from=request.analysis_date_from,
            analysis_date_to=request.analysis_date_to,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Chạy kiểm tra ngược thất bại: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Chạy kiểm tra ngược thất bại: {str(exc)}"},
        )


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "Danh sách kết quả kiểm tra ngược"},
        400: {"description": "Tham số yêu cầu không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy kết quả kiểm tra ngược",
    description="Lấy kết quả kiểm tra ngược theo phân trang, hỗ trợ lọc theo mã cổ phiếu",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="Lọc theo mã cổ phiếu"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="Lọc theo cửa sổ đánh giá"),
    analysis_date_from: Optional[date] = Query(None, description="Ngày phân tích bắt đầu (bao gồm)"),
    analysis_date_to: Optional[date] = Query(None, description="Ngày phân tích kết thúc (bao gồm)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Lọc theo giai đoạn phân tích: premarket/intraday/postmarket/unknown"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(20, ge=1, le=200, description="Số lượng mỗi trang"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        data = service.get_recent_evaluations(
            code=code,
            eval_window_days=eval_window_days,
            limit=limit,
            page=page,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Truy vấn kết quả kiểm tra ngược thất bại: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Truy vấn kết quả kiểm tra ngược thất bại: {str(exc)}"},
        )


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "Hiệu suất kiểm tra ngược tổng thể"},
        400: {"description": "Tham số yêu cầu không hợp lệ", "model": ErrorResponse},
        404: {"description": "Không có tóm tắt kiểm tra ngược", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy hiệu suất kiểm tra ngược tổng thể",
)
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="Lọc theo cửa sổ đánh giá"),
    analysis_date_from: Optional[date] = Query(None, description="Ngày phân tích bắt đầu (bao gồm)"),
    analysis_date_to: Optional[date] = Query(None, description="Ngày phân tích kết thúc (bao gồm)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Lọc theo giai đoạn phân tích: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="overall",
            code=None,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Không tìm thấy tóm tắt kiểm tra ngược tổng thể"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Truy vấn hiệu suất tổng thể thất bại: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Truy vấn hiệu suất tổng thể thất bại: {str(exc)}"},
        )


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "Hiệu suất kiểm tra ngược của cổ phiếu đơn lẻ"},
        400: {"description": "Tham số yêu cầu không hợp lệ", "model": ErrorResponse},
        404: {"description": "Không có tóm tắt kiểm tra ngược", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy hiệu suất kiểm tra ngược của cổ phiếu đơn lẻ",
)
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="Lọc theo cửa sổ đánh giá"),
    analysis_date_from: Optional[date] = Query(None, description="Ngày phân tích bắt đầu (bao gồm)"),
    analysis_date_to: Optional[date] = Query(None, description="Ngày phân tích kết thúc (bao gồm)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Lọc theo giai đoạn phân tích: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="stock",
            code=code,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Không tìm thấy tóm tắt kiểm tra ngược cho {code}"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Truy vấn hiệu suất cổ phiếu thất bại: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Truy vấn hiệu suất cổ phiếu thất bại: {str(exc)}"},
        )
