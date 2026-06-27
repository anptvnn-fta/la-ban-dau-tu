# -*- coding: utf-8 -*-
"""
===================================
Module phân tích tổng kết thị trường
===================================

Trách nhiệm:
1. Lấy dữ liệu chỉ số thị trường (Thượng Hải, Thâm Quyến, ChiNext / VN-Index, v.v.)
2. Tìm kiếm tin tức thị trường để tổng hợp thông tin tổng kết
3. Dùng LLM tạo báo cáo tổng kết thị trường hàng ngày
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from inspect import getattr_static
from typing import Optional, Dict, Any, List

import pandas as pd

from src.config import get_config
from src.report_language import normalize_report_language
from src.search_service import SearchService
from src.core.market_profile import get_profile, MarketProfile
from src.core.market_strategy import get_market_strategy_blueprint
from src.llm.backend_registry import (
    resolve_generation_backend_id,
    resolve_generation_fallback_backend_id,
)
from src.llm.generation_backend import GenerationError
from src.schemas.market_light import MarketLightSnapshot
from src.services.run_diagnostics import record_llm_run, record_llm_run_started
from src.services.intelligence_service import IntelligenceService
from data_provider.base import DataFetcherManager

logger = logging.getLogger(__name__)


_ENGLISH_SECTION_PATTERNS = {
    "market_summary": r"###\s*(?:1\.\s*)?Market Summary",
    "index_commentary": r"###\s*(?:2\.\s*)?(?:Index Commentary|Major Indices)",
    "sector_highlights": r"###\s*(?:4\.\s*)?(?:Sector Highlights|Sector/Theme Highlights)",
}

_CHINESE_SECTION_PATTERNS = {
    "market_summary": r"###\s*一、(?:盘面总览|市场总结)",
    "index_commentary": r"###\s*二、(?:指数结构|指数点评|主要指数)",
    "sector_highlights": r"###\s*三、(?:板块主线|热点解读|板块表现)",
    "funds_sentiment": r"###\s*四、(?:资金与情绪|资金动向)",
    "news_catalysts": r"###\s*五、(?:消息催化|后市展望)",
}


@dataclass
class MarketIndex:
    """Dữ liệu chỉ số thị trường"""
    code: str                    # Mã chỉ số
    name: str                    # Tên chỉ số
    current: float = 0.0         # Điểm hiện tại
    change: float = 0.0          # Thay đổi điểm
    change_pct: float = 0.0      # % Thay đổi
    open: float = 0.0            # Điểm mở cửa
    high: float = 0.0            # Điểm cao nhất
    low: float = 0.0             # Điểm thấp nhất
    prev_close: float = 0.0      # Điểm đóng cửa hôm trước
    volume: float = 0.0          # Khối lượng giao dịch (lô)
    amount: float = 0.0          # Giá trị giao dịch (đơn vị tiền tệ)
    amplitude: float = 0.0       # Biên độ (%)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'current': self.current,
            'change': self.change,
            'change_pct': self.change_pct,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'amount': self.amount,
            'amplitude': self.amplitude,
        }


@dataclass
class MarketOverview:
    """Dữ liệu tổng quan thị trường"""
    date: str                           # Ngày
    indices: List[MarketIndex] = field(default_factory=list)  # Các chỉ số chính
    up_count: int = 0                   # Số mã tăng
    down_count: int = 0                 # Số mã giảm
    flat_count: int = 0                 # Số mã đi ngang
    limit_up_count: int = 0             # Số mã trần
    limit_down_count: int = 0           # Số mã sàn
    total_amount: float = 0.0           # Tổng giá trị giao dịch hai sàn (đơn vị 100 triệu CNY)
    # north_flow: float = 0.0           # Dòng tiền ròng từ phía Bắc (đơn vị 100 triệu CNY) - đã bỏ, API không còn khả dụng

    # Bảng xếp hạng nhóm ngành
    top_sectors: List[Dict] = field(default_factory=list)     # Top 5 nhóm ngành tăng mạnh nhất
    bottom_sectors: List[Dict] = field(default_factory=list)  # Top 5 nhóm ngành giảm mạnh nhất


@dataclass
class MarketLightReviewResult:
    """Internal market-review parts built from one overview fetch."""

    overview: MarketOverview
    report: str
    market_light_snapshot: Dict[str, Any]
    structured_payload: Dict[str, Any] = field(default_factory=dict)


class MarketAnalyzer:
    """
    Bộ phân tích tổng kết thị trường

    Chức năng:
    1. Lấy dữ liệu thị trường chỉ số theo thời gian thực
    2. Lấy thống kê tăng/giảm thị trường
    3. Lấy bảng xếp hạng nhóm ngành
    4. Tìm kiếm tin tức thị trường
    5. Tạo báo cáo tổng kết thị trường
    """
    
    def __init__(
        self,
        search_service: Optional[SearchService] = None,
        analyzer=None,
        region: str = "cn",
        config: Optional[Any] = None,
    ):
        """
        Khởi tạo bộ phân tích thị trường

        Args:
            search_service: Instance dịch vụ tìm kiếm
            analyzer: Instance bộ phân tích AI (dùng để gọi LLM)
            region: Khu vực thị trường: cn=A-share, us=US stock
            config: Cấu hình dùng cho lần tổng kết này; nếu không truyền thì đọc cấu hình toàn cục
        """
        self.config = config or get_config()
        self.search_service = search_service
        self.analyzer = analyzer
        self.data_manager = DataFetcherManager()
        self.region = region if region in ("cn", "us", "hk", "vn") else "cn"
        self.profile: MarketProfile = get_profile(self.region)
        self.strategy = get_market_strategy_blueprint(self.region)

    def _log_context(self) -> str:
        return f"component=market_review region={self.region}"

    def _get_review_language(self) -> str:
        # Vietnam reviews always render in Vietnamese, independent of the global
        # report_language (which only models zh/en). Other regions follow config.
        if self.region == "vn":
            return "vi"
        return normalize_report_language(
            getattr(getattr(self, "config", None), "report_language", "zh")
        )

    def _get_template_review_language(self) -> str:
        if self.region == "vn":
            return "vi"
        return normalize_report_language(
            getattr(getattr(self, "config", None), "report_language", "zh")
        )

    def _get_market_scope_name(self, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if self.region == "vn":
            return "thị trường chứng khoán Việt Nam"
        if self.region == "us":
            return "US market" if review_language == "en" else "thị trường Mỹ"
        if self.region == "hk":
            return "Hong Kong market" if review_language == "en" else "thị trường Hồng Kông"
        if review_language == "en":
            return "A-share market"
        return "thị trường A-share"

    def _get_turnover_unit_label(self) -> str:
        """Return the turnover unit label for the current market/language."""
        if self.region == "vn":
            return "tỷ VND"
        if self.region == "us":
            return "USD bn" if self._get_review_language() == "en" else "tỷ USD"
        if self.region == "hk":
            return "HKD bn" if self._get_review_language() == "en" else "tỷ HKD"
        return "CNY 100m" if self._get_review_language() == "en" else "trăm triệu CNY"

    def _format_turnover_value(self, amount_raw: float) -> str:
        """Format raw turnover according to market-specific units."""
        if amount_raw == 0.0:
            return "N/A"
        if self.region in ("us", "hk"):
            return f"{amount_raw / 1e9:.2f}"
        if amount_raw > 1e6:
            return f"{amount_raw / 1e8:.0f}"
        return f"{amount_raw:.0f}"

    def _get_index_change_arrow(self, change_pct: float) -> str:
        if change_pct == 0:
            return "⚪"
        color_scheme = getattr(getattr(self, "config", None), "market_review_color_scheme", "green_up")
        if color_scheme == "red_up":
            return "🔴" if change_pct > 0 else "🟢"
        return "🟢" if change_pct > 0 else "🔴"

    def _get_review_title(self, date: str) -> str:
        if self.region == "vn":
            return f"## {date} Tổng kết thị trường Việt Nam"
        if self._get_review_language() == "en":
            market_names = {"us": "US Market Recap", "hk": "HK Market Recap"}
            market_name = market_names.get(self.region, "A-share Market Recap")
            return f"## {date} {market_name}"
        return f"## {date} Tổng kết thị trường"

    def _get_index_hint(self) -> str:
        if self.region == "vn":
            return "Phân tích diễn biến VN-Index, VN30, HNX-Index, UPCOM-Index và các chỉ số chính khác."
        if self._get_review_language() == "en":
            if self.region == "us":
                return "Analyze the key moves in the S&P 500, Nasdaq, Dow, and other major indices."
            if self.region == "hk":
                return "Analyze the key moves in the HSI, Hang Seng Tech, HSCEI, and other major indices."
            return "Analyze the price action in the SSE, SZSE, ChiNext, and other major indices."
        return self.profile.prompt_index_hint

    def _get_strategy_prompt_block(self) -> str:
        if self.region == "hk" and self._get_review_language() == "en":
            return """## Strategy Blueprint: Hong Kong Market Regime Strategy
Focus on HSI trend, southbound flow dynamics, and sector rotation to define next-session risk posture.

### Strategy Principles
- Read market regime from HSI, HSTECH, and HSCEI alignment first.
- Track southbound capital flow as a key sentiment driver.
- Translate recap into actionable risk-on/risk-off stance with clear invalidation points.

### Analysis Dimensions
- Trend Regime: Classify the market as momentum, range, or risk-off.
  - Are HSI/HSTECH/HSCEI directionally aligned
  - Did volume confirm the move
  - Are key index levels reclaimed or lost
- Capital Flows: Map southbound flow and macro narrative into equity risk appetite.
  - Southbound net flow direction and magnitude
  - USD/HKD and China policy implications
  - Breadth and leadership concentration
- Sector Themes: Identify persistent leaders and vulnerable laggards.
  - Tech/internet platform trend persistence
  - Financials/property sensitivity to policy shifts
  - Defensive vs growth factor rotation

### Action Framework
- Risk-on: broad index breakout with expanding southbound participation.
- Neutral: mixed index signals; focus on selective relative strength.
- Risk-off: failed breakouts and rising volatility; prioritize capital preservation."""
        if self.region == "us" and self._get_review_language() == "zh":
            return """## Chiến lược tổng kết thị trường Mỹ ba giai đoạn
Tập trung vào xu hướng chỉ số, câu chuyện vĩ mô và luân chuyển nhóm ngành để đưa ra khung kiểm soát rủi ro và tỷ trọng cho phiên tiếp theo.

### Nguyên tắc chiến lược
- Đầu tiên kiểm tra S&P 500, Nasdaq, Dow Jones có cùng chiều không, xác nhận dòng chính có nhất quán.
- Kết hợp các chỉ báo vĩ mô và thanh khoản, nhận diện khẩu vị rủi ro đang phục hồi hay suy yếu.
- Ánh xạ kết quả tổng kết sang khuyến nghị "tấn công/cân bằng/phòng thủ" với điều kiện kích hoạt vô hiệu rõ ràng.

### Chiều phân tích
- Cấu trúc xu hướng: xác định thị trường đang bứt phá, dao động hay chuyển phòng thủ; kiểm tra phân kỳ tại các mốc hỗ trợ chính.
- Dòng tiền & tâm lý: phân biệt tác động của chính sách vĩ mô, tiền tệ và biến động lên rủi ro vốn cổ phần.
- Chủ đề đầu tư: nhận diện chủ đề có độ bền nhất và luân chuyển ngành có hình thành dòng chính giao dịch được hay không.

### Khung hành động
- Tấn công: các ngành chủ đạo tăng đồng thuận và thanh khoản/mốc rủi ro cải thiện cùng chiều.
- Cân bằng: chỉ số phân kỳ hoặc thanh khoản chưa mở rộng rõ, thực hiện thận trọng với tỷ trọng thấp.
- Phòng thủ: phá vỡ mốc hỗ trợ và biến động leo thang — ưu tiên cắt giảm tỷ trọng và giữ khả năng giao dịch nhịp hồi."""
        if not (self.region == "cn" and self._get_review_language() == "en"):
            return self.strategy.to_prompt_block()
        return """## Strategy Blueprint: A-share Three-Phase Recap Strategy
Focus on index trend, liquidity, and sector rotation to shape the next-session trading plan.

### Strategy Principles
- Read index direction first, then confirm liquidity structure, and finally test sector persistence.
- Every conclusion must map to position sizing, trading pace, and risk-control actions.
- Base judgments on today's data and the latest 3-day news flow without inventing unverified information.

### Analysis Dimensions
- Trend Structure: Determine whether the market is in an uptrend, range, or defensive phase.
  - Are the SSE, SZSE, and ChiNext moving in the same direction
  - Is the market advancing on expanding volume or slipping on contracting volume
  - Have key support or resistance levels been reclaimed or broken
- Liquidity & Sentiment: Identify near-term risk appetite and market temperature.
  - Advance/decline breadth and limit-up/limit-down structure
  - Whether turnover is expanding or fading
  - Whether high-beta leaders are showing divergence
- Leading Themes: Distill tradable leadership and areas to avoid.
  - Whether leading sectors have clear event catalysts
  - Whether sector leaders are pulling the group higher
  - Whether weakness is broadening across lagging sectors

### Action Framework
- Offensive: indices rise in sync, turnover expands, and core themes strengthen.
- Balanced: index divergence or low-volume consolidation; keep sizing controlled and wait for confirmation.
- Defensive: indices weaken and laggards broaden; prioritize risk control and de-risking."""

    def _get_strategy_markdown_block(self, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if self.region == "hk" and review_language == "en":
            return """### 6. Strategy Framework
- **Trend Regime**: Classify the market as momentum, range, or risk-off based on HSI/HSTECH/HSCEI alignment.
- **Capital Flows**: Track southbound flow direction and macro narrative for risk appetite signals.
- **Sector Themes**: Focus on tech/internet platform persistence and financials/property policy sensitivity.
"""
        if self.region == "us" and review_language == "zh":
            return """### 6. Khung chiến lược
- **Cấu trúc xu hướng**: Xác định thị trường đang tấn công, dao động hay phòng thủ.
- **Dòng tiền & tâm lý**: Đánh giá khẩu vị rủi ro qua biến động, độ rộng và luân chuyển chủ đề.
- **Chủ đề dẫn dắt**: Nhận diện dòng ngành có thể tiếp diễn, khuếch đại và tuyến phòng thủ.
"""
        if not (self.region == "cn" and review_language == "en"):
            return self.strategy.to_markdown_block()
        return """### 6. Strategy Framework
- **Trend Structure**: Determine whether the market is in an uptrend, range, or defensive phase.
- **Liquidity & Sentiment**: Track breadth, turnover expansion, and whether leaders are diverging.
- **Leading Themes**: Focus on sectors with catalysts and sustained leadership while avoiding broadening weakness.
"""

    def _get_market_mood_text(self, mood_key: str, review_language: str | None = None) -> str:
        review_language = review_language or self._get_review_language()
        if review_language == "vi":
            mapping = {
                "strong_up": "tăng mạnh",
                "mild_up": "tăng nhẹ",
                "mild_down": "giảm nhẹ",
                "strong_down": "giảm rõ rệt",
                "range": "đi ngang tích luỹ",
            }
        elif review_language == "en":
            mapping = {
                "strong_up": "strong gains",
                "mild_up": "moderate gains",
                "mild_down": "mild losses",
                "strong_down": "clear weakness",
                "range": "range-bound trading",
            }
        else:
            mapping = {
                "strong_up": "tăng mạnh",
                "mild_up": "tăng nhẹ",
                "mild_down": "giảm nhẹ",
                "strong_down": "giảm rõ rệt",
                "range": "đi ngang tích luỹ",
            }
        return mapping[mood_key]

    def get_market_overview(self) -> MarketOverview:
        """
        Lấy dữ liệu tổng quan thị trường

        Returns:
            MarketOverview: Đối tượng dữ liệu tổng quan thị trường
        """
        today = datetime.now().strftime('%Y-%m-%d')
        overview = MarketOverview(date=today)

        # 1. Lấy dữ liệu chỉ số chính (chuyển đổi giữa A-share/US stock theo region)
        overview.indices = self._get_main_indices()

        # 2. Lấy thống kê tăng/giảm (A-share có, US stock không có dữ liệu tương đương)
        if self.profile.has_market_stats:
            self._get_market_statistics(overview)

        # 3. Lấy bảng xếp hạng nhóm ngành (A-share có, US stock tạm thời chưa có)
        if self.profile.has_sector_rankings:
            self._get_sector_rankings(overview)
        
        # 4. Lấy dòng tiền phía Bắc (tùy chọn)
        # self._get_north_flow(overview)
        
        return overview

    
    def _get_main_indices(self) -> List[MarketIndex]:
        """Lấy dữ liệu thị trường chỉ số chính theo thời gian thực"""
        indices = []

        try:
            logger.info("[ThịTrường] %s action=get_main_indices status=start", self._log_context())

            # Dùng DataFetcherManager lấy dữ liệu chỉ số (chuyển đổi theo region)
            data_list = self.data_manager.get_main_indices(region=self.region)

            if data_list:
                for item in data_list:
                    # Be tolerant of fetcher dicts that omit fields (e.g. VnstockFetcher
                    # provides no 'amplitude' and may report None turnover/change).
                    high = item.get('high') or 0.0
                    low = item.get('low') or 0.0
                    prev_close = item.get('prev_close') or 0.0
                    amplitude = item.get('amplitude')
                    if amplitude is None:
                        amplitude = ((high - low) / prev_close * 100) if prev_close else 0.0
                    index = MarketIndex(
                        code=item['code'],
                        name=item['name'],
                        current=item.get('current') or 0.0,
                        change=item.get('change') or 0.0,
                        change_pct=item.get('change_pct') or 0.0,
                        open=item.get('open') or 0.0,
                        high=high,
                        low=low,
                        prev_close=prev_close,
                        volume=item.get('volume') or 0.0,
                        amount=item.get('amount') or 0.0,
                        amplitude=amplitude,
                    )
                    indices.append(index)

            if not indices:
                logger.warning("[ThịTrường] %s action=get_main_indices status=empty", self._log_context())
            else:
                logger.info(
                    "[ThịTrường] %s action=get_main_indices status=success count=%d",
                    self._log_context(),
                    len(indices),
                )

        except Exception as e:
            logger.error("[ThịTrường] %s action=get_main_indices status=failed error=%s", self._log_context(), e)

        return indices

    def _get_market_statistics(self, overview: MarketOverview):
        """Lấy thống kê tăng/giảm thị trường"""
        try:
            logger.info("[ThịTrường] %s action=get_market_stats status=start", self._log_context())

            stats = self.data_manager.get_market_stats(purpose=f"market_review:{self.region}")

            if stats:
                overview.up_count = stats.get('up_count', 0)
                overview.down_count = stats.get('down_count', 0)
                overview.flat_count = stats.get('flat_count', 0)
                overview.limit_up_count = stats.get('limit_up_count', 0)
                overview.limit_down_count = stats.get('limit_down_count', 0)
                overview.total_amount = stats.get('total_amount', 0.0)

                logger.info(
                    "[ThịTrường] %s action=get_market_stats status=success up=%s down=%s flat=%s "
                    "limit_up=%s limit_down=%s amount=%.0f ty",
                    self._log_context(),
                    overview.up_count,
                    overview.down_count,
                    overview.flat_count,
                    overview.limit_up_count,
                    overview.limit_down_count,
                    overview.total_amount,
                )
            else:
                logger.warning("[ThịTrường] %s action=get_market_stats status=empty", self._log_context())

        except Exception as e:
            logger.error("[ThịTrường] %s action=get_market_stats status=failed error=%s", self._log_context(), e)

    def _get_sector_rankings(self, overview: MarketOverview):
        """Lấy bảng xếp hạng tăng/giảm nhóm ngành"""
        try:
            logger.info("[ThịTrường] %s action=get_sector_rankings status=start", self._log_context())

            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(5)

            if top_sectors or bottom_sectors:
                overview.top_sectors = top_sectors
                overview.bottom_sectors = bottom_sectors

                logger.info(
                    "[ThịTrường] %s action=get_sector_rankings status=success top=%s bottom=%s",
                    self._log_context(),
                    [s['name'] for s in overview.top_sectors],
                    [s['name'] for s in overview.bottom_sectors],
                )
            else:
                logger.warning("[ThịTrường] %s action=get_sector_rankings status=empty", self._log_context())

        except Exception as e:
            logger.error("[ThịTrường] %s action=get_sector_rankings status=failed error=%s", self._log_context(), e)
    
    # def _get_north_flow(self, overview: MarketOverview):
    #     """Lấy dòng tiền ròng vào từ phía Bắc"""
    #     try:
    #         logger.info("[大盘] Đang lấy dòng tiền phía Bắc...")
    #
    #         # Lấy dữ liệu dòng tiền phía Bắc
    #         df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
    #
    #         if df is not None and not df.empty:
    #             # Lấy bản ghi mới nhất
    #             latest = df.iloc[-1]
    #             if '当日净流入' in df.columns:
    #                 overview.north_flow = float(latest['当日净流入']) / 1e8  # Chuyển sang đơn vị 100 triệu
    #             elif '净流入' in df.columns:
    #                 overview.north_flow = float(latest['净流入']) / 1e8
    #
    #             logger.info(f"[大盘] Dòng tiền ròng vào từ phía Bắc: {overview.north_flow:.2f} trăm triệu")
    #
    #     except Exception as e:
    #         logger.warning(f"[大盘] Lấy dòng tiền phía Bắc thất bại: {e}")
    
    def search_market_news(self) -> List[Dict]:
        """
        Tìm kiếm tin tức thị trường

        Returns:
            Danh sách tin tức
        """
        if not self.search_service:
            logger.warning(
                "[ThịTrường] %s action=search_market_news status=skipped reason=no_search_service",
                self._log_context(),
            )
            return []
        
        all_news = []

        # Dùng từ khóa tìm kiếm tin tức khác nhau theo region
        search_queries = self.profile.news_queries
        review_language = self._get_review_language()
        market_names = {
            "cn": "thị trường A-share" if review_language == "zh" else "A-share market",
            "us": "thị trường Mỹ" if review_language == "zh" else "US market",
            "hk": "thị trường Hồng Kông" if review_language == "zh" else "HK market",
            "vn": "thị trường chứng khoán Việt Nam",
        }
        
        try:
            logger.info("[ThiTruong] %s action=search_market_news status=start", self._log_context())
            
            # Thiết lập tên ngữ cảnh tìm kiếm theo region, tránh tìm kiếm US stock bị hiểu là ngữ cảnh A-share
            market_name = market_names.get(self.region, "thị trường A-share")
            for query in search_queries:
                response = self.search_service.search_stock_news(
                    stock_code="market",
                    stock_name=market_name,
                    max_results=3,
                    focus_keywords=query.split()
                )
                if response and response.results:
                    all_news.extend(response.results)
                    logger.info(
                        "[ThịTrường] %s action=search_market_news status=query_success count=%d",
                        self._log_context(),
                        len(response.results),
                    )
            
            logger.info(
                "[ThịTrường] %s action=search_market_news status=success count=%d",
                self._log_context(),
                len(all_news),
            )
            
        except Exception as e:
            logger.error("[ThịTrường] %s action=search_market_news status=failed error=%s", self._log_context(), e)
        
        return all_news
    
    def generate_market_review(self, overview: MarketOverview, news: List) -> str:
        """
        Dùng LLM tạo báo cáo tổng kết thị trường

        Args:
            overview: Dữ liệu tổng quan thị trường
            news: Danh sách tin tức thị trường (danh sách đối tượng SearchResult)

        Returns:
            Văn bản báo cáo tổng kết thị trường
        """
        backend_error = self._get_analyzer_generation_backend_config_error()
        if backend_error is not None:
            logger.error(
                "[ThịTrường] %s action=generate_review status=failed error_type=%s error=%s",
                self._log_context(),
                type(backend_error).__name__,
                backend_error,
            )
            record_llm_run(
                success=False,
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
                error_type=type(backend_error).__name__,
                error_message=backend_error,
            )
            raise backend_error

        if not self.analyzer or not self.analyzer.is_available():
            logger.warning(
                "[ThịTrường] %s action=generate_review status=fallback_template reason=no_analyzer",
                self._log_context(),
            )
            return self._generate_template_review(overview, news)

        # Xây dựng Prompt
        prompt = self._build_review_prompt(overview, news)

        logger.info("[ThịTrường] %s action=generate_review status=start", self._log_context())
        # Use the public generate_text() entry point - never access private analyzer attributes.
        llm_started_at = time.perf_counter()
        try:
            record_llm_run_started(
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
            )
            review = self.analyzer.generate_text(prompt, max_tokens=8192, temperature=0.7)
        except Exception as exc:
            record_llm_run(
                success=False,
                provider="litellm",
                model=getattr(self.config, "litellm_model", None),
                call_type="market_review",
                duration_ms=int((time.perf_counter() - llm_started_at) * 1000),
                error_type=type(exc).__name__,
                error_message=exc,
            )
            raise

        record_llm_run(
            success=bool(review),
            provider="litellm",
            model=getattr(self.config, "litellm_model", None),
            call_type="market_review",
            duration_ms=int((time.perf_counter() - llm_started_at) * 1000),
            error_type=None if review else "EmptyResponse",
            error_message=None if review else "empty market review response",
        )

        if review:
            logger.info(
                "[ThịTrường] %s action=generate_review status=success length=%d",
                self._log_context(),
                len(review),
            )
            # Inject structured data tables into LLM prose sections
            return self._inject_data_into_review(review, overview, news)

        logger.warning(
            "[ThịTrường] %s action=generate_review status=fallback_template reason=empty_llm_response",
            self._log_context(),
        )
        return self._generate_template_review(overview, news)

    def _get_analyzer_generation_backend_config_error(self) -> Optional[GenerationError]:
        """Return analyzer backend config errors without relying on dynamic mock attributes."""
        if self.analyzer is None:
            try:
                resolve_generation_backend_id(self.config)
                resolve_generation_fallback_backend_id(self.config)
            except GenerationError as exc:
                return exc
            return None
        missing = object()
        if getattr_static(self.analyzer, "get_generation_backend_config_error", missing) is missing:
            return None
        method = getattr(self.analyzer, "get_generation_backend_config_error", None)
        if not callable(method):
            return None
        error = method()
        return error if isinstance(error, GenerationError) else None

    def build_market_review_payload(
        self,
        overview: MarketOverview,
        news: List,
        report: str,
        market_light_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the structured market-review contract consumed by API, Web, and notifications."""
        language = self._get_review_language()
        sections = self._split_report_sections(report, self._get_review_language())
        title = self._extract_report_title(report) or self._get_review_title(overview.date).lstrip("# ").strip()
        light = market_light_snapshot or self.build_market_light_snapshot(overview)
        breadth_dimensions = None
        if isinstance(light, dict):
            dimensions = light.get("dimensions")
            if isinstance(dimensions, dict):
                breadth_dimensions = dimensions.get("breadth")

        breadth_supported = bool(self.profile.has_market_stats)
        if breadth_supported and isinstance(breadth_dimensions, dict) and "available" in breadth_dimensions:
            breadth_supported = bool(breadth_dimensions.get("available"))

        has_breadth_data = False
        if breadth_supported:
            if isinstance(breadth_dimensions, dict) and "available" in breadth_dimensions:
                has_breadth_data = bool(breadth_dimensions.get("available"))
            else:
                breadth_available = overview.up_count + overview.down_count + overview.flat_count > 0
                limit_available = overview.limit_up_count + overview.limit_down_count > 0
                has_breadth_data = bool(breadth_available or limit_available)

        payload = {
            "version": 1,
            "kind": "market_review",
            "region": self.region,
            "language": language,
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "date": overview.date,
            "market_scope": self._get_market_scope_name(language),
            "market_light": light,
            "indices": [idx.to_dict() for idx in overview.indices],
            "sectors": {
                "top": list(overview.top_sectors or []),
                "bottom": list(overview.bottom_sectors or []),
            },
            "news": [self._normalize_news_item(item) for item in (news or [])[:8]],
            "sections": sections,
            "markdown_report": report,
        }

        if has_breadth_data:
            payload["breadth"] = {
                "up_count": overview.up_count,
                "down_count": overview.down_count,
                "flat_count": overview.flat_count,
                "limit_up_count": overview.limit_up_count,
                "limit_down_count": overview.limit_down_count,
                "total_amount": overview.total_amount,
                "turnover_unit": self._get_turnover_unit_label(),
            }

        return payload

    @staticmethod
    def _extract_report_title(report: str) -> str:
        for line in (report or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

    @classmethod
    def _split_report_sections(cls, report: str, review_language: str = "zh") -> List[Dict[str, str]]:
        text = (report or "").strip()
        if not text:
            return []
        matches = list(re.finditer(r"^(#{2,3})\s+(.+?)\s*$", text, flags=re.MULTILINE))
        if not matches:
            return [{"key": "full_review", "title": "Review", "markdown": text}]

        sections: List[Dict[str, str]] = []
        first_match = matches[0]
        starts_with_report_title = first_match.start() == 0 and first_match.group(1) == "##"
        content_start_index = 1 if starts_with_report_title else 0
        intro_start = first_match.end() if starts_with_report_title else 0
        intro_end = (
            matches[1].start()
            if starts_with_report_title and len(matches) > 1
            else (len(text) if starts_with_report_title else matches[0].start())
        )
        intro = text[intro_start:intro_end].strip()
        if intro:
            intro_title = "Tổng quan" if review_language == "vi" else "Overview"
            sections.append({"key": "overview", "title": intro_title, "markdown": intro})

        for index, match in enumerate(matches[content_start_index:], start=content_start_index):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            title = match.group(2).strip()
            markdown = text[start:end].strip()
            if not markdown:
                continue
            key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", title).strip("_").lower()
            sections.append({
                "key": key or f"section_{index + 1}",
                "title": title,
                "markdown": markdown,
            })
        return sections

    @classmethod
    def _normalize_news_item(cls, item: Any) -> Dict[str, str]:
        return {
            "title": cls._compact_news_text(cls._get_news_field(item, "title"), limit=120),
            "snippet": cls._compact_news_text(cls._get_news_field(item, "snippet"), limit=260),
            "source": cls._compact_news_text(cls._get_news_field(item, "source"), limit=80),
            "published_date": cls._compact_news_text(cls._get_news_field(item, "published_date"), limit=40),
            "url": cls._compact_news_text(cls._get_news_field(item, "url"), limit=240),
        }
    
    def _inject_data_into_review(
        self,
        review: str,
        overview: MarketOverview,
        news: Optional[List] = None,
    ) -> str:
        """Inject structured data tables into the corresponding LLM prose sections."""
        # Build data blocks
        stats_block = self._build_stats_block(overview)
        indices_block = self._build_indices_block(overview)
        sector_block = self._build_sector_block(overview)
        patterns = (
            _ENGLISH_SECTION_PATTERNS
            if self._get_review_language() == "en"
            else _CHINESE_SECTION_PATTERNS
        )

        if stats_block:
            review = self._insert_after_section(
                review,
                patterns["market_summary"],
                stats_block,
            )

        if indices_block:
            review = self._insert_after_section(
                review,
                patterns["index_commentary"],
                indices_block,
            )

        if sector_block:
            review = self._insert_after_section(
                review,
                patterns["sector_highlights"],
                sector_block,
            )

        return review

    @staticmethod
    def _insert_after_section(text: str, heading_pattern: str, block: str) -> str:
        """Insert a data block at the end of a markdown section (before the next ### heading)."""
        import re
        # Find the heading
        match = re.search(heading_pattern, text)
        if not match:
            return text
        start = match.end()
        # Find the next ### heading after this one
        next_heading = re.search(r'\n###\s', text[start:])
        if next_heading:
            insert_pos = start + next_heading.start()
        else:
            # No next heading — append at end
            insert_pos = len(text)
        # Insert the block before the next heading, with spacing
        return text[:insert_pos].rstrip() + '\n\n' + block + '\n\n' + text[insert_pos:].lstrip('\n')

    def _build_stats_block(self, overview: MarketOverview) -> str:
        """Build market statistics block."""
        has_stats = overview.up_count or overview.down_count or overview.total_amount
        if not has_stats:
            return ""
        if self._get_review_language() == "en":
            light = self.build_market_light_snapshot(overview)
            return "\n".join(
                [
                    f"- **Market Signal**: {light['score']}/100 "
                    f"({light['temperature_label']}, {light['label']})",
                    f"- **Drivers**: {'; '.join(light['reasons'])}",
                    f"- **Guidance**: {light['guidance']}",
                    "",
                    f"- **Breadth**: Advancers {overview.up_count} / Decliners {overview.down_count} / "
                    f"Flat {overview.flat_count}; "
                    f"Limit-up {overview.limit_up_count} / Limit-down {overview.limit_down_count}; "
                    f"Turnover {overview.total_amount:.0f} ({self._get_turnover_unit_label()})",
                ]
            )
        light = self.build_market_light_snapshot(overview)
        score, label = light["score"], light["temperature_label"]
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else 0.0
        limit_spread = overview.limit_up_count - overview.limit_down_count
        lines = [
            f"- **Tín hiệu thị trường**：{score}/100（{label}，{light['label']}）",
            f"- **Cơ sở tín hiệu**：{'；'.join(light['reasons'])}",
            f"- **Khuyến nghị vận hành**：{light['guidance']}",
            "",
            "| Chỉ tiêu | Giá trị | Nhận xét |",
            "|------|------|------|",
            f"| Tăng/Giảm/Đi ngang | {overview.up_count} / {overview.down_count} / {overview.flat_count} | Tỷ lệ tăng (không tính đi ngang) {up_ratio:.1%} |",
            f"| Trần/Sàn | {overview.limit_up_count} / {overview.limit_down_count} | Chênh lệch trần-sàn {limit_spread:+d} |",
            f"| Tổng GTGD | {overview.total_amount:.0f} ({self._get_turnover_unit_label()}) | {self._describe_turnover(overview.total_amount)} |",
        ]
        return "\n".join(lines)

    def build_market_light_snapshot(self, overview: MarketOverview) -> Dict[str, Any]:
        """Build a deterministic market-light snapshot from structured breadth data."""
        scores = self._build_market_light_scores(overview)
        score = int(scores["score"])
        temperature_label = str(scores["temperature_label"])
        if score >= 60:
            status = "green"
        elif score >= 40:
            status = "yellow"
        else:
            status = "red"

        if self._get_review_language() == "vi":
            label_map = {
                "green": "có thể tấn công",
                "yellow": "cần quan sát",
                "red": "thiên về phòng thủ",
            }
            guidance_map = {
                "green": "Khẩu vị rủi ro ở mức chấp nhận được; chú ý dòng dẫn dắt tiếp diễn và kỷ luật tỷ trọng.",
                "yellow": "Tín hiệu phân hoá; kiểm soát tỷ trọng và chờ xác nhận giá - thanh khoản.",
                "red": "Rủi ro ở mức cao; ưu tiên kiểm soát thua lỗ, tránh mua đuổi nhịp hồi yếu.",
            }
            reasons = self._build_market_light_reasons_vi(overview, score)
        elif self._get_review_language() == "en":
            label_map = {
                "green": "risk-on",
                "yellow": "balanced",
                "red": "risk-off",
            }
            guidance_map = {
                "green": "Risk appetite is acceptable; focus on leading themes and position discipline.",
                "yellow": "Signals are mixed; keep position sizing moderate and wait for confirmation.",
                "red": "Risk is elevated; prioritize drawdown control and avoid chasing weak rebounds.",
            }
            reasons = self._build_market_light_reasons_en(overview, score)
        else:
            label_map = {
                "green": "có thể tấn công",
                "yellow": "cần quan sát",
                "red": "thiên về phòng thủ",
            }
            guidance_map = {
                "green": "Khẩu vị rủi ro ở mức chấp nhận được; chú ý dòng dẫn dắt tiếp diễn và kỷ luật tỷ trọng.",
                "yellow": "Tín hiệu phân hoá; kiểm soát tỷ trọng và chờ xác nhận giá - thanh khoản.",
                "red": "Rủi ro ở mức cao; ưu tiên kiểm soát thua lỗ, tránh mua đuổi nhịp hồi yếu.",
            }
            reasons = self._build_market_light_reasons_zh(overview, score)

        snapshot = MarketLightSnapshot(
            region=self.region,
            trade_date=overview.date,
            status=status,
            label=label_map[status],
            score=score,
            temperature_label=temperature_label,
            reasons=reasons,
            guidance=guidance_map[status],
            dimensions=scores["dimensions"],
            data_quality=str(scores["data_quality"]),
        )
        return snapshot.model_dump()

    def _build_market_light_reasons_zh(self, overview: MarketOverview, score: int) -> List[str]:
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else None
        reasons: List[str] = []
        if up_ratio is not None:
            if up_ratio >= 0.6:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, hiệu ứng kiếm tiền lan toả")
            elif up_ratio <= 0.4:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, áp lực giảm chiếm ưu thế")
            else:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, thị trường phân hoá")
        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        if index_changes:
            avg_change = sum(index_changes) / len(index_changes)
            reasons.append(f"Các chỉ số chính tăng/giảm bình quân {avg_change:+.2f}%")
        if overview.limit_up_count or overview.limit_down_count:
            reasons.append(f"Chênh lệch trần/sàn {overview.limit_up_count - overview.limit_down_count:+d}")
        if not reasons and overview.total_amount:
            reasons.append(f"Giá trị giao dịch {overview.total_amount:.0f} ({self._get_turnover_unit_label()}), {self._describe_turnover(overview.total_amount)}")
        if not reasons:
            reasons.append("Dữ liệu độ rộng thị trường còn hạn chế; đánh giá theo dữ liệu sẵn có")
        return reasons[:4]

    def _build_market_light_reasons_vi(self, overview: MarketOverview, score: int) -> List[str]:
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else None
        reasons: List[str] = []
        if up_ratio is not None:
            if up_ratio >= 0.6:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, hiệu ứng kiếm tiền lan toả")
            elif up_ratio <= 0.4:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, áp lực giảm chiếm ưu thế")
            else:
                reasons.append(f"Tỷ lệ mã tăng {up_ratio:.0%}, thị trường phân hoá")
        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        if index_changes:
            avg_change = sum(index_changes) / len(index_changes)
            reasons.append(f"Các chỉ số chính tăng/giảm bình quân {avg_change:+.2f}%")
        if overview.limit_up_count or overview.limit_down_count:
            reasons.append(f"Chênh lệch trần/sàn {overview.limit_up_count - overview.limit_down_count:+d}")
        if not reasons and overview.total_amount:
            reasons.append(f"Giá trị giao dịch {overview.total_amount:.0f} ({self._get_turnover_unit_label()})")
        if not reasons:
            reasons.append("Dữ liệu độ rộng thị trường còn hạn chế; đánh giá theo dữ liệu sẵn có")
        return reasons[:4]

    def _build_market_light_reasons_en(self, overview: MarketOverview, score: int) -> List[str]:
        participation = overview.up_count + overview.down_count
        up_ratio = overview.up_count / participation if participation else None
        reasons: List[str] = []
        if up_ratio is not None:
            if up_ratio >= 0.6:
                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is expanding")
            elif up_ratio <= 0.4:
                reasons.append(f"advancers ratio {up_ratio:.0%}, downside pressure dominates")
            else:
                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is mixed")
        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        if index_changes:
            avg_change = sum(index_changes) / len(index_changes)
            reasons.append(f"average major-index change {avg_change:+.2f}%")
        if overview.limit_up_count or overview.limit_down_count:
            reasons.append(f"limit-up/down spread {overview.limit_up_count - overview.limit_down_count:+d}")
        if not reasons and overview.total_amount:
            reasons.append(f"turnover {overview.total_amount:.0f} ({self._get_turnover_unit_label()})")
        if not reasons:
            reasons.append("limited structured breadth data; using available market inputs")
        return reasons[:4]

    def _build_indices_block(self, overview: MarketOverview) -> str:
        """Xây dựng bảng dữ liệu chỉ số"""
        if not overview.indices:
            return ""
        if self._get_review_language() == "en":
            lines = [
                f"| Index | Last | Change % | Open | High | Low | Amplitude | Turnover ({self._get_turnover_unit_label()}) |",
                "|-------|------|----------|------|------|-----|-----------|-----------------|",
            ]
        else:
            lines = [
                f"| Chỉ số | Hiện tại | Thay đổi % | Mở cửa | Cao | Thấp | Biên độ | GTGD ({self._get_turnover_unit_label()}) |",
                "|------|------|--------|------|------|------|------|-----------|",
            ]
        for idx in overview.indices:
            arrow = self._get_index_change_arrow(idx.change_pct)
            amount_raw = idx.amount or 0.0
            amount_str = self._format_turnover_value(amount_raw)
            lines.append(
                f"| {idx.name} | {idx.current:.2f} | {arrow} {idx.change_pct:+.2f}% | "
                f"{self._format_optional_number(idx.open)} | {self._format_optional_number(idx.high)} | "
                f"{self._format_optional_number(idx.low)} | {self._format_optional_pct(idx.amplitude)} | {amount_str} |"
            )
        return "\n".join(lines)

    def _build_sector_block(self, overview: MarketOverview) -> str:
        """Build sector ranking block."""
        if not overview.top_sectors and not overview.bottom_sectors:
            return ""
        lines = []
        if overview.top_sectors:
            if self._get_review_language() == "en":
                lines.extend([
                    "#### Leading Sectors",
                    "| Rank | Sector | Change |",
                    "|------|--------|--------|",
                ])
            else:
                lines.extend([
                    "#### Nhóm ngành tăng mạnh nhất Top 5",
                    "| Hạng | Ngành | Thay đổi % |",
                    "|------|------|--------|",
                ])
            for rank, sector in enumerate(overview.top_sectors[:5], 1):
                lines.append(
                    f"| {rank} | {sector.get('name', '-')} | {self._format_signed_pct(sector.get('change_pct'))} |"
                )
        if overview.bottom_sectors:
            if lines:
                lines.append("")
            if self._get_review_language() == "en":
                lines.extend([
                    "#### Lagging Sectors",
                    "| Rank | Sector | Change |",
                    "|------|--------|--------|",
                ])
            else:
                lines.extend([
                    "#### Nhóm ngành giảm mạnh nhất Top 5",
                    "| Hạng | Ngành | Thay đổi % |",
                    "|------|------|--------|",
                ])
            for rank, sector in enumerate(overview.bottom_sectors[:5], 1):
                lines.append(
                    f"| {rank} | {sector.get('name', '-')} | {self._format_signed_pct(sector.get('change_pct'))} |"
                )
        return "\n".join(lines)

    def _build_news_block(self, news: List) -> str:
        """Build a compact source-aware news catalyst list for the rendered report."""
        if not news:
            return ""
        language = self._get_review_language()
        if language == "en":
            lines = [
                "#### News Catalysts",
            ]
        else:
            lines = [
                "#### Tin thị trường 3 ngày gần nhất",
            ]

        for idx, item in enumerate(news[:5], 1):
            lines.append(self._format_news_catalyst_line(idx, item, language=language))
        return "\n".join(lines)

    @staticmethod
    def _get_news_field(item: Any, field: str) -> str:
        if hasattr(item, field):
            value = getattr(item, field, "") or ""
        elif isinstance(item, dict):
            value = item.get(field, "") or ""
        else:
            value = ""
        return str(value).strip()

    @classmethod
    def _format_news_catalyst_line(cls, idx: int, item: Any, *, language: str = "zh") -> str:
        fallback_title = "Untitled catalyst" if language == "en" else "Tin tức chưa đặt tiêu đề"
        title = cls._compact_news_text(cls._get_news_field(item, "title"), limit=90) or fallback_title
        source = cls._compact_news_text(cls._get_news_field(item, "source"), limit=40)
        date_text = cls._compact_news_text(cls._get_news_field(item, "published_date"), limit=24)
        url = cls._compact_news_text(cls._get_news_field(item, "url"), limit=0)
        title_text = cls._escape_markdown_link_label(title)
        if url:
            title_text = f"[{title_text}]({url})"
        meta_parts = [part for part in (source, date_text) if part]
        if language == "en":
            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""
        else:
            meta = f"（{' / '.join(meta_parts)}）" if meta_parts else ""
        return f"- {idx}. {title_text}{meta}"

    @staticmethod
    def _compact_news_text(value: str, *, limit: int) -> str:
        text = " ".join(str(value or "").split())
        if limit <= 0 or len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _format_optional_number(value: float) -> str:
        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}"

    @staticmethod
    def _format_optional_pct(value: float) -> str:
        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}%"

    @staticmethod
    def _format_signed_pct(value: Any) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "N/A"
        return f"{numeric_value:+.2f}%"

    @staticmethod
    def _escape_markdown_link_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")

    @staticmethod
    def _describe_turnover(total_amount: float) -> str:
        if total_amount >= 15000:
            return "thanh khoản cao"
        if total_amount >= 9000:
            return "thanh khoản trung bình"
        if total_amount > 0:
            return "co cụm, thận trọng"
        return "chưa có dữ liệu"

    def _build_market_light_scores(self, overview: MarketOverview) -> Dict[str, Any]:
        """Build the canonical Market Light scores used by reports and alerts."""

        participants = overview.up_count + overview.down_count
        breadth_available = bool(self.profile.has_market_stats and participants > 0)
        breadth_score = 50
        if breadth_available:
            breadth_score = int(overview.up_count / participants * 100)

        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]
        index_available = bool(overview.indices and index_changes)
        index_score = 50
        if index_available:
            avg_change = sum(index_changes) / len(index_changes)
            index_score = int(max(0, min(100, 50 + avg_change * 12)))

        limit_total = overview.limit_up_count + overview.limit_down_count
        limit_available = bool(self.profile.has_market_stats and limit_total > 0)
        limit_score = 50
        if limit_available:
            limit_score = int(overview.limit_up_count / limit_total * 100)

        dimensions = {
            "breadth": {"score": breadth_score, "available": breadth_available},
            "index": {"score": index_score, "available": index_available},
            "limit": {"score": limit_score, "available": limit_available},
        }

        if not index_available:
            data_quality = "unavailable"
        elif all(dimension["available"] for dimension in dimensions.values()):
            data_quality = "ok"
        else:
            data_quality = "partial"

        score = int(round(breadth_score * 0.45 + index_score * 0.35 + limit_score * 0.20))
        if self._get_review_language() == "vi":
            if score >= 70:
                label = "mạnh"
            elif score >= 55:
                label = "ấm"
            elif score >= 40:
                label = "đi ngang"
            else:
                label = "yếu"
        elif self._get_review_language() == "en":
            if score >= 70:
                label = "risk-on"
            elif score >= 55:
                label = "constructive"
            elif score >= 40:
                label = "mixed"
            else:
                label = "defensive"
        else:
            if score >= 70:
                label = "mạnh"
            elif score >= 55:
                label = "ấm"
            elif score >= 40:
                label = "đi ngang"
            else:
                label = "yếu"
        return {
            "score": score,
            "temperature_label": label,
            "dimensions": dimensions,
            "data_quality": data_quality,
        }

    def _build_market_temperature(self, overview: MarketOverview) -> tuple[int, str]:
        scores = self._build_market_light_scores(overview)
        score = int(scores["score"])
        label = str(scores["temperature_label"])
        return score, label

    def _build_review_prompt(self, overview: MarketOverview, news: List) -> str:
        """Xây dựng Prompt tạo báo cáo tổng kết"""
        review_language = self._get_review_language()

        # Thông tin chỉ số (định dạng ngắn gọn, không dùng emoji)
        indices_text = ""
        for idx in overview.indices:
            direction = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "-"
            indices_text += f"- {idx.name}: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"
        
        # Thông tin nhóm ngành
        top_sectors_text = ", ".join([f"{s['name']}({s['change_pct']:+.2f}%)" for s in overview.top_sectors[:3]])
        bottom_sectors_text = ", ".join([f"{s['name']}({s['change_pct']:+.2f}%)" for s in overview.bottom_sectors[:3]])
        
        # Thông tin tin tức - hỗ trợ đối tượng SearchResult hoặc dict
        news_text = ""
        for i, n in enumerate(news[:6], 1):
            # Tương thích cả đối tượng SearchResult và dict
            title = self._compact_news_text(self._get_news_field(n, "title"), limit=90)
            snippet = self._compact_news_text(self._get_news_field(n, "snippet"), limit=220)
            source = self._compact_news_text(self._get_news_field(n, "source"), limit=60)
            published_date = self._compact_news_text(self._get_news_field(n, "published_date"), limit=30)
            url = self._compact_news_text(self._get_news_field(n, "url"), limit=180)
            meta_parts = [part for part in (source, published_date) if part]
            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""
            url_line = f"\n   URL: {url}" if url else ""
            news_text += f"{i}. {title}{meta}\n   {snippet or '-'}{url_line}\n"
        
        # Lắp ráp khối tổng quan thị trường và nhóm ngành theo region (US stock không có dữ liệu tăng/giảm và nhóm ngành)
        stats_block = ""
        sector_block = ""
        if review_language == "en":
            if self.profile.has_market_stats:
                stats_block = f"""## Market Breadth
- Advancers: {overview.up_count} | Decliners: {overview.down_count} | Flat: {overview.flat_count}
- Limit-up: {overview.limit_up_count} | Limit-down: {overview.limit_down_count}
- Turnover: {overview.total_amount:.0f} ({self._get_turnover_unit_label()})"""
            else:
                stats_block = "## Market Breadth\n(No equivalent advance/decline statistics are available for this market.)"

            if self.profile.has_sector_rankings:
                sector_block = f"""## Sector Performance
Leading: {top_sectors_text if top_sectors_text else "N/A"}
Lagging: {bottom_sectors_text if bottom_sectors_text else "N/A"}"""
            else:
                sector_block = "## Sector Performance\n(Sector data not available for this market.)"
        else:
            if self.profile.has_market_stats:
                stats_block = f"""## Diễn biến thị trường
- Tăng: {overview.up_count} mã | Giảm: {overview.down_count} mã | Đi ngang: {overview.flat_count} mã
- Trần: {overview.limit_up_count} mã | Sàn: {overview.limit_down_count} mã
- Tổng GTGD: {overview.total_amount:.0f} ({self._get_turnover_unit_label()})"""
            else:
                stats_block = "## Diễn biến thị trường\n(Thị trường này không có thống kê số mã tăng/giảm tương đương.)"

            if self.profile.has_sector_rankings:
                sector_block = f"""## Nhóm ngành
Tăng mạnh: {top_sectors_text if top_sectors_text else "Chưa có dữ liệu"}
Giảm mạnh: {bottom_sectors_text if bottom_sectors_text else "Chưa có dữ liệu"}"""
            else:
                sector_block = "## Nhóm ngành\n(Thị trường này không có dữ liệu nhóm ngành.)"

        data_no_indices_hint = (
            "Lưu ý: Không lấy được dữ liệu thị trường. Hãy phân tích định tính chủ yếu dựa trên [Tin thị trường], không bịa ra mức điểm chỉ số."
            if not indices_text
            else ""
        )
        if review_language == "vi":
            data_no_indices_hint = (
                "Lưu ý: Không lấy được dữ liệu chỉ số. Hãy phân tích định tính chủ yếu dựa trên [Tin thị trường], không bịa ra mức điểm chỉ số."
                if not indices_text
                else ""
            )
            indices_placeholder = indices_text if indices_text else "Chưa có dữ liệu chỉ số (lỗi nguồn dữ liệu)"
            news_placeholder = news_text if news_text else "Chưa có tin liên quan"
        elif review_language == "en":
            data_no_indices_hint = (
                "Note: Market data fetch failed. Rely mainly on [Market News] for qualitative analysis. Do not invent index levels."
                if not indices_text
                else ""
            )
            indices_placeholder = indices_text if indices_text else "No index data (API error)"
            news_placeholder = news_text if news_text else "No relevant news"
        else:
            indices_placeholder = indices_text if indices_text else "Chưa có dữ liệu chỉ số (lỗi nguồn dữ liệu)"
            news_placeholder = news_text if news_text else "Chưa có tin liên quan"

        if review_language == "vi":
            return f"""Bạn là chuyên gia phân tích thị trường chứng khoán Việt Nam. Hãy lập một báo cáo tổng kết thị trường có cấu trúc dựa trên dữ liệu dưới đây.

【Yêu cầu quan trọng】
- Chỉ xuất văn bản Markdown thuần
- Không xuất JSON
- Không xuất code block
- Chỉ dùng emoji ít ở tiêu đề (mỗi tiêu đề tối đa 1)
- Toàn bộ báo cáo PHẢI viết bằng tiếng Việt
- Báo cáo như bàn làm việc của trader sau phiên: kết luận trước, rồi triển khai theo số liệu, dòng dẫn dắt, catalyst, kế hoạch
- Không lặp lại số liệu bảng đã được hệ thống chèn sẵn; phần nội dung giải thích ý nghĩa phía sau số liệu

---

# Dữ liệu thị trường hôm nay

## Ngày
{overview.date}

## Các chỉ số chính
{indices_placeholder}

## Tin thị trường
{news_placeholder}

{data_no_indices_hint}

{self._get_strategy_prompt_block()}

---

# Mẫu định dạng đầu ra (vui lòng tuân thủ đúng cấu trúc này)

## {overview.date} Tổng kết thị trường Việt Nam

> Một câu nêu trạng thái thị trường hôm nay, mâu thuẫn cốt lõi và hướng ưu tiên theo dõi ngày mai.

### 1. Tổng quan phiên
(2-3 câu khái quát chỉ số, thanh khoản và nhiệt độ tâm lý; nêu rõ "mạnh/ấm/đi ngang/yếu".)

### 2. Cấu trúc chỉ số
({self._get_index_hint()} Nêu rõ nhóm nào nâng đỡ, nhóm nào kéo lùi, cùng các mốc hỗ trợ/kháng cự quan trọng.)

### 3. Dòng tiền & khối ngoại
(Diễn giải thanh khoản, mua/bán ròng của khối ngoại và khẩu vị rủi ro.)

### 4. Nhóm ngành dẫn dắt
(Phân tích logic và độ bền của nhóm ngành tăng/giảm mạnh nhất.)

### 5. Catalyst tin tức
(Kết hợp tin 3 ngày gần nhất, chắt lọc catalyst thực sự ảnh hưởng tới giao dịch ngày mai.)

### 6. Kế hoạch giao dịch ngày mai
(Đưa ra kết luận tấn công/cân bằng/phòng thủ, vùng tỷ trọng, hướng quan tâm, hướng cần tránh và một điều kiện kích hoạt vô hiệu.)

### 7. Cảnh báo rủi ro
(Liệt kê các rủi ro cần theo dõi; cuối cùng bổ sung "Khuyến nghị chỉ mang tính tham khảo, không phải lời khuyên đầu tư.")

---

Hãy xuất trực tiếp nội dung báo cáo, không thêm lời giải thích nào khác.
"""

        if review_language == "en":
            report_title = self._get_review_title(overview.date).removeprefix("## ").strip()
            return f"""You are a professional US/A/H market analyst. Please produce a concise market recap report based on the data below.

[Requirements]
- Output pure Markdown only
- No JSON
- No code blocks
- Use emoji sparingly in headings (at most one per heading)
- The entire fixed shell, headings, guidance, and conclusion must be in English

---

# Today's Market Data

## Date
{overview.date}

## Major Indices
{indices_placeholder}

{stats_block}

{sector_block}

## Market News
{news_placeholder}

{data_no_indices_hint}

{self._get_strategy_prompt_block()}

---

# Output Template (follow this structure)

## {report_title}

### 1. Market Summary
(2-3 sentences summarizing overall market tone, index moves, and liquidity.)

### 2. Index Commentary
({self._get_index_hint()})

### 3. Fund Flows
(Interpret what turnover, participation, and flow signals imply.)

### 4. Sector Highlights
(Analyze the drivers behind the leading and lagging sectors or themes.)

### 5. Outlook
(Provide the near-term outlook based on price action and news.)

### 6. Risk Alerts
(List the main risks to monitor.)

### 7. Strategy Plan
(Provide an offensive/balanced/defensive stance, a position-sizing guideline, one invalidation trigger, and end with "For reference only, not investment advice.")

---

Output the report content directly, no extra commentary.
"""

        # Fallback prompt (non-VN, non-EN) — dùng tiếng Việt để đồng nhất
        return f"""Bạn là chuyên gia phân tích thị trường {self._get_market_scope_name('vi')}. Hãy tạo báo cáo tổng kết thị trường có cấu trúc dựa trên dữ liệu dưới đây.

【Yêu cầu quan trọng】
- Chỉ xuất văn bản Markdown thuần
- Không xuất JSON
- Không xuất code block
- Chỉ dùng emoji ít ở tiêu đề (mỗi tiêu đề tối đa 1)
- Báo cáo như bàn làm việc của trader sau phiên: kết luận trước, rồi triển khai theo số liệu, dòng dẫn dắt, catalyst, kế hoạch
- Không lặp lại số liệu bảng đã được hệ thống chèn sẵn; phần nội dung giải thích ý nghĩa phía sau số liệu

---

# Dữ liệu thị trường hôm nay

## Ngày
{overview.date}

## Các chỉ số chính
{indices_placeholder}

{stats_block}

{sector_block}

## Tin thị trường
{news_placeholder}

{data_no_indices_hint}

{self._get_strategy_prompt_block()}

---

# Mẫu định dạng đầu ra (vui lòng tuân thủ đúng cấu trúc này)

## {overview.date} Tổng kết thị trường {self._get_market_scope_name('vi')}

> Một câu nêu trạng thái thị trường hôm nay, mâu thuẫn cốt lõi và hướng ưu tiên theo dõi ngày mai.

### 1. Tổng quan phiên
(2-3 câu khái quát chỉ số, thanh khoản và nhiệt độ tâm lý; nêu rõ "mạnh/ấm/đi ngang/yếu".)

### 2. Cấu trúc chỉ số
({self._get_index_hint()} Nêu rõ nhóm nào nâng đỡ, nhóm nào kéo lùi, cùng các mốc hỗ trợ/kháng cự quan trọng.)

### 3. Nhóm ngành dẫn dắt
(Phân tích logic và độ bền của nhóm ngành tăng/giảm mạnh nhất.)

### 4. Dòng tiền & tâm lý
(Diễn giải thanh khoản, cấu trúc trần/sàn, độ rộng thị trường và khẩu vị rủi ro.)

### 5. Catalyst tin tức
(Kết hợp tin 3 ngày gần nhất, chắt lọc catalyst thực sự ảnh hưởng tới giao dịch ngày mai.)

### 6. Kế hoạch giao dịch ngày mai
(Đưa ra kết luận tấn công/cân bằng/phòng thủ, vùng tỷ trọng, hướng quan tâm, hướng cần tránh và một điều kiện kích hoạt vô hiệu.)

### 7. Cảnh báo rủi ro
(Liệt kê các rủi ro cần theo dõi; cuối cùng bổ sung "Khuyến nghị chỉ mang tính tham khảo, không phải lời khuyên đầu tư.")

---

Hãy xuất trực tiếp nội dung báo cáo, không thêm lời giải thích nào khác.
"""
    
    def _generate_template_review(self, overview: MarketOverview, news: List) -> str:
        """Dùng mẫu tạo báo cáo tổng kết (phương án dự phòng khi không có LLM)"""
        template_language = self._get_template_review_language()
        mood_code = self.profile.mood_index_code
        # Tìm chỉ số tương ứng theo mood_index_code
        # cn: mood_code="000001", idx.code có thể là "sh000001" (kết thúc bằng mood_code)
        # us: mood_code="SPX", idx.code trực tiếp là "SPX"
        mood_index = next(
            (
                idx
                for idx in overview.indices
                if idx.code == mood_code or idx.code.endswith(mood_code)
            ),
            None,
        )
        if mood_index:
            if mood_index.change_pct > 1:
                market_mood = self._get_market_mood_text("strong_up", template_language)
            elif mood_index.change_pct > 0:
                market_mood = self._get_market_mood_text("mild_up", template_language)
            elif mood_index.change_pct > -1:
                market_mood = self._get_market_mood_text("mild_down", template_language)
            else:
                market_mood = self._get_market_mood_text("strong_down", template_language)
        else:
            market_mood = self._get_market_mood_text("range", template_language)
        
        # Dữ liệu chỉ số (định dạng ngắn gọn)
        indices_text = ""
        for idx in overview.indices[:4]:
            direction = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "-"
            indices_text += f"- **{idx.name}**: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"
        
        # Thông tin nhóm ngành
        separator = ", " if template_language == "en" else "、"
        top_text = separator.join([s['name'] for s in overview.top_sectors[:3]])
        bottom_text = separator.join([s['name'] for s in overview.bottom_sectors[:3]])

        if template_language == "vi":
            return f"""## {overview.date} Tổng kết thị trường Việt Nam

> Thị trường Việt Nam hôm nay nhìn chung **{market_mood}**; ưu tiên theo dõi lực cầu tại chỉ số, biến động thanh khoản và độ bền của nhóm ngành.

### 1. Tổng quan phiên
Thị trường chứng khoán Việt Nam hôm nay thể hiện trạng thái **{market_mood}**.

### 2. Cấu trúc chỉ số
{indices_text or "- Chưa có dữ liệu chỉ số."}

### 3. Dòng tiền & khối ngoại
- Kết hợp thanh khoản và diễn biến chỉ số, hiện phù hợp chờ xác nhận, tránh mua đuổi chỉ dựa trên một điểm nóng.

### 4. Catalyst tin tức
- Khi chưa có tin khả dụng, nên hạ mức độ chắc chắn về độ bền của câu chuyện nhóm ngành.

{self._get_strategy_markdown_block(template_language)}

### 7. Cảnh báo rủi ro
- Thị trường luôn có rủi ro, đầu tư cần thận trọng. Các số liệu trên chỉ mang tính tham khảo, không phải lời khuyên đầu tư.

---
*Thời gian tổng kết: {datetime.now().strftime('%H:%M')}*
"""

        if template_language == "en":
            stats_section = ""
            if self.profile.has_market_stats:
                stats_section = f"""
### 3. Breadth & Liquidity
| Metric | Value |
|--------|-------|
| Advancers | {overview.up_count} |
| Decliners | {overview.down_count} |
| Limit-up | {overview.limit_up_count} |
| Limit-down | {overview.limit_down_count} |
| Turnover ({self._get_turnover_unit_label()}) | {overview.total_amount:.0f} |
"""
            sector_section = ""
            if self.profile.has_sector_rankings and (top_text or bottom_text):
                sector_section = f"""
### 4. Sector Highlights
- **Leaders**: {top_text or "N/A"}
- **Laggards**: {bottom_text or "N/A"}
"""
            market_names = {"us": "US Market Recap", "hk": "HK Market Recap"}
            market_name = market_names.get(self.region, "A-share Market Recap")
            report = f"""## {overview.date} {market_name}

### 1. Market Summary
Today's {self._get_market_scope_name(template_language)} showed **{market_mood}**.

### 2. Major Indices
{indices_text or "- No index data available"}
{stats_section}
{sector_section}
### 5. Risk Alerts
Market conditions can change quickly. The data above is for reference only and does not constitute investment advice.

{self._get_strategy_markdown_block(template_language)}

---
*Review Time: {datetime.now().strftime('%H:%M')}*
"""
            return report

        market_labels = {"cn": "A-share", "us": "Mỹ", "hk": "Hồng Kông"}
        market_label = market_labels.get(self.region, "A-share")
        dashboard_block = self._build_stats_block(overview)
        indices_block = self._build_indices_block(overview)
        sector_block = self._build_sector_block(overview)
        return f"""## {overview.date} Tổng kết thị trường {market_label}

> Thị trường {market_label} hôm nay nhìn chung **{market_mood}**; ưu tiên theo dõi lực cầu tại chỉ số, biến động thanh khoản và độ bền của nhóm ngành.

### 1. Tổng quan phiên
{dashboard_block or "Chưa có dữ liệu độ rộng thị trường."}

### 2. Cấu trúc chỉ số
{indices_block or indices_text or "Chưa có dữ liệu chỉ số."}

### 3. Nhóm ngành dẫn dắt
{sector_block or "- Chưa có bảng xếp hạng nhóm ngành."}

### 4. Dòng tiền & tâm lý
- Kết hợp thanh khoản và diễn biến chỉ số, hiện phù hợp chờ xác nhận, tránh mua đuổi chỉ dựa trên một điểm nóng.

### 5. Catalyst tin tức
- Khi chưa có tin khả dụng, nên hạ mức độ chắc chắn về độ bền của câu chuyện nhóm ngành.

{self._get_strategy_markdown_block(template_language)}

### 7. Cảnh báo rủi ro
- Thị trường luôn có rủi ro, đầu tư cần thận trọng. Các số liệu trên chỉ mang tính tham khảo, không phải lời khuyên đầu tư.

---
*Thời gian tổng kết: {datetime.now().strftime('%H:%M')}*
"""
    
    def _run_daily_review_parts(self) -> MarketLightReviewResult:
        """Run market review once and keep report/snapshot on the same overview."""
        logger.info("========== Bắt đầu phân tích tổng kết thị trường ==========")

        # 1. Lấy tổng quan thị trường
        overview = self.get_market_overview()

        # 2. Tìm kiếm tin tức thị trường
        news = self.search_market_news()
        news = self._merge_persisted_market_intelligence(news)

        # 3. Tạo báo cáo tổng kết
        report = self.generate_market_review(overview, news)
        snapshot = self.build_market_light_snapshot(overview)
        structured_payload = self.build_market_review_payload(
            overview,
            news,
            report,
            snapshot,
        )

        logger.info("========== Phân tích tổng kết thị trường hoàn tất ==========")

        return MarketLightReviewResult(
            overview=overview,
            report=report,
            market_light_snapshot=snapshot,
            structured_payload=structured_payload,
        )

    def _merge_persisted_market_intelligence(self, news: List) -> List:
        """Merge local persisted market intelligence and search news with bounded prompt/payload slot preservation."""
        search_news = list(news or [])
        merged_local = []
        seen_urls = {
            self._get_news_field(item, "url")
            for item in search_news
            if self._get_news_field(item, "url")
        }
        try:
            service = IntelligenceService()
            payload = service.list_items(
                scope_type="market",
                market=self.region,
                published_days=max(1, int(self.config.get_effective_news_window_days() or 1)),
                page=1,
                page_size=6,
            )
            for item in payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)
                merged_local.append({
                    "title": item.get("title") or "Tin tức chưa đặt tiêu đề",
                    "snippet": item.get("summary") or "",
                    "source": item.get("source") or item.get("source_name") or "local-intel",
                    "published_date": item.get("published_at") or "",
                    "url": "" if url.startswith("no-url:intel:") else url,
                })
        except Exception as exc:
            logger.debug("[ThiTruong] %s action=load_local_intelligence status=failed error=%s", self._log_context(), exc)
        merged_news = []
        merged_local_index = 0
        merged_search_index = 0
        while merged_local_index < len(merged_local) or merged_search_index < len(search_news):
            if merged_local_index < len(merged_local):
                merged_news.append(merged_local[merged_local_index])
                merged_local_index += 1
            if merged_search_index < len(search_news):
                merged_news.append(search_news[merged_search_index])
                merged_search_index += 1
        return merged_news

    def run_daily_review(self) -> str:
        """
        Thực thi quy trình tổng kết thị trường hàng ngày

        Returns:
            Văn bản báo cáo tổng kết
        """
        return self.run_daily_review_with_snapshot().report

    def run_daily_review_with_snapshot(self) -> MarketLightReviewResult:
        """Run daily review and return the report plus its structured Market Light snapshot."""
        return self._run_daily_review_parts()


# Điểm vào kiểm thử
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )

    analyzer = MarketAnalyzer()

    # Kiểm thử lấy tổng quan thị trường
    overview = analyzer.get_market_overview()
    print(f"\n=== Tổng quan thị trường ===")
    print(f"Ngày: {overview.date}")
    print(f"Số chỉ số: {len(overview.indices)}")
    for idx in overview.indices:
        print(f"  {idx.name}: {idx.current:.2f} ({idx.change_pct:+.2f}%)")
    print(f"Tăng: {overview.up_count} | Giảm: {overview.down_count}")
    print(f"Tổng GTGD: {overview.total_amount:.0f}")

    # Kiểm thử tạo báo cáo mẫu
    report = analyzer._generate_template_review(overview, [])
    print(f"\n=== Báo cáo tổng kết ===")
    print(report)
