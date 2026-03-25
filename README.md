# Leadership Research — DEF 14A NEO gender composition

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Data collection (full S&P 500)

1. **Optional — refresh S&P 500 list** (Wikipedia snapshot; needs network + User-Agent):

   ```bash
   python scripts/fetch_sp500_constituents.py
   ```

   Writes `data/sp500_constituents.csv` (~503 rows).

2. **Collect DEF 14A NEO data** (long run: ~1–3+ hours; respects SEC-friendly delay between tickers):

   ```bash
   python scripts/collect_sec_data.py
   ```

   Options:

   - `--constituents PATH` — custom CSV (`ticker`, `company`, `industry`)
   - `--limit N` — first N tickers only (smoke tests)
   - `--retry-failed` — retry tickers in `data/_failed_tickers.json` (uses full constituents for metadata; `--limit` ignored)

3. **Merge and summary stats**:

   ```bash
   python scripts/merge_and_analyze.py
   ```

## Outputs

| File | Description |
|------|-------------|
| `data/sp500_constituents.csv` | S&P 500 tickers + GICS sector |
| `data/leadership_gender_data.csv` | NEO gender counts per firm |
| `data/sec_filings_index.csv` | Filing index |
| `data/merged_leadership_data.csv` | Merged analysis-ready table |

Not every firm may return non-zero NEO rows (filing layout / parser limits); treat as a coverage caveat in analysis.

**Constituent list:** `sp500_constituents.csv` is a Wikipedia snapshot. If a ticker fails collection (`data/_failed_tickers.json`), verify the SEC trading symbol (e.g. Marsh McLennan is `MMC`, not `MRSH`). Some issuers may have no `DEF 14A` in EDGAR under the expected ticker, or symbols may be Wikipedia errors—correct the CSV and re-run or collect manually.
