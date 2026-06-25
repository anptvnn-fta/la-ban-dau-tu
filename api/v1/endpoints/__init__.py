# -*- coding: utf-8 -*-
"""
===================================
Khởi tạo module API v1 Endpoints
===================================

Trách nhiệm:
1. Khai báo tất cả các module định tuyến endpoint
"""

from api.v1.endpoints import (
    health,
    analysis,
    history,
    stocks,
    backtest,
    system_config,
    auth,
    agent,
    usage,
    portfolio,
    alerts,
    decision_signals,
    alphasift,
)
__all__ = [
    "health",
    "analysis",
    "history",
    "stocks",
    "backtest",
    "system_config",
    "auth",
    "agent",
    "usage",
    "portfolio",
    "alerts",
    "decision_signals",
    "alphasift",
]
