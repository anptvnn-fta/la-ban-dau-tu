# -*- coding: utf-8 -*-
"""
===================================
API dữ liệu cổ phiếu
===================================

Trách nhiệm:
1. POST /api/v1/stocks/extract-from-image Trích xuất mã cổ phiếu từ ảnh
2. POST /api/v1/stocks/parse-import Phân tích CSV/Excel/clipboard
3. GET /api/v1/stocks/{code}/quote API giá thời gian thực
4. GET /api/v1/stocks/{code}/history API dữ liệu lịch sử
"""

import logging
from typing import Optional
import re

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Depends

from api.deps import get_system_config_service

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockQuote,
)
from api.v1.schemas.history import WatchlistRequest, WatchlistResponse
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService
from src.services.system_config_service import SystemConfigService
from data_provider.base import normalize_stock_code

logger = logging.getLogger(__name__)

router = APIRouter()

# Phải định nghĩa trước route /{stock_code}
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


def _read_watchlist_codes(service: SystemConfigService) -> list:
    """Read STOCK_LIST codes as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    stock_list_str = ""
    for item in config_data.get("items", []):
        if item.get("key") == "STOCK_LIST":
            stock_list_str = str(item.get("value", ""))
            break
    return [c.strip() for c in stock_list_str.split(",") if c.strip()]


def _write_watchlist_codes(service: SystemConfigService, codes: list) -> None:
    """Persist stock codes to STOCK_LIST as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    config_version = config_data.get("config_version", "")
    service.update(
        config_version=config_version,
        items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
        mask_token="******",
        reload_now=True,
    )


# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|[A-Z]{2,3}\.VN"                        # Vietnam .VN suffix (e.g. FPT.VN)
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    """Validate stock code format and return canonical form.

    Raises HTTPException(400) if the code does not match supported formats.
    """
    stripped = code.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "Mã cổ phiếu không được để trống"},
        )
    if not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_stock_code",
                "message": f"'{stripped}' không phải định dạng mã cổ phiếu hợp lệ",
            },
        )
    return normalize_stock_code(stripped)


def _watchlist_match_key(code: str) -> str:
    """Return the equivalence key used for watchlist add/remove matching."""
    normalized = normalize_stock_code(code.strip())
    if re.fullmatch(r"\d{5}", normalized):
        return f"HK{normalized}"
    return normalized.upper()


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "提取的股票代码"},
        400: {"description": "图片无效", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从图片提取股票代码",
    description="上传截图/图片，通过 Vision LLM 提取股票代码。支持 JPEG、PNG、WebP、GIF，最大 5MB。",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="图片文件（表单字段名 file）"),
    include_raw: bool = Query(False, description="是否在结果中包含原始 LLM 响应"),
) -> ExtractFromImageResponse:
    """
    Trích xuất mã cổ phiếu từ ảnh tải lên (sử dụng Vision LLM).

    Dùng trường form file để tải ảnh lên. Thứ tự ưu tiên: Gemini / Anthropic / OpenAI (dùng cái đầu tiên khả dụng).
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "Chưa cung cấp file, vui lòng tải lên ảnh qua trường form file"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"Loại file không được hỗ trợ: {content_type}. Cho phép: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # Đọc đến giới hạn kích thước trước, sau đó kiểm tra có dữ liệu thừa không (vượt giới hạn thì từ chối)
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"Ảnh vượt quá giới hạn {MAX_SIZE_BYTES // (1024 * 1024)}MB",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Đọc file tải lên thất bại: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "Đọc file tải lên thất bại"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"Trích xuất từ ảnh thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "Trích xuất từ ảnh thất bại"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "解析结果"},
        400: {"description": "未提供数据或解析失败", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析 CSV/Excel/剪贴板",
    description="上传 CSV/Excel 文件或粘贴文本，自动解析股票代码。文件上限 2MB，文本上限 100KB。",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    Phân tích file CSV/Excel hoặc văn bản từ clipboard.

    - multipart/form-data + file: Tải file lên
    - application/json + {"text": "..."}: Dán văn bản
    - Ưu tiên dùng file; nếu cả hai cùng được cung cấp thì bỏ qua text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"Phân tích JSON thất bại: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "Chưa cung cấp text, vui lòng dùng {\"text\": \"...\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "Chưa cung cấp file, vui lòng dùng trường form file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"File vượt quá giới hạn {MAX_FILE_BYTES // (1024 * 1024)}MB",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"File vượt quá giới hạn {MAX_FILE_BYTES // (1024 * 1024)}MB",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "Đọc file thất bại"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "Vui lòng dùng multipart/form-data để tải file, hoặc application/json để gửi {\"text\": \"...\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "当前自选队列"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取自选队列",
    description="返回当前 STOCK_LIST 配置中的所有股票代码。",
)
def get_watchlist(
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        codes = _read_watchlist_codes(service)
        return WatchlistResponse(stock_codes=codes, message=f"Danh sách theo dõi hiện có {len(codes)} cổ phiếu")
    except Exception as e:
        logger.error(f"Lấy danh sách theo dõi thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Lấy danh sách theo dõi thất bại: {str(e)}"},
        )


@router.post(
    "/watchlist/add",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已加入自选"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="加入自选队列",
    description="将指定股票代码加入 STOCK_LIST。",
)
def add_to_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        if _watchlist_match_key(validated) not in existing_keys:
            codes.append(request.stock_code.strip())
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"Đã thêm {request.stock_code.strip()} vào danh sách theo dõi")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Thêm vào danh sách theo dõi thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Thêm vào danh sách theo dõi thất bại: {str(e)}"},
        )


@router.post(
    "/watchlist/remove",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "已从自选删除"},
        400: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="从自选队列删除",
    description="从 STOCK_LIST 中移除指定股票代码。",
)
def remove_from_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        requested_key = _watchlist_match_key(validated)
        if requested_key in existing_keys:
            idx = existing_keys.index(requested_key)
            codes.pop(idx)
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"Đã xóa {request.stock_code.strip()} khỏi danh sách theo dõi")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xóa khỏi danh sách theo dõi thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Xóa khỏi danh sách theo dõi thất bại: {str(e)}"},
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "行情数据"},
        404: {"description": "股票不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票实时行情",
    description="获取指定股票的最新行情数据"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    Lấy giá thời gian thực của cổ phiếu

    Lấy dữ liệu giá mới nhất của cổ phiếu được chỉ định

    Args:
        stock_code: Mã cổ phiếu (ví dụ: 600519, 00700, AAPL)

    Returns:
        StockQuote: Dữ liệu giá thời gian thực

    Raises:
        HTTPException: 404 - Cổ phiếu không tồn tại
    """
    try:
        service = StockService()

        # Dùng def thay vì async def, FastAPI tự chạy trong thread pool
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"Không tìm thấy dữ liệu giá cổ phiếu {stock_code}"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lấy giá thời gian thực thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Lấy giá thời gian thực thất bại: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "历史行情数据"},
        422: {"description": "不支持的周期参数", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票历史行情",
    description="获取指定股票的历史 K 线数据"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K 线周期", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="获取天数")
) -> StockHistoryResponse:
    """
    Lấy dữ liệu lịch sử cổ phiếu

    Lấy dữ liệu K-line lịch sử của cổ phiếu được chỉ định

    Args:
        stock_code: Mã cổ phiếu
        period: Chu kỳ K-line (daily/weekly/monthly)
        days: Số ngày cần lấy

    Returns:
        StockHistoryResponse: Dữ liệu lịch sử giá
    """
    try:
        service = StockService()

        # Dùng def thay vì async def, FastAPI tự chạy trong thread pool
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # Chuyển đổi sang response model
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )
    
    except ValueError as e:
        # Lỗi tham số period không được hỗ trợ (ví dụ: weekly/monthly)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Lấy dữ liệu lịch sử thất bại: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Lấy dữ liệu lịch sử thất bại: {str(e)}"
            }
        )
