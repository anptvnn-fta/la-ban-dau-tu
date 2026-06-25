#!/usr/bin/env python3
"""
Generate VN stock autocomplete index JSON for the React stock app.

Reads the seed CSV and emits a bare tuple-array JSON (StockIndexTuple[])
that matches the exact format expected by stockIndexLoader.ts / stockIndexFields.ts.

Tuple shape (10 positions, index as defined in INDEX_FIELD):
  0  canonicalCode  str   e.g. "VCB.VN"
  1  displayCode    str   e.g. "VCB.VN"
  2  nameZh         str   Vietnamese company name (nameZh field repurposed for VN)
  3  pinyinFull     str   "" (no pinyin for VN stocks)
  4  pinyinAbbr     str   "" (no pinyin for VN stocks)
  5  aliases        list  [str] — bare symbol always included; CSV aliases split on "|"
  6  market         str   "VN"
  7  assetType      str   "stock"
  8  active         bool  true
  9  popularity     int   0..100 (higher for well-known blue-chip tickers)
"""

import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Popularity map — well-known VN blue-chip tickers get higher scores so they
# rank first in autocomplete results.  All others default to 0.
# ---------------------------------------------------------------------------
POPULARITY: dict[str, int] = {
    # Banking
    "VCB": 100,
    "BID": 95,
    "CTG": 90,
    "MBB": 85,
    "TCB": 85,
    "ACB": 80,
    "HDB": 75,
    "STB": 70,
    "VPB": 70,
    "TPB": 65,
    # Large-caps / VN30 staples
    "VIC": 100,
    "VNM": 95,
    "FPT": 90,
    "HPG": 90,
    "GAS": 85,
    "SAB": 80,
    "MSN": 80,
    "MWG": 80,
    "VHM": 75,
    "BCM": 70,
    "PLX": 70,
    "GVR": 65,
    "POW": 65,
    "SSI": 65,
    "DGC": 60,
    "VRE": 60,
    "NVL": 60,
    "PDR": 55,
    "KDH": 55,
    "DXG": 50,
}


def parse_aliases(raw: str, symbol: str) -> list[str]:
    """
    Build the aliases array.
    - Always include the bare symbol (e.g. "VCB")
    - Split the CSV aliases field on "|" and include non-empty parts
    - Deduplicate while preserving order
    """
    seen: set[str] = set()
    result: list[str] = []

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    # The bare ticker symbol comes first (most useful for autocomplete)
    add(symbol)

    # Split CSV aliases field on pipe delimiter
    if raw:
        for part in raw.split("|"):
            add(part)

    return result


def get_symbol(ts_code: str) -> str:
    """Extract bare symbol from ts_code like 'VCB.VN' -> 'VCB'."""
    return ts_code.split(".")[0] if "." in ts_code else ts_code


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    seed_path = os.path.join(script_dir, "stock_index_seeds", "stock_list_vn.csv")
    output_dir = os.path.join(repo_root, "web", "public")
    output_path = os.path.join(output_dir, "stocks.index.json")

    print(f"Reading seed CSV: {seed_path}")
    if not os.path.exists(seed_path):
        print(f"ERROR: Seed CSV not found at {seed_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    tuples: list[list] = []

    with open(seed_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts_code: str = row["ts_code"].strip()
            name: str = row["name"].strip()
            aliases_raw: str = row.get("aliases", "").strip()

            # canonical and display code: keep the full "SYMBOL.VN" form
            canonical_code = ts_code      # e.g. "VCB.VN"
            display_code = ts_code        # e.g. "VCB.VN"

            symbol = get_symbol(ts_code)  # e.g. "VCB"

            aliases = parse_aliases(aliases_raw, symbol)
            popularity = POPULARITY.get(symbol, 0)

            # StockIndexTuple — 10 positions
            tuple_row = [
                canonical_code,   # 0 canonicalCode
                display_code,     # 1 displayCode
                name,             # 2 nameZh  (Vietnamese name)
                "",               # 3 pinyinFull  (empty for VN)
                "",               # 4 pinyinAbbr  (empty for VN)
                aliases,          # 5 aliases
                "VN",             # 6 market
                "stock",          # 7 assetType
                True,             # 8 active
                popularity,       # 9 popularity
            ]
            tuples.append(tuple_row)

    print(f"Generated {len(tuples)} entries")

    # The loader's isCompressedFormat() check:
    #   Array.isArray(data) && Array.isArray(data[0]) && typeof data[0][0] === 'string'
    # So we output a bare top-level array of tuples (NOT wrapped in {version, items}).
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(tuples, fh, ensure_ascii=False, separators=(",", ":"))

    file_size = os.path.getsize(output_path)
    print(f"Wrote {output_path} ({file_size:,} bytes)")

    # --- Quick verification ---
    print("\n--- Verification sample ---")
    check_symbols = {"VCB", "FPT", "VNM", "VIC", "HPG"}
    found: dict[str, list] = {}
    for t in tuples:
        sym = get_symbol(t[0])
        if sym in check_symbols:
            found[sym] = t

    for sym in ["VCB", "FPT", "VNM"]:
        if sym in found:
            t = found[sym]
            print(
                f"  {sym}: canonical={t[0]!r}, display={t[1]!r}, "
                f"name={t[2]!r}, aliases={t[5]!r}, "
                f"market={t[6]!r}, assetType={t[7]!r}, "
                f"active={t[8]}, popularity={t[9]}"
            )
        else:
            print(f"  {sym}: NOT FOUND")

    print(f"\nTotal entries: {len(tuples)}")
    print(f"Tuple length check (first entry): {len(tuples[0])} fields (expected 10)")


if __name__ == "__main__":
    main()
