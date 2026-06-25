# -*- coding: utf-8 -*-
"""
Post-render Vietnamese glossary for VN stock reports.

The decision-dashboard report is rendered by Python scaffold (Chinese labels) from
LLM JSON. Even with the LLM forced to output Vietnamese prose, the Python scaffold
(section headers, table labels, enum strings) stays Chinese. This module provides a
deterministic backstop: apply_vn_report_glossary() replaces every Chinese scaffold
string with its standard Vietnamese term (see VN_TERMINOLOGY.md).

It is applied ONLY to reports that contain a ``.VN`` ticker, so Chinese (cn/hk) and
English reports are never touched. The map is ordered longest-first so compound
strings (归母净利润) are replaced before their substrings (净利).
"""

# (chinese, vietnamese) — ORDER MATTERS: longest / most-specific first.
_VN_REPORT_GLOSSARY = [
    # ── Long compound phrases ──
    ("AI生成，仅供参考，不构成投资建议", "Nội dung do AI tạo, chỉ mang tính tham khảo, không phải khuyến nghị đầu tư"),
    ("筹码分布未启用或数据源暂不可用，未纳入筹码判断。", "Phân tích phân phối giá vốn chưa khả dụng cho thị trường VN — không đưa vào đánh giá."),
    ("筹码分布数据缺失，无法评估筹码集中度及潜在抛压。", "Không có dữ liệu phân phối giá vốn để đánh giá mức độ cô đặc và áp lực bán."),
    ("资金流不可用，未使用资金流校准", "Không có dữ liệu dòng tiền; không áp hiệu chỉnh dòng tiền"),
    ("近12月每股现金分红(税前)", "Cổ tức tiền mặt/cp 12 tháng (trước thuế)"),
    # ── Section headings & scaffold ──
    ("市场状态", "Trạng thái thị trường"),
    ("阶段未知", "Giai đoạn chưa rõ"),
    ("行情来源", "Nguồn dữ liệu"),
    ("越南股", "Cổ phiếu Việt Nam"),
    ("只股票", "cổ phiếu"),
    ("共分析", "Đã phân tích"),
    ("检查项", "Mục kiểm tra"),
    ("缩量", "khối lượng thấp"),
    ("放量", "khối lượng cao"),
    ("筹码分布", "Phân phối giá vốn"),
    ("筹码", "Phân phối giá vốn"),
    ("行业", "Ngành"),
    ("越南市场扩展技术指标", "Chỉ báo kỹ thuật mở rộng (VN)"),
    ("重要信息速览", "Thông tin nhanh"),
    ("决策仪表盘", "Bảng quyết định giao dịch"),
    ("历史信号对比", "So sánh tín hiệu lịch sử"),
    ("盘中决策护栏", "Rào chắn quyết định trong phiên"),
    ("分析结果摘要", "Tóm tắt kết quả phân tích"),
    ("股票分析报告", "Báo cáo phân tích cổ phiếu"),
    ("报告生成时间", "Thời gian tạo báo cáo"),
    ("检查未通过项", "Mục chưa đạt"),
    ("数据透视", "Phân tích dữ liệu"),
    ("核心结论", "Kết luận chính"),
    ("作战计划", "Chiến lược giao dịch"),
    ("一句话决策", "Quyết định một câu"),
    ("检查清单", "Danh sách kiểm tra"),
    ("关联板块", "Ngành/nhóm liên quan"),
    ("持仓建议", "Khuyến nghị vị thế"),
    ("操作点位", "Mức giá hành động"),
    ("业绩预期", "Triển vọng kinh doanh"),
    ("风险警报", "Cảnh báo rủi ro"),
    ("利好催化", "Xúc tác tích cực"),
    ("最新动态", "Tin tức mới nhất"),
    ("操作建议", "Khuyến nghị hành động"),
    ("持仓情况", "Tình trạng vị thế"),
    ("舆情情绪", "Tâm lý thị trường"),
    ("当日行情", "Diễn biến trong phiên"),
    ("置信度理由", "Lý do độ tin cậy"),
    ("行动窗口", "Khung hành động"),
    ("当前动作", "Hành động hiện tại"),
    ("观察条件", "Điều kiện theo dõi"),
    ("下次检查", "Kiểm tra tiếp"),
    ("数据限制", "Giới hạn dữ liệu"),
    ("理想买入点", "Vùng mua tốt"),
    ("次优买入点", "Vùng mua thứ hai"),
    ("建仓策略", "Chiến lược giải ngân"),
    ("风控策略", "Quản trị rủi ro"),
    ("仓位建议", "Gợi ý tỷ trọng"),
    ("价格指标", "Chỉ số giá"),
    ("趋势强度", "Độ mạnh xu hướng"),
    ("分析模型", "Mô hình phân tích"),
    ("详细报告见", "Xem báo cáo chi tiết:"),
    ("财务摘要", "Tóm tắt tài chính"),
    ("财报摘要", "Tóm tắt tài chính"),
    # ── Fundamentals ──
    ("归母净利润", "LNST cổ đông công ty mẹ"),
    ("营业收入", "Doanh thu (DT)"),
    ("经营现金流", "Dòng tiền hoạt động"),
    ("营收同比", "DT so cùng kỳ (YoY)"),
    ("净利同比", "LNST so cùng kỳ (YoY)"),
    ("毛利率", "Biên lợi nhuận gộp"),
    ("报告期", "Kỳ báo cáo"),
    ("目标价", "Giá mục tiêu"),
    ("市值", "Vốn hóa"),
    # ── Trend / MA ──
    ("均线排列", "Trạng thái MA"),
    ("多头排列", "MA xếp tăng"),
    ("空头排列", "MA xếp giảm"),
    ("乖离率(MA5)", "Độ lệch MA5 (BIAS)"),
    ("乖离率", "Độ lệch MA (BIAS)"),
    ("均线", "Đường MA"),
    # ── Price / trading ──
    ("成交量", "Khối lượng (KL)"),
    ("成交额", "Giá trị giao dịch (GTGD)"),
    ("当前价", "Giá hiện tại"),
    ("换手率", "Thanh khoản"),
    ("涨跌幅", "% Thay đổi"),
    ("涨跌额", "Mức thay đổi"),
    ("振幅", "Biên độ"),
    ("收盘", "Đóng cửa"),
    ("昨收", "Tham chiếu"),
    ("开盘", "Mở cửa"),
    ("最高", "Cao nhất"),
    ("最低", "Thấp nhất"),
    ("量比", "Tỷ lệ KL"),
    # ── Levels / position ──
    ("支撑位", "Ngưỡng hỗ trợ"),
    ("压力位", "Ngưỡng kháng cự"),
    ("止损位", "Ngưỡng cắt lỗ"),
    ("目标位", "Giá mục tiêu"),
    ("持仓者", "Người đang nắm giữ"),
    ("空仓者", "Người chưa có vị thế"),
    ("继续持有", "Tiếp tục nắm giữ"),
    ("仓位", "Tỷ trọng"),
    # ── Decision / trend enums ──
    ("强烈买入", "Mua mạnh"),
    ("强烈卖出", "Bán mạnh"),
    ("强烈看多", "Rất tích cực"),
    ("强烈看空", "Rất tiêu cực"),
    ("减仓", "Giảm tỷ trọng"),
    ("买入", "Mua"),
    ("持有", "Nắm giữ"),
    ("卖出", "Bán"),
    ("观望", "Quan sát"),
    ("看多", "Tích cực"),
    ("看空", "Tiêu cực"),
    ("震荡", "Đi ngang"),
    # ── Sentiment ──
    ("极度乐观", "Rất tích cực"),
    ("极度悲观", "Rất tiêu cực"),
    ("乐观", "Tích cực"),
    ("悲观", "Tiêu cực"),
    ("中性", "Trung lập"),
    # ── Confidence / risk ──
    ("健康", "Tốt"),
    ("警惕", "Thận trọng"),
    ("警戒", "Cảnh báo"),
    ("危险", "Nguy hiểm"),
    ("安全", "An toàn"),
    # ── Placeholders / fallback ──
    ("待确认股票", "Mã chưa xác định"),
    ("数据缺失", "Dữ liệu không có"),
    ("待补充", "Chưa có dữ liệu"),
    ("无分析结果", "Không có kết quả phân tích"),
    # ── Misc / table columns ──
    ("领涨", "Dẫn đầu tăng"),
    ("领跌", "Dẫn đầu giảm"),
    ("板块", "Ngành"),
    ("类型", "Loại"),
    ("建议", "Khuyến nghị"),
    ("趋势", "Xu hướng"),
    ("评分", "Điểm"),
    ("时间", "Thời gian"),
    ("时效性", "Tính thời điểm"),
    ("本周内", "Trong tuần"),
    ("今日内", "Trong ngày"),
    ("一般", "Trung bình"),
    # ── Boolean scaffold (single chars — kept last so compounds resolve first) ──
    ("否", "Không"),
    ("是", "Có"),
]


import re


def _fmt_shares(v: float) -> str:
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f} triệu cp"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.1f} nghìn cp"
    return f"{v:.0f} cp"


def _fmt_vnd(v: float) -> str:
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f} tỷ VND"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f} triệu VND"
    return f"{v:.0f} VND"


def _num(s: str) -> float:
    return float(s.replace(",", ""))


# Chinese myriad/number units (万=1e4, 亿=1e8, 万亿=1e12). The Python renderer
# emits e.g. "169.15 万股" / "1199.27 亿元"; we must recompute the SCALE, not just
# swap the unit word. Order: longest unit first.
_NUM_UNIT_RULES = [
    (re.compile(r"([\d,]+\.?\d*)\s*万亿元"), lambda m: _fmt_vnd(_num(m.group(1)) * 1e12)),
    (re.compile(r"([\d,]+\.?\d*)\s*万亿"),   lambda m: _fmt_vnd(_num(m.group(1)) * 1e12)),
    (re.compile(r"([\d,]+\.?\d*)\s*亿股"),   lambda m: _fmt_shares(_num(m.group(1)) * 1e8)),
    (re.compile(r"([\d,]+\.?\d*)\s*万股"),   lambda m: _fmt_shares(_num(m.group(1)) * 1e4)),
    (re.compile(r"([\d,]+\.?\d*)\s*股"),     lambda m: _fmt_shares(_num(m.group(1)))),
    (re.compile(r"([\d,]+\.?\d*)\s*亿元"),   lambda m: _fmt_vnd(_num(m.group(1)) * 1e8)),
    (re.compile(r"([\d,]+\.?\d*)\s*万元"),   lambda m: _fmt_vnd(_num(m.group(1)) * 1e4)),
    (re.compile(r"([\d,]+\.?\d*)\s*元"),     lambda m: _fmt_vnd(_num(m.group(1)))),
]


def _convert_cn_number_units(text: str) -> str:
    for pattern, repl in _NUM_UNIT_RULES:
        try:
            text = pattern.sub(repl, text)
        except Exception:
            continue
    return text


def apply_vn_report_glossary(text: str) -> str:
    """Replace Chinese scaffold strings + number units with Vietnamese equivalents.

    No-op when ``text`` is falsy. Number units (万/亿/万亿 + 股/元) are recomputed to
    triệu cp / tỷ VND first; then scaffold strings are replaced longest-first.
    Safe to call repeatedly.
    """
    if not text:
        return text
    text = _convert_cn_number_units(text)
    for zh, vi in _VN_REPORT_GLOSSARY:
        if zh in text:
            text = text.replace(zh, vi)
    # residual unit words (safe, specific forms only)
    for a, b in (("越南盾", "VND"), ("(股)", "(cp)"), ("（股）", "（cp）"),
                 ("(元)", "(VND)"), ("（元）", "（VND）"), ("亿", ""), ("万", "")):
        text = text.replace(a, b)
    return text
