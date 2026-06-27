# -*- coding: utf-8 -*-
"""DecisionSignal API endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, Field

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.decision_signals import (
    DecisionSignalCreateRequest,
    DecisionSignalFeedbackItem,
    DecisionSignalFeedbackRequest,
    DecisionSignalItem,
    DecisionSignalListResponse,
    DecisionSignalMutationResponse,
    DecisionSignalOutcomeListResponse,
    DecisionSignalOutcomeRunRequest,
    DecisionSignalOutcomeRunResponse,
    DecisionSignalOutcomeStatsResponse,
    DecisionSignalStatusUpdateRequest,
)
from src.auth import COOKIE_NAME
from src.services.decision_signal_service import (
    DecisionSignalNotFoundError,
    DecisionSignalService,
    DecisionSignalStorageError,
)
from src.services.decision_signal_outcome_service import DecisionSignalOutcomeService


logger = logging.getLogger(__name__)

admin_session_cookie = APIKeyCookie(
    name=COOKIE_NAME,
    scheme_name="AdminSessionCookie",
    auto_error=False,
)
# Lưu ý: Security(admin_session_cookie) ở đây CHỈ để khai báo schema cookie cho
# tài liệu OpenAPI (auto_error=False nên không tự chặn). Việc THỰC THI xác thực do
# AuthMiddleware toàn cục đảm nhiệm cho mọi /api/v1/* khi ADMIN_AUTH_ENABLED=true.
router = APIRouter(dependencies=[Security(admin_session_cookie)])

AUTH_RESPONSE = {
    401: {
        "model": ErrorResponse,
        "description": "Chưa đăng nhập hoặc phiên quản trị không hợp lệ (khi ADMIN_AUTH_ENABLED=true)",
    },
}


class SignalScanRequest(BaseModel):
    source: str = Field("watchlist", description="watchlist | portfolio")
    account_id: Optional[int] = None


class SignalScanResponse(BaseModel):
    source: str
    scanned: int = 0
    created: int = 0
    failed: List[str] = Field(default_factory=list)


@router.post(
    "/scan",
    response_model=SignalScanResponse,
    summary="Quét tín hiệu kỹ thuật cho danh mục theo dõi / cổ phiếu đang nắm giữ",
)
def scan_signals(request: SignalScanRequest) -> SignalScanResponse:
    from src.services.signal_scanner import resolve_scan_codes, scan_technical_signals

    source = request.source if request.source in ("watchlist", "portfolio") else "watchlist"
    codes = resolve_scan_codes(source, account_id=request.account_id)
    if not codes:
        return SignalScanResponse(source=source)
    result = scan_technical_signals(codes)
    return SignalScanResponse(source=source, **result)


def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": error, "message": str(exc)},
    )


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": str(exc)},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": message},
    )


@router.post(
    "",
    response_model=DecisionSignalMutationResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Trường yêu cầu không hợp lệ"},
        422: {"model": ErrorResponse, "description": "Xác thực body yêu cầu hoặc tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Tạo thất bại"},
    },
    summary="Tạo hoặc khử trùng tín hiệu quyết định",
    description=(
        "Ghi tường minh DecisionSignal. Nếu không truyền horizon/expires_at, dịch vụ sẽ bổ sung vòng đời mặc định; "
        "trúng khoá khử trùng cùng nguồn hoặc relaxed hẹp sẽ trả về bản ghi hiện có và created=false; "
        "tạo mới active hoặc gia hạn expired sẽ vô hiệu tín hiệu active ngược chiều cũ cùng cổ phiếu, "
        "active duplicate retry cũng chạy lại phần sửa đó; duplicate/replay cũ thông thường không phải sự kiện kích hoạt mới; "
        "không đảm bảo tuyệt đối idempotent khi có tranh chấp."
    ),
    operation_id="createDecisionSignal",
)
def create_signal(request: DecisionSignalCreateRequest) -> DecisionSignalMutationResponse:
    service = DecisionSignalService()
    try:
        payload = request.model_dump(exclude_unset=True)
        return DecisionSignalMutationResponse(**service.create_signal(payload))
    except DecisionSignalStorageError as exc:
        raise _internal_error("Create decision signal failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create decision signal failed", exc)


@router.get(
    "",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Tham số truy vấn không hợp lệ"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số truy vấn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn danh sách tín hiệu quyết định",
    description=(
        "Truy vấn phân trang DecisionSignal; trước khi đọc sẽ lazy-expire các tín hiệu active đã đến expires_at. "
        "Khi source_type=analysis và chỉ truyền source_report_id, nếu không có tín hiệu khớp sẽ thử lazy backfill từ báo cáo lịch sử một lần "
        "(chỉ trong kịch bản lần đầu trúng danh sách; truy vấn chính xác này sẽ kích hoạt ghi backfill tín hiệu lịch sử, thuộc hành vi read-with-write; "
        "không ảnh hưởng các kịch bản lọc danh sách phân trang khác). "
        "holding_only=true chỉ đọc danh mục nắm giữ cache portfolio_positions của tài khoản active, không kích hoạt portfolio snapshot replay."
    ),
    operation_id="listDecisionSignals",
)
def list_signals(
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr"),
    stock_code: Optional[str] = Query(None, description="Optional stock code filter"),
    action: Optional[str] = Query(None, description="Optional decision action filter"),
    market_phase: Optional[str] = Query(None, description="Optional market phase filter"),
    source_type: Optional[str] = Query(None, description="Optional source type filter"),
    source_report_id: Optional[int] = Query(None, description="Optional source report id filter"),
    trace_id: Optional[str] = Query(None, description="Optional trace id filter"),
    trigger_source: Optional[str] = Query(None, description="Optional trigger source filter"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    created_from: Optional[str] = Query(None, description="Inclusive created_at lower bound"),
    created_to: Optional[str] = Query(None, description="Inclusive created_at upper bound"),
    expires_from: Optional[str] = Query(None, description="Inclusive expires_at lower bound"),
    expires_to: Optional[str] = Query(None, description="Inclusive expires_at upper bound"),
    holding_only: bool = Query(False, description="Filter to active cached portfolio holdings only"),
    account_id: Optional[int] = Query(
        None,
        description="Optional active portfolio account id for holding_only",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.list_signals(
                market=market,
                stock_code=stock_code,
                action=action,
                market_phase=market_phase,
                source_type=source_type,
                source_report_id=source_report_id,
                trace_id=trace_id,
                trigger_source=trigger_source,
                status=status,
                created_from=created_from,
                created_to=created_to,
                expires_from=expires_from,
                expires_to=expires_to,
                holding_only=holding_only,
                account_id=account_id,
                page=page,
                page_size=page_size,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("List decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signals failed", exc)


@router.post(
    "/outcomes/run",
    response_model=DecisionSignalOutcomeRunResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Trường yêu cầu không hợp lệ"},
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực body yêu cầu thất bại"},
        500: {"model": ErrorResponse, "description": "Tính toán hậu nghiệm thất bại"},
    },
    summary="Kích hoạt đánh giá hậu nghiệm tín hiệu quyết định",
    description=(
        "Kích hoạt tường minh tính toán outcome cấp tín hiệu; mặc định bỏ qua completed và unable terminal, "
        "nhưng sẽ tính lại các unable có thể phục hồi như thiếu dữ liệu giá; force=true sẽ tính lại và ghi đè cùng "
        "signal_id+horizon+engine_version."
    ),
    operation_id="runDecisionSignalOutcomes",
)
def run_outcomes(request: DecisionSignalOutcomeRunRequest) -> DecisionSignalOutcomeRunResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeRunResponse(
            **service.run_outcomes(
                signal_id=request.signal_id,
                horizons=request.horizons,
                force=request.force,
                market=request.market,
                stock_code=request.stock_code,
                action=request.action,
                source_type=request.source_type,
                status=request.status,
                limit=request.limit,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Run decision signal outcomes failed", exc)


@router.get(
    "/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Tham số truy vấn không hợp lệ"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số truy vấn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn kết quả hậu nghiệm tín hiệu quyết định",
    description="Truy vấn phân trang signal-level outcome; mặc định chỉ truy vấn engine_version hậu nghiệm hiện tại.",
    operation_id="listDecisionSignalOutcomes",
)
def list_outcomes(
    signal_id: Optional[int] = Query(None, gt=0),
    horizon: Optional[str] = Query(None),
    engine_version: Optional[str] = Query(None),
    eval_status: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(
            **service.list_outcomes(
                signal_id=signal_id,
                horizon=horizon,
                engine_version=engine_version,
                eval_status=eval_status,
                outcome=outcome,
                page=page,
                page_size=page_size,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/outcomes/stats",
    response_model=DecisionSignalOutcomeStatsResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Tham số truy vấn không hợp lệ"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số truy vấn thất bại"},
        500: {"model": ErrorResponse, "description": "Thống kê thất bại"},
    },
    summary="Truy vấn thống kê hậu nghiệm tín hiệu quyết định",
    description="Mặc định thống kê engine_version hiện tại và loại trừ tín hiệu archived.",
    operation_id="getDecisionSignalOutcomeStats",
)
def get_outcome_stats(
    horizons: Optional[List[str]] = Query(None),
    engine_version: Optional[str] = Query(None),
    statuses: Optional[List[str]] = Query(None),
) -> DecisionSignalOutcomeStatsResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeStatsResponse(
            **service.get_stats(
                horizons=horizons,
                engine_version=engine_version,
                statuses=statuses,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal outcome stats failed", exc)


@router.get(
    "/latest/{stock_code}",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Tham số yêu cầu không hợp lệ"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số đường dẫn hoặc truy vấn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn tín hiệu quyết định active mới nhất của cổ phiếu",
    description="Trả về danh sách tín hiệu active mới nhất của cổ phiếu chỉ định; trước khi đọc sẽ thực hiện lazy-expire.",
    operation_id="getLatestDecisionSignals",
)
def get_latest_active(
    stock_code: str,
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr"),
    limit: int = Query(1, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.get_latest_active(
                stock_code=stock_code,
                market=market,
                limit=limit,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get latest decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get latest decision signals failed", exc)


@router.get(
    "/{signal_id}",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn một tín hiệu quyết định",
    description="Truy vấn một DecisionSignal theo ID; trước khi đọc sẽ thực hiện lazy-expire.",
    operation_id="getDecisionSignal",
)
def get_signal(signal_id: int) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(**service.get_signal(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get decision signal failed", exc)
    except Exception as exc:
        raise _internal_error("Get decision signal failed", exc)


@router.get(
    "/{signal_id}/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn kết quả hậu nghiệm của một tín hiệu quyết định",
    description="Trả về kết quả hậu nghiệm của signal_id chỉ định theo engine_version hiện tại.",
    operation_id="listDecisionSignalOutcomesBySignal",
)
def list_signal_outcomes(signal_id: int) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(**service.list_signal_outcomes(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Truy vấn thất bại"},
    },
    summary="Truy vấn phản hồi người dùng về tín hiệu quyết định",
    description="Trả về feedback_value=null khi không có phản hồi; trả về 404 khi tín hiệu không tồn tại.",
    operation_id="getDecisionSignalFeedback",
)
def get_feedback(signal_id: int) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(**service.get_feedback(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal feedback failed", exc)


@router.put(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Trường yêu cầu không hợp lệ"},
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực body yêu cầu hoặc tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Cập nhật thất bại"},
    },
    summary="Ghi phản hồi người dùng về tín hiệu quyết định",
    description="Upsert phản hồi useful/not_useful mới nhất theo signal_id.",
    operation_id="putDecisionSignalFeedback",
)
def put_feedback(signal_id: int, request: DecisionSignalFeedbackRequest) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(
            **service.put_feedback(
                signal_id,
                feedback_value=request.feedback_value,
                reason_code=request.reason_code,
                note=request.note,
                source=request.source,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Put decision signal feedback failed", exc)


@router.patch(
    "/{signal_id}/status",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "Trạng thái không hợp lệ"},
        404: {"model": ErrorResponse, "description": "Tín hiệu không tồn tại"},
        422: {"model": ErrorResponse, "description": "Xác thực body yêu cầu hoặc tham số đường dẫn thất bại"},
        500: {"model": ErrorResponse, "description": "Cập nhật thất bại"},
    },
    summary="Cập nhật trạng thái tín hiệu quyết định",
    description=(
        "Chỉ cập nhật trạng thái hợp lệ và metadata tùy chọn; khi truyền metadata sẽ thay thế toàn bộ gói. "
        "Các trạng thái terminal như expired/invalidated/closed/archived không thể PATCH trực tiếp về active."
    ),
    operation_id="updateDecisionSignalStatus",
)
def update_status(signal_id: int, request: DecisionSignalStatusUpdateRequest) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(
            **service.update_status(
                signal_id,
                status=request.status,
                metadata=request.metadata,
                replace_metadata="metadata" in request.model_fields_set,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Update decision signal status failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update decision signal status failed", exc)
