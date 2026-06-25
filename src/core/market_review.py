# -*- coding: utf-8 -*-
"""
===================================
Hệ thống phân tích cổ phiếu thông minh - Mô-đun tổng kết thị trường
(Hỗ trợ A-share / Hồng Kông / Mỹ / Việt Nam)
===================================

Trách nhiệm:
1. Chọn vùng thị trường theo cấu hình MARKET_REVIEW_REGION (cn / hk / us / both / vn)
2. Thực hiện phân tích tổng kết thị trường và tạo báo cáo tổng kết
3. Lưu và gửi báo cáo tổng kết
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from src.config import get_config
from src.notification import NotificationService
from src.market_analyzer import MarketAnalyzer
from src.report_language import normalize_report_language
from src.search_service import SearchService
from src.analyzer import AnalysisResult, GeminiAnalyzer
from src.llm.generation_backend import GenerationError
from src.services.run_diagnostics import (
    current_diagnostic_snapshot,
    record_history_run,
    record_notification_run,
)


logger = logging.getLogger(__name__)

MARKET_REVIEW_HISTORY_CODE = "MARKET"
MARKET_REVIEW_REPORT_TYPE = "market_review"
_MARKET_REVIEW_MARKETS = (
    ('cn', 'cn_title', 'A 股'),
    ('hk', 'hk_title', '港股'),
    ('us', 'us_title', '美股'),
    ('vn', 'vn_title', 'Việt Nam'),
)
_MARKET_REVIEW_REGION_ORDER = tuple(market for market, _, _ in _MARKET_REVIEW_MARKETS)
_VALID_MARKET_REVIEW_REGIONS = frozenset(_MARKET_REVIEW_REGION_ORDER)
# 'both' keeps its historical meaning of the three CN/HK/US markets; Vietnam is an
# opt-in single region (MARKET_REVIEW_REGION=vn), not part of the 'both' bundle.
_BOTH_REGION_ORDER = tuple(market for market in _MARKET_REVIEW_REGION_ORDER if market != "vn")


@dataclass
class MarketReviewRunResult:
    """Structured result for API/Web consumers while keeping Markdown compatibility."""

    report: str
    market_review_payload: Dict[str, Any] = field(default_factory=dict)


def _refresh_market_review_history_diagnostics(*, query_id: str) -> None:
    """Refresh persisted market-review diagnostics after late flow events are recorded."""
    diagnostic_snapshot = current_diagnostic_snapshot()
    if diagnostic_snapshot is None:
        return

    try:
        from src.storage import DatabaseManager

        db = DatabaseManager.get_instance()
        updater = getattr(db, "update_analysis_history_diagnostics", None)
        if callable(updater):
            updater(
                query_id=query_id,
                code=MARKET_REVIEW_HISTORY_CODE,
                diagnostics=diagnostic_snapshot,
            )
    except Exception as exc:
        logger.warning("回写大盘复盘运行诊断失败（fail-open）: %s", exc)


def _record_market_review_notification_run(
    *,
    query_id: str,
    channel: str,
    status: str,
    success: bool,
    attempts: int = 1,
    error_message: Optional[Any] = None,
) -> None:
    record_notification_run(
        channel=channel,
        status=status,
        success=success,
        attempts=attempts,
        error_message=error_message,
    )
    _refresh_market_review_history_diagnostics(query_id=query_id)


def _get_market_review_text(language: str) -> dict[str, str]:
    # Vietnamese is not part of the global report_language model (zh/en), so a
    # 'vi' request is honoured here directly before normalization collapses it.
    if str(language or "").strip().lower() == "vi":
        return {
            "root_title": "# 🎯 Tổng kết thị trường",
            "push_title": "🎯 Tổng kết thị trường",
            "cn_title": "# Tổng kết thị trường A-share",
            "us_title": "# Tổng kết thị trường Mỹ",
            "hk_title": "# Tổng kết thị trường Hồng Kông",
            "vn_title": "# Tổng kết thị trường Việt Nam",
            "separator": "> Tiếp theo là tổng kết thị trường kế tiếp",
        }
    normalized = normalize_report_language(language)
    if normalized == "en":
        return {
            "root_title": "# 🎯 Market Review",
            "push_title": "🎯 Market Review",
            "cn_title": "# A-share Market Recap",
            "us_title": "# US Market Recap",
            "hk_title": "# HK Market Recap",
            "vn_title": "# Vietnam Market Recap",
            "separator": "> Next market recap follows",
        }
    return {
        "root_title": "# 🎯 大盘复盘",
        "push_title": "🎯 大盘复盘",
        "cn_title": "# A股大盘复盘",
        "us_title": "# 美股大盘复盘",
        "hk_title": "# 港股大盘复盘",
        "vn_title": "# 越南股市复盘",
        "separator": "> 以下为下一市场大盘复盘",
    }


def _resolve_market_review_regions(raw_region: Optional[str]) -> list[str]:
    """Normalize MARKET_REVIEW_REGION into an ordered, non-empty region list."""

    region = str(raw_region or 'cn').strip().lower()
    if region == 'both':
        return list(_BOTH_REGION_ORDER)
    if ',' in region:
        requested = {
            item.strip().lower()
            for item in region.split(',')
            if item.strip().lower() in _VALID_MARKET_REVIEW_REGIONS
        }
        return [market for market in _MARKET_REVIEW_REGION_ORDER if market in requested] or ['cn']
    if region in _VALID_MARKET_REVIEW_REGIONS:
        return [region]
    return ['cn']


def run_market_review(
    notifier: NotificationService,
    analyzer: Optional[GeminiAnalyzer] = None,
    search_service: Optional[SearchService] = None,
    config: Optional[object] = None,
    send_notification: bool = True,
    merge_notification: bool = False,
    override_region: Optional[str] = None,
    query_id: Optional[str] = None,
    return_structured: bool = False,
    save_report_file: bool = True,
    persist_history: bool = True,
    trigger_source: str = "cli",
) -> Optional[str] | Optional[MarketReviewRunResult]:
    """
    Thực hiện phân tích tổng kết thị trường

    Args:
        notifier: Dịch vụ thông báo
        analyzer: Bộ phân tích AI (tùy chọn)
        search_service: Dịch vụ tìm kiếm (tùy chọn)
        config: Cấu hình dùng cho lần tổng kết này (tùy chọn; nếu không truyền thì đọc cấu hình toàn cục)
        send_notification: Có gửi thông báo không
        merge_notification: Có gộp thông báo không (bỏ qua lần gửi này, để tầng main gộp cổ phiếu+tổng kết rồi gửi một lần, Issue #190)
        override_region: Ghi đè market_review_region của config (Issue #373 — tập con hợp lệ sau lọc ngày giao dịch)
        query_id: ID liên kết lịch sử; tác vụ nền API truyền task_id, CLI/Bot để trống thì tự sinh
        save_report_file: Có lưu file Markdown không; có thể tắt trên đường dẫn sinh ngữ cảnh để tránh nhiều vùng tổng kết tạm thời ghi đè nhau
        persist_history: Có ghi vào analysis_history không; có thể tắt trên đường dẫn pre-warm để tránh ghi đè bản ghi tổng kết thị trường cùng ngày mà người dùng đang xem
        trigger_source: Nguồn kích hoạt, dùng cho log debug (cli/schedule/api/bot/service, v.v.)

    Returns:
        Nội dung văn bản báo cáo tổng kết
    """
    runtime_config = config or get_config()
    history_query_id = query_id or f"market_review_{uuid.uuid4().hex}"
    raw_region = (
        override_region
        if override_region is not None
        else (getattr(runtime_config, 'market_review_region', 'cn') or 'cn')
    )
    run_markets = _resolve_market_review_regions(raw_region)
    persist_region = ','.join(run_markets) if len(run_markets) > 1 else run_markets[0]
    # A Vietnam-only review renders its wrapper/title text in Vietnamese; mixed or
    # other-market runs follow the configured report_language (zh/en).
    review_text_language = (
        "vi" if run_markets == ["vn"] else getattr(runtime_config, "report_language", "zh")
    )
    review_text = _get_market_review_text(review_text_language)
    logger.info(
        "[MarketReview] component=market_review action=start trigger_source=%s query_id=%s region=%s",
        trigger_source,
        history_query_id,
        persist_region,
    )

    try:
        if len(run_markets) > 1:
            # Thực hiện tuần tự nhiều thị trường, gộp báo cáo
            parts = []
            market_light_snapshots: Dict[str, Dict[str, Any]] = {}
            market_review_payloads: Dict[str, Dict[str, Any]] = {}
            for mkt, title_key, label in _MARKET_REVIEW_MARKETS:
                if mkt not in run_markets:
                    continue
                logger.info(
                    "[MarketReview] component=market_review action=build_report "
                    "trigger_source=%s query_id=%s region=%s label=%s",
                    trigger_source,
                    history_query_id,
                    mkt,
                    label,
                )
                mkt_analyzer = MarketAnalyzer(
                    search_service=search_service,
                    analyzer=analyzer,
                    region=mkt,
                    config=runtime_config,
                )
                review_result = mkt_analyzer.run_daily_review_with_snapshot()
                mkt_report = review_result.report
                market_light_snapshots[mkt] = review_result.market_light_snapshot
                market_review_payloads[mkt] = _coerce_market_review_payload(
                    review_result,
                    region=mkt,
                    report=mkt_report,
                )
                if mkt_report:
                    parts.append(f"{review_text[title_key]}\n\n{mkt_report}")
            if parts:
                review_report = f"\n\n---\n\n{review_text['separator']}\n\n".join(parts)
            else:
                review_report = None
        else:
            run_region = run_markets[0]
            label = next(
                (market_label for mkt, _, market_label in _MARKET_REVIEW_MARKETS if mkt == run_region),
                run_region,
            )
            logger.info(
                "[MarketReview] component=market_review action=build_report "
                "trigger_source=%s query_id=%s region=%s label=%s",
                trigger_source,
                history_query_id,
                run_region,
                label,
            )
            market_analyzer = MarketAnalyzer(
                search_service=search_service,
                analyzer=analyzer,
                region=run_region,
                config=runtime_config,
            )
            review_result = market_analyzer.run_daily_review_with_snapshot()
            review_report = review_result.report
            market_light_snapshots = {run_region: review_result.market_light_snapshot}
            market_review_payloads = {
                run_region: _coerce_market_review_payload(
                    review_result,
                    region=run_region,
                    report=review_report,
                )
            }
        
        if review_report:
            market_review_payload = _build_combined_market_review_payload(
                review_report=review_report,
                payloads=market_review_payloads,
                region=persist_region,
                language=review_text_language,
                root_title=review_text["root_title"],
            )
            markdown_report = _render_market_review_payload_markdown(
                market_review_payload,
                wrapper_title=review_text["root_title"],
            )
            if save_report_file:
                # Lưu báo cáo ra file
                date_str = datetime.now().strftime('%Y%m%d')
                report_filename = f"market_review_{date_str}.md"
                filepath = notifier.save_report_to_file(
                    markdown_report,
                    report_filename
                )
                logger.info(
                    "[MarketReview] component=market_review action=save_report "
                    "trigger_source=%s query_id=%s region=%s path=%s",
                    trigger_source,
                    history_query_id,
                    persist_region,
                    filepath,
                )

            if persist_history:
                _persist_market_review_history(
                    review_report=review_report,
                    markdown_report=markdown_report,
                    region=persist_region,
                    config=runtime_config,
                    query_id=history_query_id,
                    market_light_snapshots=market_light_snapshots,
                    market_review_payload=market_review_payload,
                )
            
            # Gửi thông báo (bỏ qua ở chế độ gộp, để tầng main gửi thống nhất)
            if merge_notification and send_notification:
                logger.info(
                    "[MarketReview] component=market_review action=skip_standalone_notification "
                    "trigger_source=%s query_id=%s region=%s",
                    trigger_source,
                    history_query_id,
                    persist_region,
                )
                _record_market_review_notification_run(
                    query_id=history_query_id,
                    channel="report",
                    status="skipped",
                    success=False,
                    attempts=0,
                )
            elif send_notification and notifier.is_available():
                # Thêm tiêu đề
                report_content = _render_market_review_payload_markdown(
                    market_review_payload,
                    wrapper_title=review_text["push_title"],
                )

                success = notifier.send(report_content, email_send_to_all=True, route_type="report")
                _record_market_review_notification_run(
                    query_id=history_query_id,
                    channel="report",
                    status="success" if success else "failed",
                    success=success,
                )
                if success:
                    logger.info(
                        "[MarketReview] component=market_review action=send_notification "
                        "status=success trigger_source=%s query_id=%s region=%s",
                        trigger_source,
                        history_query_id,
                        persist_region,
                    )
                else:
                    logger.warning(
                        "[MarketReview] component=market_review action=send_notification "
                        "status=failed trigger_source=%s query_id=%s region=%s",
                        trigger_source,
                        history_query_id,
                        persist_region,
                    )
            elif not send_notification:
                logger.info(
                    "[MarketReview] component=market_review action=skip_notification "
                    "reason=no_notify trigger_source=%s query_id=%s region=%s",
                    trigger_source,
                    history_query_id,
                    persist_region,
                )
                _record_market_review_notification_run(
                    query_id=history_query_id,
                    channel="report",
                    status="skipped",
                    success=False,
                    attempts=0,
                )
            else:
                logger.info(
                    "[MarketReview] component=market_review action=skip_notification "
                    "reason=not_configured trigger_source=%s query_id=%s region=%s",
                    trigger_source,
                    history_query_id,
                    persist_region,
                )
                _record_market_review_notification_run(
                    query_id=history_query_id,
                    channel="report",
                    status="not_configured",
                    success=False,
                    attempts=0,
                )
            
            if return_structured:
                return MarketReviewRunResult(
                    report=review_report,
                    market_review_payload=market_review_payload,
                )
            return review_report
        
    except GenerationError:
        logger.exception(
            "[MarketReview] component=market_review action=failed "
            "reason=generation_backend_config trigger_source=%s query_id=%s region=%s",
            trigger_source,
            history_query_id,
            persist_region,
        )
        raise
    except Exception:
        logger.exception(
            "[MarketReview] component=market_review action=failed "
            "trigger_source=%s query_id=%s region=%s",
            trigger_source,
            history_query_id,
            persist_region,
        )
    
    return None


def _coerce_market_review_payload(
    review_result: Any,
    *,
    region: str,
    report: Optional[str],
) -> Dict[str, Any]:
    payload = getattr(review_result, "structured_payload", None)
    if isinstance(payload, dict) and payload:
        return payload
    return {
        "version": 1,
        "kind": MARKET_REVIEW_REPORT_TYPE,
        "region": region,
        "title": "",
        "sections": [{"key": "full_review", "title": "Review", "markdown": report or ""}],
        "markdown_report": report or "",
    }


def _build_combined_market_review_payload(
    *,
    review_report: str,
    payloads: Dict[str, Dict[str, Any]],
    region: str,
    language: str,
    root_title: str,
) -> Dict[str, Any]:
    normalized_language = normalize_report_language(language)
    title = root_title.lstrip("#").strip()
    if len(payloads) == 1:
        payload = dict(next(iter(payloads.values())))
        payload["version"] = payload.get("version") or 1
        payload["kind"] = MARKET_REVIEW_REPORT_TYPE
        payload["region"] = region
        payload["language"] = payload.get("language") or normalized_language
        payload["root_title"] = title
        payload["markdown_report"] = review_report
        return payload
    return {
        "version": 1,
        "kind": MARKET_REVIEW_REPORT_TYPE,
        "region": region,
        "language": normalized_language,
        "title": title,
        "root_title": title,
        "markets": payloads,
        "markdown_report": review_report,
    }


def _render_market_review_payload_markdown(
    payload: Dict[str, Any],
    *,
    wrapper_title: Optional[str] = None,
) -> str:
    """Render Markdown from the structured market-review payload for file/push compatibility."""
    body = _render_market_review_payload_body(payload)
    if wrapper_title:
        return f"{wrapper_title}\n\n{body}".strip()
    return body.strip()


def _render_market_review_payload_body(payload: Dict[str, Any]) -> str:
    markets = payload.get("markets")
    if isinstance(markets, dict) and markets:
        markdown_report = payload.get("markdown_report")
        if isinstance(markdown_report, str) and markdown_report.strip():
            return markdown_report.strip()
        parts = []
        for market in _MARKET_REVIEW_REGION_ORDER:
            market_payload = markets.get(market)
            if isinstance(market_payload, dict):
                parts.append(_render_single_market_review_payload(market_payload))
        return "\n\n---\n\n".join(part for part in parts if part).strip()
    return _render_single_market_review_payload(payload)


def _render_single_market_review_payload(payload: Dict[str, Any]) -> str:
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        markdown = payload.get("markdown_report")
        return markdown if isinstance(markdown, str) else ""

    title = payload.get("title")
    normalized_title = _normalize_market_review_heading(title)
    lines = []
    if isinstance(title, str) and title.strip():
        lines.extend([f"## {title.strip()}", ""])
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_title = str(section.get("title") or "").strip()
        markdown = str(section.get("markdown") or "").strip()
        if not markdown:
            continue
        should_render_section_title = (
            section_title
            and section.get("key") != "overview"
            and _normalize_market_review_heading(section_title) != normalized_title
        )
        if should_render_section_title:
            lines.extend([f"### {section_title}", ""])
        lines.extend([markdown, ""])
    return "\n".join(lines).strip()


def _normalize_market_review_heading(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lstrip("#").strip().lower().split())


def _persist_market_review_history(
    *,
    review_report: str,
    markdown_report: str,
    region: str,
    config: object,
    query_id: Optional[str] = None,
    market_light_snapshots: Optional[Dict[str, Dict[str, Any]]] = None,
    market_review_payload: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist market review output into the existing analysis history table."""
    try:
        from src.storage import DatabaseManager

        report_language = normalize_report_language(getattr(config, "report_language", "zh"))
        is_vn = str(region or "").strip().lower() == "vn"
        summary = _summarize_market_review(review_report, "vi" if is_vn else report_language)
        if is_vn:
            stock_name = "Tổng kết thị trường"
            operation_advice = "Xem tổng kết"
            trend_prediction = "Tổng kết thị trường"
        elif report_language == "en":
            stock_name = "Market Review"
            operation_advice = "View review"
            trend_prediction = "Market review"
        else:
            stock_name = "大盘复盘"
            operation_advice = "查看复盘"
            trend_prediction = "大盘复盘"

        result = AnalysisResult(
            code=MARKET_REVIEW_HISTORY_CODE,
            name=stock_name,
            sentiment_score=50,
            trend_prediction=trend_prediction,
            operation_advice=operation_advice,
            analysis_summary=summary,
            report_language=report_language,
            news_summary=review_report,
            raw_response=markdown_report,
            data_sources="market_review",
        )

        history_query_id = query_id or f"market_review_{uuid.uuid4().hex}"
        context_snapshot = {
            "report_kind": MARKET_REVIEW_REPORT_TYPE,
            "market_review_region": region,
            "report_language": report_language,
        }
        if market_light_snapshots:
            context_snapshot["market_light_snapshots"] = market_light_snapshots
        if market_review_payload:
            context_snapshot["market_review_payload"] = market_review_payload
        diagnostic_snapshot = current_diagnostic_snapshot()
        if diagnostic_snapshot is not None:
            context_snapshot["diagnostics"] = diagnostic_snapshot
        context_snapshot["analysis_context_pack_overview"] = _build_market_review_context_overview(
            region=region,
            report_language=report_language,
            diagnostic_snapshot=diagnostic_snapshot,
        )

        db = DatabaseManager.get_instance()
        saved_history_id = db.save_analysis_history(
            result=result,
            query_id=history_query_id,
            report_type=MARKET_REVIEW_REPORT_TYPE,
            news_content=review_report,
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        valid_saved_history_id = (
            saved_history_id
            if (
                isinstance(saved_history_id, int)
                and not isinstance(saved_history_id, bool)
                and saved_history_id > 0
            )
            else None
        )
        record_history_run(
            report_saved=bool(saved_history_id),
            metadata_saved=bool(saved_history_id),
            analysis_history_id=valid_saved_history_id,
        )
        _refresh_market_review_history_diagnostics(query_id=history_query_id)
        if saved_history_id:
            logger.info("大盘复盘历史记录已保存: query_id=%s", history_query_id)
        else:
            logger.warning("大盘复盘历史记录保存失败: query_id=%s", history_query_id)
        return saved_history_id
    except Exception as exc:
        record_history_run(
            report_saved=False,
            metadata_saved=False,
            error_message=exc,
        )
        logger.warning("大盘复盘历史记录保存异常，报告文件与推送流程继续: %s", exc, exc_info=True)
        return 0


def _build_market_review_context_overview(
    *,
    region: str,
    report_language: str,
    diagnostic_snapshot: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a low-sensitivity overview block for market-review run-flow rendering."""
    warnings: list[str] = []
    counts = {
        "available": 1,
        "missing": 0,
        "not_supported": 0,
        "fallback": 0,
        "stale": 0,
        "estimated": 0,
        "partial": 0,
        "fetch_failed": 0,
    }
    metadata: Dict[str, Any] = {
        "trigger_source": "market_review",
        "scope": "market_review",
        "report_type": MARKET_REVIEW_REPORT_TYPE,
    }
    if isinstance(diagnostic_snapshot, dict):
        metadata["trigger_source"] = diagnostic_snapshot.get("trigger_source") or metadata["trigger_source"]
        metadata["scope"] = diagnostic_snapshot.get("scope") or metadata["scope"]

    if str(region or "").strip().lower() == "vn":
        label = "Tổng kết thị trường"
    elif report_language == "en":
        label = "Market review"
    else:
        label = "大盘复盘"
    return {
        "pack_version": "market_review/1.0",
        "created_at": datetime.now().isoformat(),
        "subject": {
            "code": MARKET_REVIEW_HISTORY_CODE,
            "stock_name": label,
            "market": region,
        },
        "blocks": [
            {
                "key": MARKET_REVIEW_REPORT_TYPE,
                "label": label,
                "status": "available",
                "source": MARKET_REVIEW_REPORT_TYPE,
                "warnings": warnings,
                "missing_reasons": [],
            }
        ],
        "counts": counts,
        "warnings": warnings,
        "metadata": metadata,
        "data_quality": {
            "level": "good",
            "overall_score": 100,
            "available": 1,
            "total": 1,
            "missing": 0,
        },
    }


def _summarize_market_review(review_report: str, report_language: str) -> str:
    for line in (review_report or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text and not text.startswith("---") and not text.startswith(">"):
            return text[:200]
    if report_language == "vi":
        return "Đã tạo báo cáo tổng kết thị trường."
    return "Market review report generated." if report_language == "en" else "大盘复盘报告已生成。"
