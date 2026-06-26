# -*- coding: utf-8 -*-
"""Kiểm định trượt tiến (walk-forward) — đánh giá tín hiệu kỹ thuật trên dữ liệu lịch sử.

Ý tưởng: tại mỗi ngày T trong quá khứ, tính tín hiệu kỹ thuật CHỈ từ dữ liệu tới
ngày T (không nhìn trước), rồi đối chiếu với biến động giá N phiên sau đó (đã biết).
→ Cho kết quả đánh giá NGAY, không cần báo cáo AI cũ ≥ 14 ngày, không gọi LLM.

Tái dùng:
- src/stock_analyzer.StockTrendAnalyzer.analyze(df) → tín hiệu kỹ thuật (causal).
- src/core/backtest_engine.BacktestEngine.evaluate_single / compute_summary → chấm điểm.
"""

import logging
import re
from collections import namedtuple
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_Bar = namedtuple("_Bar", ["date", "open", "high", "low", "close", "volume"])

# Tín hiệu kỹ thuật → khuyến nghị nội bộ mà engine hiểu (buy→tăng, sell→giảm, hold→đi ngang).
_SIGNAL_TO_ADVICE = {
    "STRONG_BUY": "buy", "BUY": "buy",
    "HOLD": "hold", "WAIT": "hold",
    "SELL": "sell", "STRONG_SELL": "sell",
}
_SIGNAL_LABEL_VI = {
    "STRONG_BUY": "Mua mạnh", "BUY": "Mua", "HOLD": "Nắm giữ",
    "WAIT": "Chờ", "SELL": "Bán", "STRONG_SELL": "Bán mạnh",
}

_WARMUP_BARS = 60  # đủ ấm cho MA60 / RSI / MACD


def _to_vn(code: str) -> str:
    c = (code or "").strip().upper()
    if re.match(r"^[A-Z]{2,3}$", c):
        return f"{c}.VN"
    return c


def run_walk_forward(
    code: str,
    *,
    days: int = 400,
    eval_window_days: int = 10,
    step: int = 1,
    max_points: int = 160,
) -> Dict[str, Any]:
    """Chạy kiểm định trượt tiến cho một mã. Trả về summary + items + thông báo."""
    code = _to_vn(code)
    eval_window_days = max(1, min(int(eval_window_days or 10), 60))

    from data_provider.base import DataFetcherManager
    from src.stock_analyzer import StockTrendAnalyzer
    from src.core.backtest_engine import BacktestEngine, EvaluationConfig

    need = _WARMUP_BARS + eval_window_days + 30
    mgr = DataFetcherManager()
    try:
        df, _src = mgr.get_daily_data(code, days=max(int(days or 400), need))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[WalkForward] get_daily_data lỗi cho %s: %s", code, exc)
        df = None

    if df is None or getattr(df, "empty", True):
        return _empty(code, eval_window_days, f"Không lấy được dữ liệu lịch sử cho {code}.")

    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n < _WARMUP_BARS + eval_window_days + 5:
        return _empty(code, eval_window_days,
                      f"Lịch sử của {code} quá ngắn ({n} phiên) để kiểm định {eval_window_days} phiên.")

    analyzer = StockTrendAnalyzer()
    engine = BacktestEngine()
    cfg = EvaluationConfig(eval_window_days=eval_window_days)

    last_idx = n - eval_window_days - 1
    # Liên tục: đánh giá MỖI phiên giao dịch (step=1), giới hạn số điểm gần nhất
    # để giữ thời gian hợp lý (vd 160 phiên ~ 7-8 tháng gần đây).
    eff_step = max(1, int(step or 1))
    start_idx = max(_WARMUP_BARS, last_idx - (max_points - 1) * eff_step)

    results: List[Any] = []
    items: List[Dict[str, Any]] = []
    sig_dist: Dict[str, int] = {}

    i = start_idx
    while i <= last_idx:
        try:
            trend = analyzer.analyze(df.iloc[: i + 1], code)
            sig = getattr(trend.buy_signal, "name", str(trend.buy_signal))
            advice = _SIGNAL_TO_ADVICE.get(sig, "hold")
            start_price = float(df.iloc[i]["close"])
            adate = df.iloc[i]["date"]
            adate = adate.date() if hasattr(adate, "date") else adate
            fwd = df.iloc[i + 1 : i + 1 + eval_window_days]
            forward_bars = [
                _Bar(
                    (rr["date"].date() if hasattr(rr["date"], "date") else rr["date"]),
                    rr.get("open"), rr.get("high"), rr.get("low"), rr.get("close"), rr.get("volume"),
                )
                for _, rr in fwd.iterrows()
            ]
            ev = engine.evaluate_single(
                operation_advice=advice, analysis_date=adate, start_price=start_price,
                forward_bars=forward_bars, stop_loss=None, take_profit=None, config=cfg,
            )
            results.append(SimpleNamespace(**ev))
            sig_dist[sig] = sig_dist.get(sig, 0) + 1
            items.append({
                "date": str(adate),
                "signal": sig,
                "signal_label": _SIGNAL_LABEL_VI.get(sig, sig),
                "signal_score": int(getattr(trend, "signal_score", 0) or 0),
                "direction_expected": ev.get("direction_expected"),
                "start_price": ev.get("start_price"),
                "end_close": ev.get("end_close"),
                "return_pct": ev.get("stock_return_pct"),
                "direction_correct": ev.get("direction_correct"),
                "outcome": ev.get("outcome"),
            })
        except Exception as exc:  # noqa: BLE001
            logger.debug("[WalkForward] đánh giá lỗi tại i=%s: %s", i, exc)
        i += eff_step

    if not results:
        return _empty(code, eval_window_days, "Không tạo được điểm đánh giá nào từ dữ liệu lịch sử.")

    def _summ(res_list: List[Any]) -> Dict[str, Any]:
        if not res_list:
            return None  # type: ignore[return-value]
        raw = engine.compute_summary(
            results=res_list, scope="stock", code=code,
            eval_window_days=eval_window_days, engine_version="v1-wf",
        )
        return {
            "total": raw.get("total_evaluations"),
            "completed": raw.get("completed_count"),
            "win": raw.get("win_count"),
            "loss": raw.get("loss_count"),
            "neutral": raw.get("neutral_count"),
            "direction_accuracy_pct": raw.get("direction_accuracy_pct"),
            "win_rate_pct": raw.get("win_rate_pct"),
            "avg_return_pct": raw.get("avg_stock_return_pct"),
        }

    # Tín hiệu ĐỊNH HƯỚNG (Mua/Bán) — loại bỏ Nắm giữ/Chờ vốn kỳ vọng "đi ngang".
    # Độ chính xác của nhóm này thường cao & ý nghĩa hơn cho việc ra quyết định.
    _DIRECTIONAL = {"STRONG_BUY", "BUY", "SELL", "STRONG_SELL"}
    act_results = [r for r, it in zip(results, items) if it["signal"] in _DIRECTIONAL]

    # Bảng độ chính xác theo từng loại tín hiệu
    by_sig: Dict[str, Dict[str, int]] = {}
    for it in items:
        b = by_sig.setdefault(it["signal"], {"count": 0, "correct": 0, "wrong": 0})
        b["count"] += 1
        if it["direction_correct"] is True:
            b["correct"] += 1
        elif it["direction_correct"] is False:
            b["wrong"] += 1
    by_signal = [
        {
            "signal": k,
            "label": _SIGNAL_LABEL_VI.get(k, k),
            "count": v["count"],
            "correct": v["correct"],
            "accuracy_pct": round(v["correct"] / (v["correct"] + v["wrong"]) * 100, 1)
            if (v["correct"] + v["wrong"]) else None,
        }
        for k, v in sorted(by_sig.items(), key=lambda kv: -kv[1]["count"])
    ]

    return {
        "code": code,
        "evaluated": len(results),
        "eval_window_days": eval_window_days,
        "summary": _summ(results),
        "actionable_summary": _summ(act_results),
        "by_signal": by_signal,
        "items": items[-100:],  # bảng tối đa 100 dòng gần nhất
        "signal_distribution": sig_dist,
        "message": None,
    }


def _empty(code: str, eval_window_days: int, message: str) -> Dict[str, Any]:
    return {
        "code": code, "evaluated": 0, "eval_window_days": eval_window_days,
        "summary": None, "actionable_summary": None, "by_signal": [],
        "items": [], "signal_distribution": {}, "message": message,
    }


# ── Phương án B: kiểm định bằng AI (LLM quyết định trên dữ liệu kỹ thuật point-in-time) ──

def _llm_action(prompt: str) -> Optional[str]:
    """Gọi LLM trả về một hành động: 'buy' / 'sell' / 'hold'. None nếu lỗi."""
    try:
        import litellm  # type: ignore
        from src.config import get_config
        cfg = get_config()
        model = getattr(cfg, "litellm_model", None) or "gemini/gemini-2.5-flash"
        if model.startswith(("gemini/", "vertex_ai/")):
            keys = [k for k in getattr(cfg, "gemini_api_keys", []) if k]
        elif model.startswith("anthropic/"):
            keys = [k for k in getattr(cfg, "anthropic_api_keys", []) if k]
        else:
            keys = [k for k in getattr(cfg, "openai_api_keys", []) if k]
        kwargs: Dict[str, Any] = {
            "model": model,
            # Model suy luận (gemini-2.5-flash...) tiêu tốn "thinking tokens" ẩn → phải để
            # max_tokens lớn, nếu không câu trả lời hiển thị sẽ rỗng/cụt.
            "max_tokens": 512,
            "temperature": 0,
            "timeout": 40,
            "messages": [{"role": "user", "content": prompt}],
        }
        if keys:
            kwargs["api_key"] = keys[0]
        if not model.startswith(("gemini/", "anthropic/", "vertex_ai/")) and getattr(cfg, "openai_base_url", None):
            kwargs["api_base"] = cfg.openai_base_url
        resp = litellm.completion(**kwargs)
        txt = (resp.choices[0].message.content or "").strip().upper()
        if "MUA" in txt or "BUY" in txt:
            return "buy"
        if "BÁN" in txt or "BAN" in txt or "SELL" in txt:
            return "sell"
        return "hold"
    except Exception as exc:  # noqa: BLE001
        logger.warning("[WalkForwardAI] LLM lỗi: %s", exc)
        return None


_ADVICE_LABEL_VI = {"buy": "Mua", "sell": "Bán", "hold": "Quan sát"}


def run_walk_forward_ai(
    code: str,
    *,
    days: int = 400,
    eval_window_days: int = 10,
    samples: int = 8,
) -> Dict[str, Any]:
    """Kiểm định bằng AI: tại ~`samples` mốc quá khứ, cho LLM quyết định dựa trên
    dữ liệu kỹ thuật tính đến mốc đó, rồi đối chiếu giá thực tế sau đó."""
    code = _to_vn(code)
    eval_window_days = max(1, min(int(eval_window_days or 10), 60))

    from data_provider.base import DataFetcherManager
    from src.stock_analyzer import StockTrendAnalyzer
    from src.core.backtest_engine import BacktestEngine, EvaluationConfig

    need = _WARMUP_BARS + eval_window_days + 30
    try:
        df, _src = DataFetcherManager().get_daily_data(code, days=max(int(days or 400), need))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[WalkForwardAI] get_daily_data lỗi cho %s: %s", code, exc)
        df = None
    if df is None or getattr(df, "empty", True):
        return _empty(code, eval_window_days, f"Không lấy được dữ liệu lịch sử cho {code}.")
    df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n < _WARMUP_BARS + eval_window_days + 5:
        return _empty(code, eval_window_days, f"Lịch sử của {code} quá ngắn để kiểm định AI.")

    analyzer = StockTrendAnalyzer()
    engine = BacktestEngine()
    cfg = EvaluationConfig(eval_window_days=eval_window_days)

    last_idx = n - eval_window_days - 1
    samples = max(3, min(int(samples or 10), 16))
    idxs = sorted(set(
        int(_WARMUP_BARS + k * (last_idx - _WARMUP_BARS) / (samples - 1))
        for k in range(samples)
    )) if last_idx > _WARMUP_BARS else [_WARMUP_BARS]

    results: List[Any] = []
    items: List[Dict[str, Any]] = []
    for i in idxs:
        try:
            trend = analyzer.analyze(df.iloc[: i + 1], code)
            price = float(df.iloc[i]["close"])
            adate = df.iloc[i]["date"]; adate = adate.date() if hasattr(adate, "date") else adate
            chg5 = round((price / float(df.iloc[i - 5]["close"]) - 1) * 100, 2) if i >= 5 else None
            chg20 = round((price / float(df.iloc[i - 20]["close"]) - 1) * 100, 2) if i >= 20 else None
            prompt = (
                "Bạn là trader kỹ thuật chứng khoán Việt Nam, quyết đoán. Dựa HOÀN TOÀN vào dữ liệu kỹ thuật "
                f"của mã {code} tính đến ngày {adate} (KHÔNG dùng thông tin sau ngày này):\n"
                f"- Giá đóng cửa: {price:.0f}\n"
                f"- Thay đổi 5 phiên: {chg5}% | 20 phiên: {chg20}%\n"
                f"- Xu hướng: {getattr(trend, 'trend_status', '')}\n"
                f"- MACD: {getattr(trend, 'macd_status', '')}\n"
                f"- RSI(6/12/24): {getattr(trend, 'rsi_6', '')}/{getattr(trend, 'rsi_12', '')}/{getattr(trend, 'rsi_24', '')}\n"
                f"- Độ lệch MA5/10/20: {getattr(trend, 'bias_ma5', '')}/{getattr(trend, 'bias_ma10', '')}/{getattr(trend, 'bias_ma20', '')}\n"
                f"Dự đoán XU HƯỚNG GIÁ {eval_window_days} phiên tới sẽ TĂNG hay GIẢM? "
                "Hãy chọn dứt khoát. Trả lời MUA nếu nghiêng tăng, BÁN nếu nghiêng giảm. "
                "CHỈ dùng QUAN SÁT khi tín hiệu thực sự mâu thuẫn (hạn chế tối đa). "
                "Trả lời đúng MỘT từ: MUA hoặc BÁN hoặc QUAN SÁT."
            )
            advice = _llm_action(prompt)
            if advice is None:
                advice = _SIGNAL_TO_ADVICE.get(getattr(trend.buy_signal, "name", ""), "hold")
            fwd = df.iloc[i + 1 : i + 1 + eval_window_days]
            forward_bars = [
                _Bar(
                    (rr["date"].date() if hasattr(rr["date"], "date") else rr["date"]),
                    rr.get("open"), rr.get("high"), rr.get("low"), rr.get("close"), rr.get("volume"),
                )
                for _, rr in fwd.iterrows()
            ]
            ev = engine.evaluate_single(
                operation_advice=advice, analysis_date=adate, start_price=price,
                forward_bars=forward_bars, stop_loss=None, take_profit=None, config=cfg,
            )
            results.append(SimpleNamespace(**ev))
            items.append({
                "date": str(adate),
                "signal": advice.upper(),
                "signal_label": _ADVICE_LABEL_VI.get(advice, advice),
                "signal_score": int(getattr(trend, "signal_score", 0) or 0),
                "direction_expected": ev.get("direction_expected"),
                "start_price": ev.get("start_price"),
                "end_close": ev.get("end_close"),
                "return_pct": ev.get("stock_return_pct"),
                "direction_correct": ev.get("direction_correct"),
                "outcome": ev.get("outcome"),
            })
        except Exception as exc:  # noqa: BLE001
            logger.debug("[WalkForwardAI] lỗi tại i=%s: %s", i, exc)

    if not results:
        return _empty(code, eval_window_days, "Không tạo được điểm đánh giá AI nào.")

    raw = engine.compute_summary(
        results=results, scope="stock", code=code,
        eval_window_days=eval_window_days, engine_version="v1-wf-ai",
    )
    summary = {
        "total": raw.get("total_evaluations"), "completed": raw.get("completed_count"),
        "win": raw.get("win_count"), "loss": raw.get("loss_count"), "neutral": raw.get("neutral_count"),
        "direction_accuracy_pct": raw.get("direction_accuracy_pct"),
        "win_rate_pct": raw.get("win_rate_pct"), "avg_return_pct": raw.get("avg_stock_return_pct"),
    }
    dist: Dict[str, int] = {}
    for it in items:
        dist[it["signal"]] = dist.get(it["signal"], 0) + 1
    return {
        "code": code, "evaluated": len(results), "eval_window_days": eval_window_days,
        "summary": summary, "actionable_summary": None, "by_signal": [],
        "items": items, "signal_distribution": dist, "message": None,
    }
