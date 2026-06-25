# -*- coding: utf-8 -*-
"""
Cấu hình vùng thị trường cho tổng kết thị trường

Định nghĩa metadata của từng vùng thị trường: mã chỉ số, từ khóa tìm kiếm tin tức,
gợi ý Prompt, v.v. — dùng cho MarketAnalyzer chuyển đổi hành vi tổng kết
giữa A-share / Mỹ / Hồng Kông / Việt Nam.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class MarketProfile:
    """Cấu hình vùng thị trường cho tổng kết thị trường"""

    region: str  # "cn" | "us"
    # Mã chỉ số dùng để đánh giá xu hướng tổng thể: cn dùng 000001 (Thượng Hải), us dùng SPX
    mood_index_code: str
    # Từ khóa tìm kiếm tin tức
    news_queries: List[str]
    # Gợi ý Prompt bình luận chỉ số
    prompt_index_hint: str
    # Tổng quan thị trường có chứa số mã tăng/giảm, trần/sàn không (A-share có, Mỹ không)
    has_market_stats: bool
    # Tổng quan thị trường có chứa bảng xếp hạng ngành không (A-share có, Mỹ chưa có)
    has_sector_rankings: bool


CN_PROFILE = MarketProfile(
    region="cn",
    mood_index_code="000001",
    news_queries=[
        "A股 大盘 复盘",
        "股市 行情 分析",
        "A股 市场 热点 板块",
    ],
    prompt_index_hint="分析上证、深证、创业板等各指数走势特点",
    has_market_stats=True,
    has_sector_rankings=True,
)

US_PROFILE = MarketProfile(
    region="us",
    mood_index_code="SPX",
    news_queries=[
        "美股 大盘",
        "US stock market",
        "S&P 500 NASDAQ",
    ],
    prompt_index_hint="分析标普500、纳斯达克、道指等各指数走势特点",
    has_market_stats=False,
    has_sector_rankings=False,
)

HK_PROFILE = MarketProfile(
    region="hk",
    mood_index_code="HSI",
    news_queries=[
        "港股 大盘 复盘",
        "Hong Kong stock market",
        "恒生指数 行情",
    ],
    prompt_index_hint="分析恒生指数、恒生科技指数、国企指数等各指数走势特点",
    has_market_stats=False,
    has_sector_rankings=False,
)

VN_PROFILE = MarketProfile(
    region="vn",
    mood_index_code="VNINDEX",
    news_queries=[
        "VN-Index chứng khoán Việt Nam",
        "thị trường chứng khoán HOSE HNX",
        "khối ngoại mua bán ròng VNINDEX",
    ],
    prompt_index_hint="分析 VNINDEX、VN30、HNX-Index、UPCOM-Index 等越南各指数走势特点",
    has_market_stats=False,
    has_sector_rankings=False,
)


def get_profile(region: str) -> MarketProfile:
    """Trả về MarketProfile tương ứng theo region"""
    if region == "us":
        return US_PROFILE
    if region == "hk":
        return HK_PROFILE
    if region == "vn":
        return VN_PROFILE
    return CN_PROFILE
