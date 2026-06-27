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
    ForeignFlowItem,
    ForeignFlowResponse,
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
        200: {"description": "Mã cổ phiếu được trích xuất"},
        400: {"description": "Ảnh không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Trích xuất mã cổ phiếu từ ảnh",
    description="Tải lên ảnh chụp màn hình/ảnh, trích xuất mã cổ phiếu qua Vision LLM. Hỗ trợ JPEG, PNG, WebP, GIF, tối đa 5MB.",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="File ảnh (tên trường form: file)"),
    include_raw: bool = Query(False, description="Có bao gồm phản hồi thô từ LLM trong kết quả không"),
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
        200: {"description": "Kết quả phân tích"},
        400: {"description": "Không có dữ liệu hoặc phân tích thất bại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Phân tích CSV/Excel/clipboard",
    description="Tải lên file CSV/Excel hoặc dán văn bản, tự động trích xuất mã cổ phiếu. Giới hạn file 2MB, văn bản 100KB.",
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
        200: {"description": "Danh mục theo dõi hiện tại"},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy danh mục theo dõi",
    description="Trả về tất cả mã cổ phiếu trong cấu hình STOCK_LIST hiện tại.",
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
        200: {"description": "Đã thêm vào danh mục theo dõi"},
        400: {"description": "Tham số không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Thêm vào danh mục theo dõi",
    description="Thêm mã cổ phiếu chỉ định vào STOCK_LIST.",
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
        200: {"description": "Đã xóa khỏi danh mục theo dõi"},
        400: {"description": "Tham số không hợp lệ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Xóa khỏi danh mục theo dõi",
    description="Xóa mã cổ phiếu chỉ định khỏi STOCK_LIST.",
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
        200: {"description": "Dữ liệu giá"},
        404: {"description": "Cổ phiếu không tồn tại", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy giá thời gian thực của cổ phiếu",
    description="Lấy dữ liệu giá mới nhất của cổ phiếu chỉ định"
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
        200: {"description": "Dữ liệu giá lịch sử"},
        422: {"description": "Tham số chu kỳ không được hỗ trợ", "model": ErrorResponse},
        500: {"description": "Lỗi máy chủ", "model": ErrorResponse},
    },
    summary="Lấy dữ liệu lịch sử giá cổ phiếu",
    description="Lấy dữ liệu nến K lịch sử của cổ phiếu chỉ định"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="Chu kỳ nến", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="Số ngày cần lấy"),
    indicators: bool = Query(False, description="Kèm chỉ báo kỹ thuật (MA/RSI/MACD)"),
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
        if indicators and period == "daily":
            return _history_with_indicators(stock_code, days)

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


def _history_with_indicators(stock_code: str, days: int) -> StockHistoryResponse:
    """Nến ngày kèm chỉ báo kỹ thuật (MA5/10/20 có sẵn + RSI14 + MACD tính thêm)."""
    import math
    from data_provider.base import DataFetcherManager

    mgr = DataFetcherManager()
    # Lấy dư ~40 nến để các chỉ báo (MA20/RSI/MACD) đủ dữ liệu khởi động rồi mới cắt.
    df, _src = mgr.get_daily_data(stock_code, days=days + 40)
    if df is None or df.empty:
        return StockHistoryResponse(stock_code=stock_code, stock_name=None, period="daily", data=[])

    df = df.copy()
    close = df["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df = df.tail(days)

    def opt(v):
        try:
            v = float(v)
            return None if math.isnan(v) else round(v, 4)
        except Exception:
            return None

    def req(v):
        try:
            v = float(v)
            return 0.0 if math.isnan(v) else v
        except Exception:
            return 0.0

    data = [
        KLineData(
            date=str(r.get("date"))[:10],
            open=req(r.get("open")), high=req(r.get("high")), low=req(r.get("low")), close=req(r.get("close")),
            volume=opt(r.get("volume")), amount=opt(r.get("amount")), change_percent=opt(r.get("pct_chg")),
            ma5=opt(r.get("ma5")), ma10=opt(r.get("ma10")), ma20=opt(r.get("ma20")),
            rsi=opt(r.get("rsi")), macd=opt(r.get("macd")), macd_signal=opt(r.get("macd_signal")),
        )
        for _, r in df.iterrows()
    ]
    name = None
    try:
        name = mgr.get_stock_name(stock_code)
    except Exception:
        name = None
    return StockHistoryResponse(stock_code=stock_code, stock_name=name, period="daily", data=data)


def _fetch_foreign_flow_series(stock_code: str, days: int) -> list:
    """Chuỗi giao dịch khối ngoại theo ngày qua vnstock_data (fail-open)."""
    import warnings
    import datetime as _dt
    import math
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from vnstock_data.explorer.vci.trading import Trading  # type: ignore
        bare = stock_code.upper().replace(".VN", "")
        end = _dt.date.today().isoformat()
        start = (_dt.date.today() - _dt.timedelta(days=days + 5)).isoformat()
        df = Trading(bare).foreign_trade(resolution="1D", start=start, end=end, limit=days)
        if df is None or df.empty:
            return []

        def f(row, col):
            try:
                v = row[col] if col in df.columns else None
                if v is None:
                    return None
                v = float(v)
                return None if math.isnan(v) else v
            except Exception:
                return None

        out = []
        for _, row in df.tail(days).iterrows():
            out.append({
                "date": str(row.get("trading_date") or "")[:10],
                "net_volume": f(row, "fr_net_volume_total"),
                "net_value": f(row, "fr_net_value_total"),
                "buy_volume": f(row, "fr_buy_volume_total"),
                "sell_volume": f(row, "fr_sell_volume_total"),
                "room_pct": f(row, "fr_room_percentage"),
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("foreign flow fetch failed for %s: %s", stock_code, exc)
        return []


@router.get(
    "/{stock_code}/foreign-flow",
    response_model=ForeignFlowResponse,
    summary="Giao dịch khối ngoại theo ngày",
    description="Chuỗi mua/bán ròng của nhà đầu tư nước ngoài (chỉ có ý nghĩa với mã .VN)",
)
def get_stock_foreign_flow(
    stock_code: str,
    days: int = Query(30, ge=1, le=120, description="Số ngày"),
) -> ForeignFlowResponse:
    series = _fetch_foreign_flow_series(stock_code, days)
    return ForeignFlowResponse(
        stock_code=stock_code,
        data=[ForeignFlowItem(**it) for it in series],
    )
