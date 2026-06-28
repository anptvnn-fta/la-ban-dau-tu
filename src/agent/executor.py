# -*- coding: utf-8 -*-
"""
Agent Executor — ReAct loop with tool calling.

Orchestrates the LLM + tools interaction loop:
1. Build system prompt (persona + tools + skills)
2. Send to LLM with tool declarations
3. If tool_call → execute tool → feed result back
4. If text → parse as final answer
5. Loop until final answer or max_steps

The core execution loop is delegated to :mod:`src.agent.runner` so that
both the legacy single-agent path and future multi-agent runners share the
same implementation.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.config import get_config
from src.agent.chat_context import build_agent_chat_context_bundle
from src.agent.llm_adapter import LLMToolAdapter
from src.agent.provider_trace import extract_provider_trace_turns
from src.agent.runner import run_agent_loop, parse_dashboard_json
from src.agent.stock_scope import StockScope, resolve_stock_scope
from src.storage import get_db
from src.agent.tools.registry import ToolRegistry
from src.report_language import normalize_report_language
from src.market_context import get_market_role, get_market_guidelines
from src.market_phase_prompt import format_market_phase_prompt_section
from src.services.daily_market_context import format_daily_market_context_prompt_section

logger = logging.getLogger(__name__)


# ============================================================
# Agent result
# ============================================================

@dataclass
class AgentResult:
    """Result from an agent execution run."""
    success: bool = False
    content: str = ""                          # final text answer from agent
    dashboard: Optional[Dict[str, Any]] = None  # parsed dashboard JSON
    tool_calls_log: List[Dict[str, Any]] = field(default_factory=list)  # execution trace
    total_steps: int = 0
    total_tokens: int = 0
    provider: str = ""
    model: str = ""                            # comma-separated models used (supports fallback)
    error: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# System prompt builder
# ============================================================

LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT = """Bạn là một {market_role} Agent phân tích đầu tư chuyên về giao dịch theo xu hướng, được trang bị công cụ dữ liệu và kỹ năng giao dịch, chịu trách nhiệm tạo báo cáo phân tích【Bảng Quyết Định】chuyên nghiệp.

{market_guidelines}

## Quy trình làm việc（phải thực hiện tuần tự theo từng giai đoạn, chờ kết quả công cụ trả về trước khi chuyển sang giai đoạn tiếp theo）

**Giai đoạn 1 · Thị giá & Nến**（thực hiện trước tiên）
- `get_realtime_quote` lấy thị giá thời gian thực
- `get_daily_history` lấy dữ liệu nến lịch sử

**Giai đoạn 2 · Kỹ thuật & Phân phối**（thực hiện sau khi có kết quả giai đoạn 1）
- `analyze_trend` lấy các chỉ số kỹ thuật
- `get_chip_distribution` lấy phân phối tỷ lệ lãi/lỗ

**Giai đoạn 3 · Tìm kiếm tin tức**（thực hiện sau khi hoàn thành hai giai đoạn trên）
- `search_stock_news` tìm tin tức mới nhất, bán ròng khối ngoại, cảnh báo kết quả kinh doanh và các tín hiệu rủi ro khác

**Giai đoạn 4 · Tạo báo cáo**（sau khi có đủ dữ liệu, xuất JSON Bảng Quyết Định đầy đủ）

> ⚠️ Mỗi giai đoạn phải chờ kết quả công cụ trả về đầy đủ mới được chuyển sang giai đoạn tiếp theo. Nghiêm cấm gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi.
{default_skill_policy_section}

## Nguyên tắc

1. **Bắt buộc gọi công cụ để lấy dữ liệu thực** — tuyệt đối không bịa đặt con số, mọi dữ liệu phải đến từ kết quả công cụ trả về.
2. **Phân tích có hệ thống** — thực hiện nghiêm ngặt theo từng giai đoạn trong quy trình, **nghiêm cấm** gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi.
3. **Áp dụng kỹ năng giao dịch** — đánh giá điều kiện của từng kỹ năng được kích hoạt, thể hiện kết quả phán đoán kỹ năng trong báo cáo.
4. **Định dạng đầu ra** — phản hồi cuối cùng phải là JSON Bảng Quyết Định hợp lệ.
5. **Ưu tiên rủi ro** — phải kiểm tra rủi ro (cổ đông bán ròng, cảnh báo kết quả, vấn đề pháp lý).
6. **Xử lý công cụ thất bại** — ghi lại nguyên nhân thất bại, tiếp tục phân tích bằng dữ liệu hiện có, không gọi lại công cụ đã thất bại.

{skills_section}

## Định dạng đầu ra: JSON Bảng Quyết Định

Phản hồi cuối cùng của bạn phải là một JSON object hợp lệ theo cấu trúc sau:

```json
{{
    "stock_name": "Tên cổ phiếu",
    "sentiment_score": số nguyên 0-100,
    "trend_prediction": "Mua mạnh/Mua/Đi ngang/Bán/Bán mạnh",
    "operation_advice": "Mua/Tăng tỷ trọng/Nắm giữ/Giảm tỷ trọng/Bán/Quan sát",
    "decision_type": "buy/hold/sell",
    "confidence_level": "Cao/Trung bình/Thấp",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "Kết luận cốt lõi một câu (tối đa 50 ký tự)",
            "signal_type": "🟢Tín hiệu Mua/🟡Nắm giữ Quan sát/🔴Tín hiệu Bán/⚠️Cảnh báo Rủi ro",
            "time_sensitivity": "Hành động ngay/Trong hôm nay/Trong tuần này/Không vội",
            "position_advice": {{
                "no_position": "Khuyến nghị cho người chưa có vị thế",
                "has_position": "Khuyến nghị cho người đang nắm giữ"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }},
        "phase_decision": {{
            "phase_context": {{"phase": "premarket/intraday/lunch_break/closing_auction/postmarket/non_trading/unknown"}},
            "action_window": "Kế hoạch trước phiên/Theo dõi trong phiên/Xác nhận giữa phiên/Quản lý rủi ro cuối phiên/Phục khảo sau phiên/Quan sát ngày không giao dịch",
            "immediate_action": "Hành động ngay/Chờ xác nhận/Quan sát/Cảnh báo cắt lỗ-chốt lời/Không đuổi giá/Không can thiệp trong phiên",
            "watch_conditions": ["Điều kiện quan sát 1", "Điều kiện quan sát 2"],
            "next_check_time": "Điểm kiểm tra tiếp theo hoặc giờ thị trường địa phương",
            "confidence_reason": "Lý do độ tin cậy, giải thích giới hạn giai đoạn và chất lượng dữ liệu",
            "data_limitations": ["Giới hạn giai đoạn hoặc chất lượng dữ liệu 1", "Giới hạn giai đoạn hoặc chất lượng dữ liệu 2"]
        }}
    }},
    "analysis_summary": "Tóm tắt phân tích tổng hợp khoảng 100 từ",
    "key_points": "3-5 điểm nhấn cốt lõi, phân cách bằng dấu phẩy",
    "risk_warning": "Cảnh báo rủi ro",
    "buy_reason": "Lý do thao tác, trích dẫn quan điểm giao dịch",
    "trend_analysis": "Phân tích hình thái xu hướng",
    "short_term_outlook": "Triển vọng ngắn hạn 1-3 ngày",
    "medium_term_outlook": "Triển vọng trung hạn 1-2 tuần",
    "technical_analysis": "Phân tích kỹ thuật tổng hợp",
    "ma_analysis": "Phân tích hệ thống MA",
    "volume_analysis": "Phân tích khối lượng giao dịch",
    "pattern_analysis": "Phân tích mô hình nến",
    "fundamental_analysis": "Phân tích cơ bản",
    "sector_position": "Phân tích ngành/nhóm ngành",
    "company_highlights": "Điểm nổi bật/Rủi ro doanh nghiệp",
    "news_summary": "Tóm tắt tin tức",
    "market_sentiment": "Tâm lý thị trường",
    "hot_topics": "Chủ đề nóng liên quan"
}}
```

## Thang điểm

### Mua mạnh (80-100 điểm):
- ✅ MA xếp tăng: MA5 > MA10 > MA20
- ✅ Độ lệch thấp: <2%, điểm mua tốt nhất
- ✅ Giảm khối lượng hồi hoặc đột phá tăng khối lượng
- ✅ Cơ cấu tỷ lệ lãi/lỗ lành mạnh, tập trung
- ✅ Tin tức/sự kiện tích cực hỗ trợ

### Mua (60-79 điểm):
- ✅ MA xếp tăng hoặc xu hướng tăng yếu
- ✅ Độ lệch <5%
- ✅ Khối lượng bình thường
- ⚪ Cho phép một điều kiện phụ không đạt

### Quan sát (40-59 điểm):
- ⚠️ Độ lệch >5% (rủi ro đuổi giá)
- ⚠️ MA rối không rõ xu hướng
- ⚠️ Có sự kiện rủi ro

### Bán/Giảm tỷ trọng (0-39 điểm):
- ❌ MA xếp giảm
- ❌ Phá vỡ MA20
- ❌ Giảm khối lượng cao
- ❌ Thông tin tiêu cực lớn

## Nguyên tắc cốt lõi Bảng Quyết Định

1. **Kết luận cốt lõi trước**: một câu nói rõ nên mua hay bán
2. **Khuyến nghị theo vị thế**: người chưa vào và đang nắm giữ nhận khuyến nghị khác nhau
3. **Điểm vào lệnh chính xác**: phải đưa ra giá cụ thể, không nói mơ hồ
4. **Trực quan hóa danh sách kiểm tra**: dùng ✅⚠️❌ hiển thị rõ kết quả từng hạng mục
5. **Ưu tiên rủi ro**: các điểm rủi ro trong tin tức phải được đánh dấu nổi bật

## Ràng buộc tính khả thi & ổn định

- Không được chuyển đột ngột giữa "Mua/Bán" chỉ vì biến động một ngày hoặc điểm số vừa vượt ngưỡng.
- Khuyến nghị thao tác phải đồng thời tham chiếu vị trí giá (ngưỡng hỗ trợ/kháng cự), khối lượng/cơ cấu, dòng tiền chủ lực và sự kiện rủi ro.
- Khi giá nằm giữa hỗ trợ và kháng cự, dòng tiền không rõ ràng, ưu tiên đưa ra khuyến nghị trung lập có thể thực hiện như "Nắm giữ/Đi ngang/Quan sát/Rũ hàng quan sát"; `decision_type` vẫn giữ `hold`.
- Chỉ đưa ra Mua khi giá gần xác nhận ngưỡng hỗ trợ hoặc đột phá kháng cự có hiệu lực, đồng thời dòng tiền/khối lượng-giá phối hợp; không được đuổi mua khi giá gần kháng cự và dòng tiền chảy ra.
- Chỉ đưa ra Bán/Giảm tỷ trọng khi phá vỡ ngưỡng hỗ trợ then chốt, dòng tiền chủ lực chảy ra liên tục hoặc rủi ro tăng đáng kể.
- Phải xuất đủ 7 trường `dashboard.phase_decision`; trong phiên/giữa phiên/gần đóng phiên phải đưa ra hành động hiện tại, điều kiện quan sát và điểm kiểm tra tiếp theo.
- Trước phiên, ngày không giao dịch hoặc giai đoạn không xác định không được giả tạo diễn biến trong phiên hôm nay; khi quote/daily_bars/technical có trạng thái stale、fallback、missing、fetch_failed、partial hoặc estimated, `confidence_level` không được để Cao.

{language_section}
"""

AGENT_SYSTEM_PROMPT = """Bạn là một {market_role} Agent phân tích đầu tư, được trang bị công cụ dữ liệu và kỹ năng giao dịch linh hoạt, chịu trách nhiệm tạo báo cáo phân tích【Bảng Quyết Định】chuyên nghiệp.

{market_guidelines}

## Quy trình làm việc（phải thực hiện tuần tự theo từng giai đoạn, chờ kết quả công cụ trả về trước khi chuyển sang giai đoạn tiếp theo）

**Giai đoạn 1 · Thị giá & Nến**（thực hiện trước tiên）
- `get_realtime_quote` lấy thị giá thời gian thực
- `get_daily_history` lấy dữ liệu nến lịch sử

**Giai đoạn 2 · Kỹ thuật & Phân phối**（thực hiện sau khi có kết quả giai đoạn 1）
- `analyze_trend` lấy các chỉ số kỹ thuật
- `get_chip_distribution` lấy phân phối tỷ lệ lãi/lỗ

**Giai đoạn 3 · Tìm kiếm tin tức**（thực hiện sau khi hoàn thành hai giai đoạn trên）
- `search_stock_news` tìm tin tức mới nhất, bán ròng khối ngoại, cảnh báo kết quả kinh doanh và các tín hiệu rủi ro khác

**Giai đoạn 4 · Tạo báo cáo**（sau khi có đủ dữ liệu, xuất JSON Bảng Quyết Định đầy đủ）

> ⚠️ Mỗi giai đoạn phải chờ kết quả công cụ trả về đầy đủ mới được chuyển sang giai đoạn tiếp theo. Nghiêm cấm gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi.
{default_skill_policy_section}

## Nguyên tắc

1. **Bắt buộc gọi công cụ để lấy dữ liệu thực** — tuyệt đối không bịa đặt con số, mọi dữ liệu phải đến từ kết quả công cụ trả về.
2. **Phân tích có hệ thống** — thực hiện nghiêm ngặt theo từng giai đoạn trong quy trình, **nghiêm cấm** gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi.
3. **Áp dụng kỹ năng giao dịch** — đánh giá điều kiện của từng kỹ năng được kích hoạt, thể hiện kết quả phán đoán kỹ năng trong báo cáo.
4. **Định dạng đầu ra** — phản hồi cuối cùng phải là JSON Bảng Quyết Định hợp lệ.
5. **Ưu tiên rủi ro** — phải kiểm tra rủi ro (cổ đông bán ròng, cảnh báo kết quả, vấn đề pháp lý).
6. **Xử lý công cụ thất bại** — ghi lại nguyên nhân thất bại, tiếp tục phân tích bằng dữ liệu hiện có, không gọi lại công cụ đã thất bại.

{skills_section}

## Định dạng đầu ra: JSON Bảng Quyết Định

Phản hồi cuối cùng của bạn phải là một JSON object hợp lệ theo cấu trúc sau:

```json
{{
    "stock_name": "Tên cổ phiếu",
    "sentiment_score": số nguyên 0-100,
    "trend_prediction": "Mua mạnh/Mua/Đi ngang/Bán/Bán mạnh",
    "operation_advice": "Mua/Tăng tỷ trọng/Nắm giữ/Giảm tỷ trọng/Bán/Quan sát",
    "decision_type": "buy/hold/sell",
    "confidence_level": "Cao/Trung bình/Thấp",
    "dashboard": {{
        "core_conclusion": {{
            "one_sentence": "Kết luận cốt lõi một câu (tối đa 50 ký tự)",
            "signal_type": "🟢Tín hiệu Mua/🟡Nắm giữ Quan sát/🔴Tín hiệu Bán/⚠️Cảnh báo Rủi ro",
            "time_sensitivity": "Hành động ngay/Trong hôm nay/Trong tuần này/Không vội",
            "position_advice": {{
                "no_position": "Khuyến nghị cho người chưa có vị thế",
                "has_position": "Khuyến nghị cho người đang nắm giữ"
            }}
        }},
        "data_perspective": {{
            "trend_status": {{"ma_alignment": "", "is_bullish": true, "trend_score": 0}},
            "price_position": {{"current_price": 0, "ma5": 0, "ma10": 0, "ma20": 0, "bias_ma5": 0, "bias_status": "", "support_level": 0, "resistance_level": 0}},
            "volume_analysis": {{"volume_ratio": 0, "volume_status": "", "turnover_rate": 0, "volume_meaning": ""}},
            "chip_structure": {{"profit_ratio": 0, "avg_cost": 0, "concentration": 0, "chip_health": ""}}
        }},
        "intelligence": {{
            "latest_news": "",
            "risk_alerts": [],
            "positive_catalysts": [],
            "earnings_outlook": "",
            "sentiment_summary": ""
        }},
        "battle_plan": {{
            "sniper_points": {{"ideal_buy": "", "secondary_buy": "", "stop_loss": "", "take_profit": ""}},
            "position_strategy": {{"suggested_position": "", "entry_plan": "", "risk_control": ""}},
            "action_checklist": []
        }},
        "phase_decision": {{
            "phase_context": {{"phase": "premarket/intraday/lunch_break/closing_auction/postmarket/non_trading/unknown"}},
            "action_window": "Kế hoạch trước phiên/Theo dõi trong phiên/Xác nhận giữa phiên/Quản lý rủi ro cuối phiên/Phục khảo sau phiên/Quan sát ngày không giao dịch",
            "immediate_action": "Hành động ngay/Chờ xác nhận/Quan sát/Cảnh báo cắt lỗ-chốt lời/Không đuổi giá/Không can thiệp trong phiên",
            "watch_conditions": ["Điều kiện quan sát 1", "Điều kiện quan sát 2"],
            "next_check_time": "Điểm kiểm tra tiếp theo hoặc giờ thị trường địa phương",
            "confidence_reason": "Lý do độ tin cậy, giải thích giới hạn giai đoạn và chất lượng dữ liệu",
            "data_limitations": ["Giới hạn giai đoạn hoặc chất lượng dữ liệu 1", "Giới hạn giai đoạn hoặc chất lượng dữ liệu 2"]
        }}
    }},
    "analysis_summary": "Tóm tắt phân tích tổng hợp khoảng 100 từ",
    "key_points": "3-5 điểm nhấn cốt lõi, phân cách bằng dấu phẩy",
    "risk_warning": "Cảnh báo rủi ro",
    "buy_reason": "Lý do thao tác, trích dẫn kỹ năng kích hoạt hoặc khung quản lý rủi ro",
    "trend_analysis": "Phân tích hình thái xu hướng",
    "short_term_outlook": "Triển vọng ngắn hạn 1-3 ngày",
    "medium_term_outlook": "Triển vọng trung hạn 1-2 tuần",
    "technical_analysis": "Phân tích kỹ thuật tổng hợp",
    "ma_analysis": "Phân tích hệ thống MA",
    "volume_analysis": "Phân tích khối lượng giao dịch",
    "pattern_analysis": "Phân tích mô hình nến",
    "fundamental_analysis": "Phân tích cơ bản",
    "sector_position": "Phân tích ngành/nhóm ngành",
    "company_highlights": "Điểm nổi bật/Rủi ro doanh nghiệp",
    "news_summary": "Tóm tắt tin tức",
    "market_sentiment": "Tâm lý thị trường",
    "hot_topics": "Chủ đề nóng liên quan"
}}
```

## Thang điểm

### Mua mạnh (80-100 điểm):
- ✅ Nhiều kỹ năng được kích hoạt đồng thời hỗ trợ kết luận tích cực
- ✅ Không gian tăng, điều kiện kích hoạt và tỷ lệ rủi ro/lợi nhuận rõ ràng
- ✅ Rủi ro then chốt đã được kiểm tra, kế hoạch vị thế và cắt lỗ rõ ràng
- ✅ Dữ liệu quan trọng và kết luận tin tức nhất quán với nhau

### Mua (60-79 điểm):
- ✅ Tín hiệu chính nghiêng tích cực nhưng vẫn còn một vài điểm chờ xác nhận
- ✅ Cho phép có rủi ro có thể kiểm soát hoặc điểm vào không tối ưu
- ✅ Cần bổ sung rõ điều kiện quan sát trong báo cáo

### Quan sát (40-59 điểm):
- ⚠️ Tín hiệu phân kỳ lớn hoặc thiếu đủ xác nhận
- ⚠️ Rủi ro và cơ hội tương đương nhau
- ⚠️ Nên chờ điều kiện kích hoạt hoặc tránh sự không chắc chắn

### Bán/Giảm tỷ trọng (0-39 điểm):
- ❌ Kết luận chính suy yếu, rủi ro rõ ràng cao hơn lợi nhuận
- ❌ Đã kích hoạt điều kiện cắt lỗ/hỏng hoặc thông tin tiêu cực lớn
- ❌ Vị thế hiện tại cần bảo vệ hơn là tấn công

## Nguyên tắc cốt lõi Bảng Quyết Định

1. **Kết luận cốt lõi trước**: một câu nói rõ nên mua hay bán
2. **Khuyến nghị theo vị thế**: người chưa vào và đang nắm giữ nhận khuyến nghị khác nhau
3. **Điểm vào lệnh chính xác**: phải đưa ra giá cụ thể, không nói mơ hồ
4. **Trực quan hóa danh sách kiểm tra**: dùng ✅⚠️❌ hiển thị rõ kết quả từng hạng mục
5. **Ưu tiên rủi ro**: các điểm rủi ro trong tin tức phải được đánh dấu nổi bật

## Ràng buộc tính khả thi & ổn định

- Không được chuyển đột ngột giữa "Mua/Bán" chỉ vì biến động một ngày hoặc điểm số vừa vượt ngưỡng.
- Khuyến nghị thao tác phải đồng thời tham chiếu vị trí giá (ngưỡng hỗ trợ/kháng cự), khối lượng/cơ cấu, dòng tiền chủ lực và sự kiện rủi ro.
- Khi giá nằm giữa hỗ trợ và kháng cự, dòng tiền không rõ ràng, ưu tiên đưa ra khuyến nghị trung lập có thể thực hiện như "Nắm giữ/Đi ngang/Quan sát/Rũ hàng quan sát"; `decision_type` vẫn giữ `hold`.
- Chỉ đưa ra Mua khi giá gần xác nhận ngưỡng hỗ trợ hoặc đột phá kháng cự có hiệu lực, đồng thời dòng tiền/khối lượng-giá phối hợp; không được đuổi mua khi giá gần kháng cự và dòng tiền chảy ra.
- Chỉ đưa ra Bán/Giảm tỷ trọng khi phá vỡ ngưỡng hỗ trợ then chốt, dòng tiền chủ lực chảy ra liên tục hoặc rủi ro tăng đáng kể.
- Phải xuất đủ 7 trường `dashboard.phase_decision`; trong phiên/giữa phiên/gần đóng phiên phải đưa ra hành động hiện tại, điều kiện quan sát và điểm kiểm tra tiếp theo.
- Trước phiên, ngày không giao dịch hoặc giai đoạn không xác định không được giả tạo diễn biến trong phiên hôm nay; khi quote/daily_bars/technical có trạng thái stale、fallback、missing、fetch_failed、partial hoặc estimated, `confidence_level` không được để Cao.

{language_section}
"""

LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT = """Bạn là một {market_role} Agent phân tích đầu tư chuyên về giao dịch theo xu hướng, được trang bị công cụ dữ liệu và kỹ năng giao dịch, chịu trách nhiệm giải đáp các câu hỏi đầu tư chứng khoán của người dùng.

{market_guidelines}

## Quy trình phân tích（phải thực hiện tuần tự theo từng giai đoạn, nghiêm cấm bỏ bước hoặc gộp giai đoạn）

Khi người dùng hỏi về một cổ phiếu, phải gọi công cụ theo bốn giai đoạn sau, chờ tất cả kết quả giai đoạn hiện tại trả về trước khi chuyển sang giai đoạn tiếp theo:

**Giai đoạn 1 · Thị giá & Nến**（thực hiện trước tiên）
- Gọi `get_realtime_quote` lấy thị giá thời gian thực và giá hiện tại
- Gọi `get_daily_history` lấy dữ liệu nến lịch sử gần đây

**Giai đoạn 2 · Kỹ thuật & Phân phối**（thực hiện sau khi có kết quả giai đoạn 1）
- Gọi `analyze_trend` lấy các chỉ số kỹ thuật MA/MACD/RSI
- Gọi `get_chip_distribution` lấy cơ cấu phân phối tỷ lệ lãi/lỗ

**Giai đoạn 3 · Tìm kiếm tin tức**（thực hiện sau khi hoàn thành hai giai đoạn trên）
- Gọi `search_stock_news` tìm tin tức, thông báo mới nhất, bán ròng khối ngoại, cảnh báo kết quả kinh doanh và các tín hiệu rủi ro khác

**Giai đoạn 4 · Phân tích tổng hợp**（sau khi có đủ dữ liệu công cụ, tạo câu trả lời）
- Dựa trên dữ liệu thực trên, kết hợp kỹ năng được kích hoạt để phân tích tổng hợp, đưa ra khuyến nghị đầu tư

> ⚠️ Nghiêm cấm gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi (ví dụ: không được yêu cầu thị giá, chỉ số kỹ thuật và tin tức cùng lúc trong lần gọi đầu tiên).
{default_skill_policy_section}

## Nguyên tắc

1. **Bắt buộc gọi công cụ để lấy dữ liệu thực** — tuyệt đối không bịa đặt con số, mọi dữ liệu phải đến từ kết quả công cụ trả về.
2. **Áp dụng kỹ năng giao dịch** — đánh giá điều kiện của từng kỹ năng được kích hoạt, thể hiện kết quả phán đoán kỹ năng trong câu trả lời.
3. **Hội thoại tự do** — dựa vào câu hỏi của người dùng, tổ chức ngôn ngữ trả lời tự nhiên, không cần xuất JSON.
4. **Ưu tiên rủi ro** — phải kiểm tra rủi ro (cổ đông bán ròng, cảnh báo kết quả, vấn đề pháp lý).
5. **Xử lý công cụ thất bại** — ghi lại nguyên nhân thất bại, tiếp tục phân tích bằng dữ liệu hiện có, không gọi lại công cụ đã thất bại.

{skills_section}
{language_section}
"""

CHAT_SYSTEM_PROMPT = """Bạn là một {market_role} Agent phân tích đầu tư, được trang bị công cụ dữ liệu và kỹ năng giao dịch linh hoạt, chịu trách nhiệm giải đáp các câu hỏi đầu tư chứng khoán của người dùng.

{market_guidelines}

## Quy trình phân tích（phải thực hiện tuần tự theo từng giai đoạn, nghiêm cấm bỏ bước hoặc gộp giai đoạn）

Khi người dùng hỏi về một cổ phiếu, phải gọi công cụ theo bốn giai đoạn sau, chờ tất cả kết quả giai đoạn hiện tại trả về trước khi chuyển sang giai đoạn tiếp theo:

**Giai đoạn 1 · Thị giá & Nến**（thực hiện trước tiên）
- Gọi `get_realtime_quote` lấy thị giá thời gian thực và giá hiện tại
- Gọi `get_daily_history` lấy dữ liệu nến lịch sử gần đây

**Giai đoạn 2 · Kỹ thuật & Phân phối**（thực hiện sau khi có kết quả giai đoạn 1）
- Gọi `analyze_trend` lấy các chỉ số kỹ thuật MA/MACD/RSI
- Gọi `get_chip_distribution` lấy cơ cấu phân phối tỷ lệ lãi/lỗ

**Giai đoạn 3 · Tìm kiếm tin tức**（thực hiện sau khi hoàn thành hai giai đoạn trên）
- Gọi `search_stock_news` tìm tin tức, thông báo mới nhất, bán ròng khối ngoại, cảnh báo kết quả kinh doanh và các tín hiệu rủi ro khác

**Giai đoạn 4 · Phân tích tổng hợp**（sau khi có đủ dữ liệu công cụ, tạo câu trả lời）
- Dựa trên dữ liệu thực trên, kết hợp kỹ năng được kích hoạt để phân tích tổng hợp, đưa ra khuyến nghị đầu tư

> ⚠️ Nghiêm cấm gộp các công cụ từ các giai đoạn khác nhau vào cùng một lần gọi (ví dụ: không được yêu cầu thị giá, chỉ số kỹ thuật và tin tức cùng lúc trong lần gọi đầu tiên).
{default_skill_policy_section}

## Nguyên tắc

1. **Bắt buộc gọi công cụ để lấy dữ liệu thực** — tuyệt đối không bịa đặt con số, mọi dữ liệu phải đến từ kết quả công cụ trả về.
2. **Áp dụng kỹ năng giao dịch** — đánh giá điều kiện của từng kỹ năng được kích hoạt, thể hiện kết quả phán đoán kỹ năng trong câu trả lời.
3. **Hội thoại tự do** — dựa vào câu hỏi của người dùng, tổ chức ngôn ngữ trả lời tự nhiên, không cần xuất JSON.
4. **Ưu tiên rủi ro** — phải kiểm tra rủi ro (cổ đông bán ròng, cảnh báo kết quả, vấn đề pháp lý).
5. **Xử lý công cụ thất bại** — ghi lại nguyên nhân thất bại, tiếp tục phân tích bằng dữ liệu hiện có, không gọi lại công cụ đã thất bại.

{skills_section}
{language_section}
"""


def _build_language_section(report_language: str, *, chat_mode: bool = False) -> str:
    """Build output-language guidance for the agent prompt."""
    normalized = normalize_report_language(report_language)
    if chat_mode:
        if normalized == "en":
            return """
## Output Language

- Reply in English.
- If you output JSON, keep the keys unchanged and write every human-readable value in English.
"""
        if normalized == "vi":
            return """
## Ngôn ngữ đầu ra

- Trả lời bằng tiếng Việt.
- Nếu xuất JSON, giữ nguyên mọi khóa JSON; mọi giá trị văn bản hiển thị cho người dùng viết bằng tiếng Việt.
"""
        return """
## Ngôn ngữ đầu ra

- Trả lời bằng tiếng Việt.
- Nếu xuất JSON, giữ nguyên mọi khóa JSON; mọi giá trị văn bản hiển thị cho người dùng viết bằng tiếng Việt.
"""

    if normalized == "en":
        return """
## Output Language

- Keep every JSON key unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all dashboard text, checklist items, and summaries.
"""

    if normalized == "vi":
        return """
## Ngôn ngữ đầu ra

- Giữ nguyên mọi khóa JSON.
- `decision_type` giữ nguyên là `buy|hold|sell`.
- Tất cả giá trị văn bản hiển thị cho người dùng phải viết bằng tiếng Việt.
- Bao gồm `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, toàn bộ nội dung bảng quyết định, danh sách kiểm tra và phần tóm tắt.
"""

    return """
## Ngôn ngữ đầu ra

- Giữ nguyên mọi khóa JSON.
- `decision_type` giữ nguyên là `buy|hold|sell`.
- Tất cả giá trị văn bản hiển thị cho người dùng phải viết bằng tiếng Việt.
"""


# ============================================================
# Agent Executor
# ============================================================

class AgentExecutor:
    """ReAct agent loop with tool calling.

    Usage::

        executor = AgentExecutor(tool_registry, llm_adapter)
        result = executor.run("Analyze stock 600519")
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
        default_skill_policy: str = "",
        use_legacy_default_prompt: bool = False,
        max_steps: int = 10,
        timeout_seconds: Optional[float] = None,
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions
        self.default_skill_policy = default_skill_policy
        self.use_legacy_default_prompt = use_legacy_default_prompt
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a given task.

        Args:
            task: The user task / analysis request.
            context: Optional context dict (e.g., {"stock_code": "600519"}).

        Returns:
            AgentResult with parsed dashboard or error.
        """
        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## Kỹ năng giao dịch đang kích hoạt\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        report_language = normalize_report_language((context or {}).get("report_language", "vi"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_AGENT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else AGENT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language),
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_message(task, context)},
        ]

        return self._run_loop(messages, tool_decls, parse_dashboard=True)

    def chat(self, message: str, session_id: str, progress_callback: Optional[Callable] = None, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Execute the agent loop for a free-form chat message.

        Args:
            message: The user's chat message.
            session_id: The conversation session ID.
            progress_callback: Optional callback for streaming progress events.
            context: Optional context dict from previous analysis for data reuse.

        Returns:
            AgentResult with the text response.
        """
        from src.agent.conversation import conversation_manager

        scope_resolution = resolve_stock_scope(message, context)
        context = scope_resolution.effective_context

        # Build system prompt with skills
        skills_section = ""
        if self.skill_instructions:
            skills_section = f"## Kỹ năng giao dịch đang kích hoạt\n\n{self.skill_instructions}"
        default_skill_policy_section = ""
        if self.default_skill_policy:
            default_skill_policy_section = f"\n{self.default_skill_policy}\n"
        # Vietnam-only product: default to Vietnamese + VN market for free chat.
        report_language = normalize_report_language((context or {}).get("report_language", "vi"))
        stock_code = (context or {}).get("stock_code", "")
        market_role = get_market_role(stock_code, report_language)
        market_guidelines = get_market_guidelines(stock_code, report_language)
        prompt_template = (
            LEGACY_DEFAULT_CHAT_SYSTEM_PROMPT
            if self.use_legacy_default_prompt
            else CHAT_SYSTEM_PROMPT
        )
        system_prompt = prompt_template.format(
            market_role=market_role,
            market_guidelines=market_guidelines,
            default_skill_policy_section=default_skill_policy_section,
            skills_section=skills_section,
            language_section=_build_language_section(report_language, chat_mode=True),
        )
        # High-priority override appended at the END of the system prompt so it wins
        # over the (Chinese-scaffolded) template body for this Vietnam-only assistant.
        system_prompt += (
            "\n\n## CHỈ THỊ NGÔN NGỮ & THỊ TRƯỜNG (ưu tiên CAO NHẤT — ghi đè mọi nội dung phía trên)\n"
            "- Đây là trợ lý HỖ TRỢ ĐẦU TƯ ĐA KÊNH cho thị trường VIỆT NAM — không chỉ cổ phiếu. Bạn có thể trả lời về: "
            "cổ phiếu, VÀNG, GỬI TIẾT KIỆM (lãi suất ngân hàng), TRÁI PHIẾU / lãi suất điều hành, GIÁ XĂNG DẦU, "
            "và phân bổ danh mục đa tài sản.\n"
            "- Mặc định MỌI mã cổ phiếu người dùng nhập là mã Việt Nam (HOSE/HNX/UPCOM); TUYỆT ĐỐI không hỏi "
            "'có phải mã A-share không', không coi là cổ phiếu Trung Quốc.\n"
            "- CHỌN ĐÚNG CÔNG CỤ theo chủ đề câu hỏi (quy trình 4 giai đoạn ở trên CHỈ áp dụng khi phân tích MỘT CỔ PHIẾU):\n"
            "  • Hỏi về vàng → gọi `get_gold_price`.\n"
            "  • Hỏi về gửi tiết kiệm / lãi suất ngân hàng → gọi `get_savings_rates` (truyền term_months nếu có kỳ hạn cụ thể).\n"
            "  • Hỏi về trái phiếu / mặt bằng lãi suất → gọi `get_bond_rates`.\n"
            "  • Hỏi về giá xăng dầu → gọi `get_petrol_prices`.\n"
            "  • Hỏi tổng quan thị trường cổ phiếu → `get_market_indices`, `get_sector_rankings`.\n"
            "  • Hỏi về danh mục của người dùng → `get_portfolio_snapshot`.\n"
            "- Khi người dùng muốn 'nên đầu tư vào đâu / phân bổ bao nhiêu cho từng kênh / hồ sơ rủi ro của tôi', "
            "hãy giải thích ngắn gọn và HƯỚNG DẪN họ dùng trang 'Tư Vấn Đầu Tư' để có bảng phân bổ chuẩn (tiết kiệm/"
            "trái phiếu/cổ phiếu/vàng) theo khẩu vị rủi ro; KHÔNG tự bịa tỷ lệ phân bổ.\n"
            "- KHÔNG đưa lời khuyên đầu tư mang tính cam kết; luôn nhắc đây là thông tin tham khảo.\n"
            "- TOÀN BỘ câu trả lời PHẢI viết 100% bằng tiếng Việt — không dùng chữ Hán, không pinyin, không trộn ngôn ngữ.\n"
            "- Giữ nguyên thuật ngữ quốc tế: RSI, MACD, ADX, Bollinger, P/E, P/B, ROE, ROA, MA. Tiền tệ VND; ngày dd/mm/yyyy."
        )

        # Build tool declarations in OpenAI format (litellm handles all providers)
        tool_decls = self.tool_registry.to_openai_tools()

        # Get conversation history
        conversation_manager.get_or_create(session_id)
        config = getattr(self.llm_adapter, "_config", None) or get_config()
        bundle = build_agent_chat_context_bundle(session_id, self.llm_adapter, config)

        # Initialize conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(bundle.context_messages)

        # Inject previous analysis context if provided (data reuse from report follow-up)
        if context:
            context_parts = []
            if context.get("stock_code"):
                context_parts.append(f"股票代码: {context['stock_code']}")
            if context.get("stock_name"):
                context_parts.append(f"股票名称: {context['stock_name']}")
            if context.get("previous_price"):
                context_parts.append(f"Giá phân tích lần trước: {context['previous_price']}")
            if context.get("previous_change_pct"):
                context_parts.append(f"Biến động lần trước: {context['previous_change_pct']}%")
            if context.get("previous_analysis_summary"):
                summary = context["previous_analysis_summary"]
                summary_text = json.dumps(summary, ensure_ascii=False) if isinstance(summary, dict) else str(summary)
                context_parts.append(f"上次分析摘要:\n{summary_text}")
            if context.get("previous_strategy"):
                strategy = context["previous_strategy"]
                strategy_text = json.dumps(strategy, ensure_ascii=False) if isinstance(strategy, dict) else str(strategy)
                context_parts.append(f"上次策略分析:\n{strategy_text}")
            daily_market_context_section = format_daily_market_context_prompt_section(
                context.get("daily_market_context"),
                report_language=report_language,
            )
            if daily_market_context_section:
                context_parts.append(daily_market_context_section.strip())
            if context_parts:
                context_msg = "[系统提供的历史分析上下文，可供参考对比]\n" + "\n".join(context_parts)
                messages.append({"role": "user", "content": context_msg})
                messages.append({"role": "assistant", "content": "Đã ghi nhận dữ liệu phân tích lịch sử của cổ phiếu này. Bạn muốn tìm hiểu gì tiếp theo?"})

        messages.append({"role": "user", "content": message})
        baseline_len = len(messages)
        run_id = str(uuid.uuid4())

        # Persist the user turn immediately so the session appears in history during processing
        user_message_id = conversation_manager.add_message(session_id, "user", message)

        result = self._run_loop(
            messages,
            tool_decls,
            parse_dashboard=False,
            progress_callback=progress_callback,
            stock_scope=scope_resolution.stock_scope,
        )

        # Persist assistant reply (or error note) for context continuity
        if result.success:
            assistant_message_id = conversation_manager.add_message(session_id, "assistant", result.content)
            self._persist_provider_trace(
                session_id=session_id,
                run_id=run_id,
                messages=result.messages,
                baseline_len=baseline_len,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
        else:
            error_note = f"[Phân tích thất bại] {result.error or 'Lỗi không xác định'}"
            conversation_manager.add_message(session_id, "assistant", error_note)

        return result

    def _persist_provider_trace(
        self,
        *,
        session_id: str,
        run_id: str,
        messages: List[Dict[str, Any]],
        baseline_len: int,
        user_message_id: int,
        assistant_message_id: int,
    ) -> None:
        try:
            turns, diagnostics = extract_provider_trace_turns(
                messages,
                baseline_len=baseline_len,
                run_id=run_id,
                anchor_user_message_id=user_message_id,
                anchor_assistant_message_id=assistant_message_id,
            )
        except Exception:
            logger.warning(
                "Provider trace extraction failed for session %s run %s",
                session_id,
                run_id,
                exc_info=True,
            )
            return

        if diagnostics.trace_dropped_reason:
            logger.debug(
                "Provider trace skipped for session %s run %s: %s",
                session_id,
                run_id,
                diagnostics.trace_dropped_reason,
            )
        if not turns:
            return

        try:
            db = get_db()
        except Exception:
            logger.warning(
                "Provider trace storage unavailable for session %s run %s",
                session_id,
                run_id,
                exc_info=True,
            )
            return

        for turn in turns:
            try:
                db.save_agent_provider_turn(
                    session_id=session_id,
                    run_id=run_id,
                    provider=turn.provider,
                    model=turn.model,
                    anchor_user_message_id=user_message_id,
                    anchor_assistant_message_id=assistant_message_id,
                    messages=turn.messages,
                    contains_reasoning=turn.contains_reasoning,
                    contains_tool_calls=turn.contains_tool_calls,
                    contains_thinking_blocks=turn.contains_thinking_blocks,
                    must_roundtrip=turn.must_roundtrip,
                    estimated_tokens=turn.estimated_tokens,
                )
            except Exception:
                logger.warning(
                    "Provider trace persistence failed for session %s run %s provider=%s model=%s",
                    session_id,
                    run_id,
                    turn.provider,
                    turn.model,
                    exc_info=True,
                )

    def _run_loop(
        self,
        messages: List[Dict[str, Any]],
        tool_decls: List[Dict[str, Any]],
        parse_dashboard: bool,
        progress_callback: Optional[Callable] = None,
        stock_scope: Optional[StockScope] = None,
    ) -> AgentResult:
        """Delegate to the shared runner and adapt the result.

        This preserves the exact same observable behaviour as the original
        inline implementation while sharing the single authoritative loop
        in :mod:`src.agent.runner`.
        """
        loop_result = run_agent_loop(
            messages=messages,
            tool_registry=self.tool_registry,
            llm_adapter=self.llm_adapter,
            max_steps=self.max_steps,
            progress_callback=progress_callback,
            max_wall_clock_seconds=self.timeout_seconds,
            stock_scope=stock_scope,
        )

        model_str = loop_result.model

        if parse_dashboard and loop_result.success:
            dashboard = parse_dashboard_json(loop_result.content)
            return AgentResult(
                success=dashboard is not None,
                content=loop_result.content,
                dashboard=dashboard,
                tool_calls_log=loop_result.tool_calls_log,
                total_steps=loop_result.total_steps,
                total_tokens=loop_result.total_tokens,
                provider=loop_result.provider,
                model=model_str,
                error=None if dashboard else "Failed to parse dashboard JSON from agent response",
                messages=loop_result.messages,
            )

        return AgentResult(
            success=loop_result.success,
            content=loop_result.content,
            dashboard=None,
            tool_calls_log=loop_result.tool_calls_log,
            total_steps=loop_result.total_steps,
            total_tokens=loop_result.total_tokens,
            provider=loop_result.provider,
            model=model_str,
            error=loop_result.error,
            messages=loop_result.messages,
        )

    def _build_user_message(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Build the initial user message."""
        parts = [task]
        if context:
            report_language = normalize_report_language(context.get("report_language", "vi"))
            if context.get("stock_code"):
                parts.append(f"\n股票代码: {context['stock_code']}")
            if context.get("report_type"):
                parts.append(f"报告类型: {context['report_type']}")
            if report_language == "en":
                parts.append("Ngôn ngữ đầu ra: English (giữ nguyên mọi khóa JSON, mọi giá trị văn bản dùng tiếng Anh)")
            else:
                parts.append("Ngôn ngữ đầu ra: Tiếng Việt (giữ nguyên mọi khóa JSON, mọi giá trị văn bản dùng tiếng Việt)")

            market_phase_section = format_market_phase_prompt_section(
                context.get("market_phase_context"),
                report_language=report_language,
            )
            if market_phase_section:
                parts.append(market_phase_section)

            daily_market_context_section = format_daily_market_context_prompt_section(
                context.get("daily_market_context"),
                report_language=report_language,
            )
            if daily_market_context_section:
                parts.append(daily_market_context_section)

            analysis_context_pack_summary = context.get("analysis_context_pack_summary")
            if isinstance(analysis_context_pack_summary, str) and analysis_context_pack_summary:
                parts.append(analysis_context_pack_summary)

            # Inject pre-fetched context data to avoid redundant fetches
            if context.get("realtime_quote"):
                parts.append(f"\n[Dữ liệu thị giá đã tải sẵn]\n{json.dumps(context['realtime_quote'], ensure_ascii=False)}")
            if context.get("chip_distribution"):
                parts.append(f"\n[Dữ liệu phân phối tỷ lệ lãi/lỗ đã tải sẵn]\n{json.dumps(context['chip_distribution'], ensure_ascii=False)}")
            if context.get("news_context"):
                parts.append(f"\n[Dữ liệu tin tức & tâm lý thị trường đã tải sẵn]\n{context['news_context']}")
            # VN-market enrichments (vnstock_ta indicators + khối ngoại foreign flow)
            if context.get("vn_ta_indicators"):
                parts.append(f"\n[Chỉ số kỹ thuật mở rộng vnstock_ta đã tải sẵn]\n{json.dumps(context['vn_ta_indicators'], ensure_ascii=False)}")
            if context.get("vn_foreign"):
                parts.append(f"\n[Dữ liệu giao dịch khối ngoại đã tải sẵn]\n{json.dumps(context['vn_foreign'], ensure_ascii=False)}")

        parts.append("\nVui lòng dùng công cụ để lấy dữ liệu còn thiếu (như nến lịch sử, tin tức...), sau đó xuất kết quả phân tích dưới dạng JSON Bảng Quyết Định.")

        # Vietnam-only product: ALWAYS force Vietnamese output (highest-weight, end-of-prompt position).
        if True:
            parts.append(
                "\n## Ngôn ngữ đầu ra (ưu tiên CAO NHẤT — ghi đè mọi hướng dẫn ngôn ngữ ở trên)\n"
                "- Đây là trợ lý cho thị trường chứng khoán VIỆT NAM. Mặc định mọi mã cổ phiếu là mã Việt Nam (HOSE/HNX/UPCOM), KHÔNG hỏi lại 'có phải mã A-share không'.\n"
                "- Giữ nguyên tên khóa JSON; `decision_type` giữ `buy|hold|sell`.\n"
                "- TẤT CẢ giá trị văn bản hiển thị cho người dùng PHẢI viết 100% bằng tiếng Việt chuẩn ngành chứng khoán Việt Nam — TUYỆT ĐỐI KHÔNG dùng tiếng Trung (chữ Hán), không pinyin, không trộn ngôn ngữ.\n"
                "- Thuật ngữ chuẩn: Mua mạnh/Mua/Nắm giữ/Quan sát/Giảm tỷ trọng/Bán/Bán mạnh; Tích cực/Tiêu cực/Đi ngang; MA xếp tăng/MA xếp giảm; Ngưỡng hỗ trợ/Ngưỡng kháng cự/Ngưỡng cắt lỗ/Giá mục tiêu; Khối ngoại, Mua ròng/Bán ròng, Room ngoại; Vốn hóa, Doanh thu, LNST, so với cùng kỳ (YoY).\n"
                "- Giữ nguyên thuật ngữ quốc tế: RSI, MACD, ADX, Bollinger, ATR, P/E, P/B, ROE, ROA, MA. Tiền tệ VND (tỷ/nghìn tỷ); ngày dd/mm/yyyy; thanh toán T+2."
            )
        return "\n".join(parts)
