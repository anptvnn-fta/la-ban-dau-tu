# -*- coding: utf-8 -*-
"""Gotify notification sender."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests

from src.config import Config


logger = logging.getLogger(__name__)


def resolve_gotify_message_endpoint(gotify_url: Optional[str]) -> Optional[str]:
    """Resolve GOTIFY_URL server base into the fixed /message endpoint."""
    raw_url = (gotify_url or "").strip().rstrip("/")
    if not raw_url:
        return None

    parsed = urlparse(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.query or parsed.fragment:
        return None

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if path_segments and path_segments[-1].lower() == "message":
        return None

    base_url = urlunparse(
        parsed._replace(
            path="/" + "/".join(path_segments) if path_segments else "",
            params="",
            query="",
            fragment="",
        )
    ).rstrip("/")
    return f"{base_url}/message"


class GotifySender:
    """Send Markdown text notifications through Gotify's message API."""

    def __init__(self, config: Config):
        self._gotify_url = getattr(config, "gotify_url", None)
        self._gotify_token = getattr(config, "gotify_token", None)
        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)

    def _is_gotify_configured(self) -> bool:
        return bool((self._gotify_url or "").strip() and (self._gotify_token or "").strip())

    def _resolve_gotify_endpoint(self) -> Optional[str]:
        return resolve_gotify_message_endpoint(self._gotify_url)

    def send_to_gotify(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """Publish a notification to Gotify using JSON and header auth."""
        if not self._is_gotify_configured():
            logger.warning("Cấu hình Gotify chưa đầy đủ, bỏ qua gửi thông báo")
            return False

        endpoint = self._resolve_gotify_endpoint()
        if not endpoint:
            logger.error("GOTIFY_URL phải là URL cơ sở của Gotify server, không bao gồm /message")
            return False

        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 Báo cáo phân tích cổ phiếu - {date_str}"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "daily_stock_analysis",
            "X-Gotify-Key": str(self._gotify_token).strip(),
        }
        payload = {
            "title": title,
            "message": content,
            "extras": {
                "client::display": {
                    "contentType": "text/markdown",
                },
            },
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout_seconds or 10,
                verify=self._webhook_verify_ssl,
            )
            if 200 <= response.status_code < 300:
                logger.info("Gửi tin nhắn Gotify thành công")
                return True

            logger.error("Yêu cầu Gotify thất bại: HTTP %s", response.status_code)
            logger.debug("Nội dung phản hồi Gotify: %s", response.text)
            return False
        except requests.exceptions.Timeout:
            logger.error("Gửi Gotify thất bại: yêu cầu hết thời gian chờ")
            return False
        except requests.exceptions.RequestException as exc:
            logger.error("Gửi Gotify thất bại: lỗi kết nối mạng")
            logger.debug("Loại ngoại lệ Gotify: %s", type(exc).__name__)
            return False
        except Exception as exc:
            logger.error("Gửi Gotify thất bại: ngoại lệ không xác định")
            logger.debug("Loại ngoại lệ Gotify không xác định: %s", type(exc).__name__)
            return False
