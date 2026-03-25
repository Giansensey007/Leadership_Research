#!/usr/bin/env python3
"""
Download S&P 500 constituent list from Wikipedia and write data/sp500_constituents.csv.

Columns: ticker, company, industry (GICS Sector from Wikipedia).

Run once to refresh the snapshot (e.g. after index rebalancing).
"""
import csv
import io
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
WIKI_URL = (
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
)
USER_AGENT = (
    "LeadershipResearch/1.0 (academic research; contact: research@example.invalid)"
)


def _fetch_wiki_html():
    req = Request(WIKI_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_sp500_table():
    """Return DataFrame with Symbol, Security, GICS Sector."""
    html = _fetch_wiki_html()
    tables = pd.read_html(io.StringIO(html), match="Symbol")
    if not tables:
        raise RuntimeError("No matching table found on Wikipedia")
    df = tables[0]
    # Expected columns include Symbol, Security, GICS Sector
    col_map = {}
    for c in df.columns:
        s = str(c).strip()
        if s == "Symbol":
            col_map[c] = "ticker"
        elif "Security" in s or s == "Security":
            col_map[c] = "company"
        elif "GICS Sector" in s or s == "GICS Sector":
            col_map[c] = "industry"
    if "ticker" not in col_map.values():
        # Fallback: first column often Symbol
        first = df.columns[0]
        col_map = {first: "ticker", df.columns[1]: "company"}
        if len(df.columns) > 2:
            col_map[df.columns[2]] = "industry"
    df = df.rename(columns=col_map)
    need = ["ticker", "company", "industry"]
    for n in need:
        if n not in df.columns:
            raise RuntimeError(f"Missing column {n}; got {list(df.columns)}")
    out = df[need].copy()
    # Normalize tickers: Wikipedia may use dots for class shares (BRK.B)
    out["ticker"] = (
        out["ticker"]
        .astype(str)
        .str.strip()
        .str.replace(".", "-", regex=False)
    )
    out["company"] = out["company"].astype(str).str.strip()
    out["industry"] = out["industry"].astype(str).str.strip()
    out = out.drop_duplicates(subset=["ticker"], keep="first")
    out = out.sort_values("ticker").reset_index(drop=True)
    return out


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "sp500_constituents.csv"
    df = fetch_sp500_table()
    df.to_csv(out_path, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"Wrote {len(df)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
