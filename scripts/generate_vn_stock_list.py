#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate scripts/stock_index_seeds/stock_list_vn.csv from the vnstock library.

The seed feeds scripts/generate_index_from_csv.py (market 'VN') to build the
stock autocomplete index. Output schema mirrors the JP/KR seeds:

    ts_code,symbol,name,enname,aliases

For Vietnam, both ts_code and symbol carry the explicit ``.VN`` suffix (e.g.
``FPT.VN``) so the code stays unambiguous against US tickers throughout the
system. Only active equities on HOSE (HSX) / HNX / UPCOM are emitted;
DELISTED and BOND rows are skipped.

Usage:
    conda activate bank-cluster
    python scripts/generate_vn_stock_list.py
    python scripts/generate_vn_stock_list.py --output /tmp/stock_list_vn.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Active stock exchanges in vnstock's listing (HSX == HOSE).
_VN_STOCK_EXCHANGES = {"HSX", "HNX", "UPCOM"}

# Curated brand/short-name aliases for well-known tickers (improves name search).
# These are display aliases only; bare-code resolution for VN is disabled in
# src/data/stock_index_loader.py, so aliases never reroute a bare US ticker.
_VN_ALIASES = {
    "VNM": ["Vinamilk"],
    "VCB": ["Vietcombank"],
    "VIC": ["Vingroup"],
    "VHM": ["Vinhomes"],
    "VRE": ["Vincom Retail"],
    "TCB": ["Techcombank"],
    "MBB": ["MB Bank", "MBBank"],
    "HPG": ["Hoa Phat", "Hòa Phát"],
    "FPT": ["FPT Corp"],
    "VPB": ["VPBank"],
    "STB": ["Sacombank"],
    "ACB": ["ACB Bank"],
    "MSN": ["Masan"],
    "SAB": ["Sabeco"],
    "CTG": ["VietinBank"],
    "SSI": ["SSI Securities"],
    "VND": ["VNDirect"],
    "HDB": ["HDBank"],
    "TPB": ["TPBank"],
    "GAS": ["PV Gas", "PetroVietnam Gas"],
    "BID": ["BIDV"],
    "PLX": ["Petrolimex"],
    "POW": ["PV Power"],
    "MWG": ["Mobile World", "Thế Giới Di Động"],
    "VJC": ["Vietjet"],
    "GVR": ["Rubber Group"],
    "BCM": ["Becamex"],
    "DGC": ["Duc Giang"],
}


def generate_vn_stock_list(output_path: Path) -> int:
    try:
        from vnstock.api.listing import Listing
    except ImportError:
        print("[Error] vnstock not installed. Run: pip install vnstock", file=sys.stderr)
        return 1

    print("Fetching VN symbols from vnstock (source=VCI)...")
    df = Listing(source="VCI").symbols_by_exchange()
    if df is None or df.empty:
        print("[Error] empty symbol listing returned", file=sys.stderr)
        return 1

    mask = (df["type"].astype(str).str.upper() == "STOCK") & (
        df["exchange"].astype(str).str.upper().isin(_VN_STOCK_EXCHANGES)
    )
    stocks = df[mask].copy()
    stocks = stocks.sort_values("symbol").reset_index(drop=True)

    print(f"Active stocks: {len(stocks)}")
    for exch in sorted(_VN_STOCK_EXCHANGES):
        print(f"  {exch}: {(stocks['exchange'].astype(str).str.upper() == exch).sum()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts_code", "symbol", "name", "enname", "aliases"])
        for _, row in stocks.iterrows():
            sym = str(row["symbol"]).strip().upper()
            if not sym:
                continue
            ts_code = f"{sym}.VN"
            name = str(row.get("organ_name") or "").strip()
            enname = str(row.get("organ_short_name") or "").strip()
            aliases = "|".join(_VN_ALIASES.get(sym, []))
            writer.writerow([ts_code, ts_code, name, enname, aliases])
            written += 1

    print(f"Wrote {written} rows -> {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate VN stock seed CSV from vnstock")
    default_out = Path(__file__).parent / "stock_index_seeds" / "stock_list_vn.csv"
    parser.add_argument("--output", default=str(default_out))
    args = parser.parse_args()
    return generate_vn_stock_list(Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
