# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from api.v1.schemas.market_phase import MarketPhaseSummary
from src.schemas.decision_action import DecisionAction


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="仅回测指定股票")
    force: bool = Field(False, description="强制重新计算")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易日数）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="分析记录最小天龄（0=不限）")
    analysis_date_from: Optional[date] = Field(None, description="分析日期起始（含）")
    analysis_date_to: Optional[date] = Field(None, description="分析日期结束（含）")
    limit: int = Field(200, ge=1, le=2000, description="最多处理的分析记录数")


class WalkForwardRequest(BaseModel):
    """Yêu cầu kiểm định trượt tiến (đánh giá tín hiệu kỹ thuật trên dữ liệu lịch sử)."""

    code: str = Field(..., description="Mã cổ phiếu (vd VCB.VN)")
    eval_window_days: int = Field(10, ge=1, le=60, description="Số phiên đối chiếu về sau")
    days: int = Field(400, ge=120, le=1000, description="Số ngày lịch sử dùng để mô phỏng")


class WalkForwardSummary(BaseModel):
    total: Optional[int] = None
    completed: Optional[int] = None
    win: Optional[int] = None
    loss: Optional[int] = None
    neutral: Optional[int] = None
    direction_accuracy_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_return_pct: Optional[float] = None


class WalkForwardItem(BaseModel):
    date: str
    signal: str
    signal_label: str
    signal_score: int = 0
    direction_expected: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    return_pct: Optional[float] = None
    direction_correct: Optional[bool] = None
    outcome: Optional[str] = None


class WalkForwardSignalStat(BaseModel):
    signal: str
    label: str
    count: int = 0
    correct: int = 0
    accuracy_pct: Optional[float] = None


class WalkForwardResponse(BaseModel):
    code: str
    evaluated: int = 0
    eval_window_days: int = 10
    summary: Optional[WalkForwardSummary] = None
    actionable_summary: Optional[WalkForwardSummary] = None
    by_signal: List[WalkForwardSignalStat] = Field(default_factory=list)
    items: List[WalkForwardItem] = Field(default_factory=list)
    signal_distribution: Dict[str, int] = Field(default_factory=dict)
    message: Optional[str] = None
    saved_at: Optional[str] = None


class BacktestRunResponse(BaseModel):
    processed: int = Field(..., description="候选记录数")
    saved: int = Field(..., description="写入回测结果数")
    completed: int = Field(..., description="完成回测数")
    insufficient: int = Field(..., description="数据不足数")
    errors: int = Field(..., description="错误数")
    applied_eval_window_days: Optional[int] = Field(
        ...,
        description="实际生效的评估窗口（交易日数）",
    )
    message: Optional[str] = Field(None, description="空结果或降级时的诊断说明")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="回测筛选与诊断信息")


class BacktestResultItem(BaseModel):
    analysis_history_id: int
    code: str
    stock_name: Optional[str] = None
    analysis_date: Optional[str] = None
    eval_window_days: int
    engine_version: str
    eval_status: str
    evaluated_at: Optional[str] = None
    operation_advice: Optional[str] = None
    action: Optional[DecisionAction] = None
    action_label: Optional[str] = None
    trend_prediction: Optional[str] = None
    market_phase: Optional[str] = None
    market_phase_summary: Optional[MarketPhaseSummary] = None
    position_recommendation: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    max_high: Optional[float] = None
    min_low: Optional[float] = None
    stock_return_pct: Optional[float] = None
    actual_return_pct: Optional[float] = None
    actual_movement: Optional[str] = None
    direction_expected: Optional[str] = None
    direction_correct: Optional[bool] = None
    outcome: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    hit_stop_loss: Optional[bool] = None
    hit_take_profit: Optional[bool] = None
    first_hit: Optional[str] = None
    first_hit_date: Optional[str] = None
    first_hit_trading_days: Optional[int] = None
    simulated_entry_price: Optional[float] = None
    simulated_exit_price: Optional[float] = None
    simulated_exit_reason: Optional[str] = None
    simulated_return_pct: Optional[float] = None


class BacktestResultsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestResultItem] = Field(default_factory=list)


class PerformanceMetrics(BaseModel):
    scope: str
    code: Optional[str] = None
    eval_window_days: int
    engine_version: str
    computed_at: Optional[str] = None

    total_evaluations: int
    completed_count: int
    insufficient_count: int
    long_count: int
    cash_count: int
    win_count: int
    loss_count: int
    neutral_count: int

    direction_accuracy_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    neutral_rate_pct: Optional[float] = None
    avg_stock_return_pct: Optional[float] = None
    avg_simulated_return_pct: Optional[float] = None

    stop_loss_trigger_rate: Optional[float] = None
    take_profit_trigger_rate: Optional[float] = None
    ambiguous_rate: Optional[float] = None
    avg_days_to_first_hit: Optional[float] = None

    advice_breakdown: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
