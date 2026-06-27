# -*- coding: utf-8 -*-
"""ntfy notification sender."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse, urlunparse

import requests

from src.config import Config


logger = logging.getLogger(__name__)


def resolve_ntfy_endpoint(ntfy_url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split NTFY_URL into server root and topic from the final path segment."""
    raw_url = (ntfy_url or "").strip().rstrip("/")
    if not raw_url:
        return None, None

    parsed = urlparse(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None, None

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if not path_segments:
        return None, None

    topic = unquote(path_segments[-1]).strip()
    if not topic:
        return None, None

    root_path = "/".join(path_segments[:-1])
    server_url = urlunparse(
        parsed._replace(
            path=f"/{root_path}" if root_path else "",
            params="",
            query="",
            fragment="",
        )
    ).rstrip("/")

    return server_url, topic


class NtfySender:
    """Send Markdown text notifications through the ntfy JSON publish API."""

    def __init__(self, config: Config):
        self._ntfy_url = getattr(config, "ntfy_url", None)
        self._ntfy_token = getattr(config, "ntfy_token", None)
        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)

    def _is_ntfy_configured(self) -> bool:
        return bool(self._ntfy_url)

    def _resolve_ntfy_endpoint(self) -> Tuple[Optional[str], Optional[str]]:
        return resolve_ntfy_endpoint(self._ntfy_url)

    def send_to_ntfy(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """Publish a notification to ntfy using a JSON body with UTF-8 text."""
        if not self._is_ntfy_configured():
            logger.warning("ntfy URL chưa cấu hình, bỏ qua gửi thông báo")
            return False

        server_url, topic = self._resolve_ntfy_endpoint()
        if not server_url or not topic:
            logger.error("NTFY_URL phải là endpoint đầy đủ có chứa topic path, ví dụ: https://ntfy.sh/my-topic")
            return False

        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 Báo cáo phân tích cổ phiếu - {date_str}"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "daily_stock_analysis",
        }
        token = (self._ntfy_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "topic": topic,
            "title": title,
            "message": content,
            "markdown": True,
        }

        try:
            response = requests.post(
                server_url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds or 10,
                verify=self._webhook_verify_ssl,
            )
            if 200 <= response.status_code < 300:
                logger.info("Gửi tin nhắn ntfy thành công")
                return True

            logger.error("Yêu cầu ntfy thất bại: HTTP %s", response.status_code)
            logger.debug("Nội dung phản hồi ntfy: %s", response.text)
            return False
        except requests.exceptions.Timeout:
            logger.error("Gửi ntfy thất bại: yêu cầu hết thời gian chờ")
            return False
        except requests.exceptions.RequestException as exc:
            logger.error("Gửi ntfy thất bại: lỗi kết nối mạng")
            logger.debug("Loại ngoại lệ ntfy: %s", type(exc).__name__)
            return False
        except Exception as exc:
            logger.error("Gửi ntfy thất bại: ngoại lệ không xác định")
            logger.debug("Loại ngoại lệ ntfy không xác định: %s", type(exc).__name__)
            return False
