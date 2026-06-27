# -*- coding: utf-8 -*-
"""
Discord 发送提醒服务

职责：
1. 通过 webhook 或 Discord bot API 发送 Discord 消息
"""
import logging
from typing import Optional

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_words


logger = logging.getLogger(__name__)


class DiscordSender:
    
    def __init__(self, config: Config):
        """
        初始化 Discord 配置

        Args:
            config: 配置对象
        """
        self._discord_config = {
            'bot_token': getattr(config, 'discord_bot_token', None),
            'channel_id': getattr(config, 'discord_main_channel_id', None),
            'webhook_url': getattr(config, 'discord_webhook_url', None),
        }
        self._discord_max_words = getattr(config, 'discord_max_words', 2000)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)
    
    def _is_discord_configured(self) -> bool:
        """Kiểm tra cấu hình Discord có đầy đủ không (hỗ trợ Bot hoặc Webhook)"""
        # Chỉ cần cấu hình Webhook hoặc đầy đủ Bot Token+Channel là có thể dùng
        bot_ok = bool(self._discord_config['bot_token'] and self._discord_config['channel_id'])
        webhook_ok = bool(self._discord_config['webhook_url'])
        return bot_ok or webhook_ok
    
    def send_to_discord(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        推送消息到 Discord（支持 Webhook 和 Bot API）
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        # 分割内容，避免单条消息超过 Discord 限制
        try:
            chunks = chunk_content_by_max_words(content, self._discord_max_words)
        except ValueError as e:
            logger.error(f"Tách tin nhắn Discord thất bại: {e}, thử gửi nguyên vẹn.")
            chunks = [content]

        # Ưu tiên sử dụng Webhook (cấu hình đơn giản, quyền thấp)
        if self._discord_config['webhook_url']:
            return all(self._send_discord_webhook(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)

        # Sau đó sử dụng Bot API (quyền cao hơn, cần channel_id)
        if self._discord_config['bot_token'] and self._discord_config['channel_id']:
            return all(self._send_discord_bot(chunk, timeout_seconds=timeout_seconds) for chunk in chunks)

        logger.warning("Cấu hình Discord chưa đầy đủ, bỏ qua gửi thông báo")
        return False

  
    def _send_discord_webhook(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        使用 Webhook 发送消息到 Discord
        
        Discord Webhook 支持 Markdown 格式
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        try:
            payload = {
                'content': content,
                'username': 'Bot phân tích cổ phiếu',
                'avatar_url': 'https://picsum.photos/200'
            }
            
            response = requests.post(
                self._discord_config['webhook_url'],
                json=payload,
                timeout=timeout_seconds or 10,
                verify=self._webhook_verify_ssl
            )
            
            if response.status_code in [200, 204]:
                logger.info("Gửi tin nhắn Discord Webhook thành công")
                return True
            else:
                logger.error(f"Gửi Discord Webhook thất bại: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ngoại lệ khi gửi Discord Webhook: {e}")
            return False
    
    def _send_discord_bot(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        使用 Bot API 发送消息到 Discord
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        try:
            headers = {
                'Authorization': f'Bot {self._discord_config["bot_token"]}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'content': content
            }
            
            url = f'https://discord.com/api/v10/channels/{self._discord_config["channel_id"]}/messages'
            response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds or 10)
            
            if response.status_code == 200:
                logger.info("Gửi tin nhắn Discord Bot thành công")
                return True
            else:
                logger.error(f"Gửi Discord Bot thất bại: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Ngoại lệ khi gửi Discord Bot: {e}")
            return False
