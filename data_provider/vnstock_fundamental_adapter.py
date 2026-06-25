# -*- coding: utf-8 -*-
"""
VnstockFundamentalAdapter — Vietnam fundamentals via the vnstock library.

Mirrors YfinanceFundamentalAdapter: exposes get_fundamental_bundle(stock_code)
returning {status, growth, earnings, belong_boards, _valuation_extras,
source_chain, errors} consumed by DataFetcherManager._build_vn_fundamental_context.

Sources (all full VND):
  - Company.overview()      -> market cap, current/target price, foreign %, sector, 52w hi/lo
  - Finance.income_statement -> net_sales (revenue), attributable_to_parent_company (net profit)
  - Finance.balance_sheet    -> owners_equity, total_assets

IMPORTANT: Finance.ratio() is UNRELIABLE on the free VCI tier (returns duplicated
2018 data), so P/E, P/B, ROE and growth are COMPUTED from the statement tables,
which do return real multi-year data (2018..latest).
"""

import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


class VnstockFundamentalAdapter:
    """Fundamental bundle builder backed by the vnstock VCI source."""

    name = "VnstockFundamentalAdapter"

    @staticmethod
    def _convert(stock_code: str) -> str:
        code = (stock_code or "").strip().upper()
        return code[:-3] if code.endswith(".VN") else code

    @staticmethod
    def _year_cols(df) -> list:
        return sorted({str(c) for c in df.columns if str(c).isdigit()})

    @staticmethod
    def _pick(df, item_id: str, year: str) -> Optional[float]:
        try:
            if "item_id" not in df.columns:
                return None
            rows = df[df["item_id"].astype(str) == item_id]
            if rows.empty:
                return None
            for c in df.columns:
                if str(c) == year:
                    return _safe_float(rows.iloc[0][c])
            return None
        except Exception:
            return None

    def get_fundamental_bundle(self, stock_code: str) -> Dict[str, Any]:
        symbol = self._convert(stock_code)
        result: Dict[str, Any] = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "belong_boards": [],
            "_valuation_extras": {},
            "source_chain": [],
            "errors": [],
        }

        # ── Fetch the 3 sources sequentially. Concurrent VCI requests get
        # rate-limited/conflict (overview drops out), so keep them serial. ──
        ov = inc = bal = None
        try:
            from vnstock.api.company import Company
            ov = Company(symbol=symbol, source="VCI").overview()
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"overview:{type(exc).__name__}:{exc}")
        try:
            from vnstock.api.financial import Finance
            _fin = Finance(symbol=symbol, source="VCI")
            inc = _fin.income_statement(period="year", lang="en")
            bal = _fin.balance_sheet(period="year", lang="en")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"statements:{type(exc).__name__}:{exc}")

        # ── Parse company overview (reliable, single row, full VND) ──
        market_cap = current_price = foreign_pct = None
        high_52w = low_52w = target_price = sector = None
        if ov is not None and not ov.empty:
            r = ov.iloc[0]
            market_cap = _safe_float(r.get("market_cap"))
            current_price = _safe_float(r.get("current_price"))
            fp = _safe_float(r.get("foreigner_percentage"))
            foreign_pct = round(fp * 100, 2) if fp is not None else None  # fraction -> %
            high_52w = _safe_float(r.get("highest_price1_year"))
            low_52w = _safe_float(r.get("lowest_price1_year"))
            target_price = _safe_float(r.get("target_price"))
            sector = (str(r.get("sector") or "").strip() or None)
            result["source_chain"].append("overview:vnstock")

        # ── Parse statements (income + balance), reliable multi-year ──
        revenue_latest = revenue_prev = None
        np_latest = np_prev = None
        equity_latest = equity_prev = total_assets = None
        report_year = None
        if inc is not None and not inc.empty:
            yi = self._year_cols(inc)
            if yi:
                report_year = yi[-1]
                revenue_latest = self._pick(inc, "net_sales", yi[-1])
                np_latest = self._pick(inc, "attributable_to_parent_company", yi[-1])
            if len(yi) >= 2:
                revenue_prev = self._pick(inc, "net_sales", yi[-2])
                np_prev = self._pick(inc, "attributable_to_parent_company", yi[-2])
            result["source_chain"].append("income:vnstock")
        if bal is not None and not bal.empty:
            yb = self._year_cols(bal)
            if yb:
                equity_latest = self._pick(bal, "owners_equity", yb[-1])
                total_assets = self._pick(bal, "total_assets", yb[-1])
            if len(yb) >= 2:
                equity_prev = self._pick(bal, "owners_equity", yb[-2])
            result["source_chain"].append("balance:vnstock")

        # ── Computed metrics ──
        def _yoy(cur, prev):
            if cur is not None and prev not in (None, 0):
                return round((cur - prev) / abs(prev) * 100, 2)
            return None

        revenue_yoy = _yoy(revenue_latest, revenue_prev)
        net_profit_yoy = _yoy(np_latest, np_prev)

        roe = None
        if np_latest is not None and equity_latest is not None:
            avg_eq = (equity_latest + equity_prev) / 2 if equity_prev is not None else equity_latest
            if avg_eq and avg_eq > 0:
                roe = round(np_latest / avg_eq * 100, 2)
        roa = None
        if np_latest is not None and total_assets not in (None, 0):
            roa = round(np_latest / total_assets * 100, 2)
        pe = round(market_cap / np_latest, 2) if (market_cap and np_latest and np_latest > 0) else None
        pb = round(market_cap / equity_latest, 2) if (market_cap and equity_latest and equity_latest > 0) else None

        growth = {
            "revenue_yoy": revenue_yoy,
            "net_profit_yoy": net_profit_yoy,
            "roe": roe,
            "roa": roa,
            "gross_margin": None,  # not computed (cost-of-sales item id not verified)
        }
        if any(v is not None for v in growth.values()):
            result["growth"] = growth

        financial_report = {
            "report_date": report_year,
            "revenue": revenue_latest,            # full VND
            "net_profit_parent": np_latest,       # full VND (lợi nhuận thuộc về cổ đông công ty mẹ)
            "operating_cash_flow": None,
            "roe": roe,
            "currency": "VND",
        }
        if revenue_latest is not None or np_latest is not None:
            result["earnings"] = {"financial_report": financial_report}

        if sector:
            result["belong_boards"] = [{"name": sector, "type": "行业"}]

        result["_valuation_extras"] = {
            "pe_ratio": pe,
            "pb_ratio": pb,
            "total_mv": market_cap,    # full VND
            "circ_mv": None,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "foreign_ownership_pct": foreign_pct,
            "target_price": target_price,
            "current_price": current_price,
        }

        has_content = bool(
            result.get("growth")
            or result.get("earnings")
            or any(v is not None for v in result["_valuation_extras"].values())
        )
        result["status"] = "partial" if has_content else "not_supported"
        return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    b = VnstockFundamentalAdapter().get_fundamental_bundle("FPT.VN")
    print(json.dumps(b, ensure_ascii=False, indent=2))
