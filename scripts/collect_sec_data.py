#!/usr/bin/env python3
"""
Collect Named Executive Officer (NEO) gender composition data from SEC EDGAR
DEF 14A proxy filings for S&P 500 companies.

Gender determination uses a 3-tier cascade:
  1. Honorifics (Mr./Ms./Mrs.) extracted from the filing text itself
  2. First-name heuristic against curated name lists
  3. Marked 'unknown' for manual verification

Data source: SEC EDGAR (https://www.sec.gov/edgar/)

Universe: default `data/sp500_constituents.csv` (full S&P 500). Not every firm
may yield non-zero NEO counts due to filing layout / parser limits; treat
coverage as an analysis caveat.

Refresh constituents: `python scripts/fetch_sp500_constituents.py`
"""
import argparse
import json
import csv
import re
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_CONSTITUENTS_CSV = DATA_DIR / "sp500_constituents.csv"


def load_companies(csv_path):
    """
    Load (ticker, company_name, industry) from CSV with columns:
    ticker, company, industry
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Constituents file not found: {path}")

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("ticker") or "").strip()
            c = (row.get("company") or "").strip()
            i = (row.get("industry") or "").strip()
            if not t:
                continue
            rows.append((t, c, i))
    if not rows:
        raise ValueError(f"No tickers loaded from {path}")
    return rows

FEMALE_NAMES = {
    "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth", "susan",
    "jessica", "sarah", "karen", "lisa", "nancy", "betty", "margaret", "sandra",
    "ashley", "dorothy", "kimberly", "emily", "donna", "michelle", "carol",
    "amanda", "melissa", "deborah", "stephanie", "rebecca", "sharon", "laura",
    "cynthia", "kathleen", "amy", "angela", "shirley", "anna", "brenda", "pamela",
    "emma", "nicole", "helen", "samantha", "katherine", "christine", "debra",
    "rachel", "carolyn", "janet", "catherine", "maria", "heather", "diane",
    "ruth", "julie", "olivia", "joyce", "virginia", "victoria", "kelly",
    "lauren", "christina", "joan", "evelyn", "judith", "megan", "andrea",
    "cheryl", "hannah", "jacqueline", "martha", "gloria", "teresa", "ann",
    "sara", "madison", "frances", "kathryn", "janice", "jean", "abigail",
    "alice", "judy", "sophia", "grace", "denise", "amber", "doris",
    "marilyn", "danielle", "beverly", "isabella", "theresa", "diana", "natalie",
    "brittany", "charlotte", "marie", "kayla", "alexis", "lori",
    "deirdre", "isabel", "helle", "kate", "meg",
    "safra", "robin", "gail", "faiza", "phebe", "sue", "stacy",
    "rosalind", "beth", "lynn", "irene", "tracy", "toni", "pam",
    "teri", "liane", "kristin", "colleen", "claudia", "renee", "adriana",
    "joanne", "valerie", "michele", "dhivya", "kristen",
}

MALE_NAMES = {
    "james", "robert", "john", "michael", "david", "william", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew", "anthony",
    "mark", "donald", "steven", "paul", "andrew", "joshua", "kenneth",
    "kevin", "brian", "george", "timothy", "ronald", "edward", "jason",
    "jeffrey", "ryan", "jacob", "gary", "nicholas", "eric", "jonathan",
    "stephen", "larry", "justin", "scott", "brandon", "benjamin", "samuel",
    "raymond", "gregory", "frank", "alexander", "patrick", "peter", "jack",
    "dennis", "jerry", "tyler", "aaron", "jose", "nathan", "henry",
    "douglas", "adam", "carl", "roger", "keith", "jeremy", "terry",
    "sean", "ralph", "albert", "arthur", "lawrence", "jesse", "bruce",
    "gabriel", "joe", "logan", "alan", "juan", "russell", "louis",
    "philip", "harry", "vincent", "bobby", "dylan", "randy", "eugene",
    "howard", "wayne", "todd", "billy", "steve", "jensen", "satya",
    "tim", "sundar", "andy", "jamie", "reed", "bob", "doug",
    "jim", "ted", "chuck", "al", "jeff", "mike", "tom", "bill", "dan",
    "greg", "ray", "craig", "brad", "rob", "chris", "alex", "matt",
    "nick", "rick", "joel", "darren", "lance", "neil", "ivan",
    "rory", "aneel", "wesley", "alfred", "devin",
}


def infer_gender(first_name):
    """Tier-2: heuristic gender inference from first name."""
    name_lower = first_name.lower().strip()
    if name_lower in FEMALE_NAMES:
        return "female"
    if name_lower in MALE_NAMES:
        return "male"
    return "unknown"


def build_honorific_lookup(markdown_text):
    """Tier-1: extract Mr./Ms./Mrs. last-name sets from the full proxy text."""
    mr_lastnames = set()
    ms_lastnames = set()
    for line in markdown_text.split("\n"):
        for m in re.finditer(r"Mr\.\s+(\w+)", line):
            mr_lastnames.add(m.group(1).lower())
        for m in re.finditer(r"(?:Ms|Mrs)\.\s+(\w+)", line):
            ms_lastnames.add(m.group(1).lower())
    return mr_lastnames, ms_lastnames


def determine_gender(full_name, mr_set, ms_set):
    """3-tier gender cascade: honorific prefix > last-name lookup > first-name heuristic."""
    parts = full_name.strip().split()
    if not parts:
        return "unknown"

    first = parts[0]
    if first in ("Mr.", "Mr"):
        return "male"
    if first in ("Ms.", "Ms", "Mrs.", "Mrs"):
        return "female"

    last = parts[-1].lower()
    if last in mr_set:
        return "male"
    if last in ms_set:
        return "female"

    clean_first = re.sub(r"[^a-zA-Z]", "", parts[0])
    return infer_gender(clean_first)


def _is_plausible_name(text):
    """Check if text looks like a person name (2-4 capitalized words, no common non-name patterns)."""
    skip = {
        "chief", "executive", "officer", "president", "vice", "senior",
        "director", "chair", "advisor", "former", "principal", "position",
        "name", "year", "salary", "bonus", "stock", "total", "fiscal",
        "grants", "outstanding", "equity", "awards", "option", "exercises",
        "proposal", "item", "annual", "cash", "incentive", "compensation",
        "the", "our", "board", "committee", "type", "this", "about",
        "information", "vesting", "offset", "increasing", "election",
        "appendix", "annex", "exhibit", "quorum", "procedure", "ratification",
        "community", "engagement", "talent", "morgan", "blackrock", "vanguard",
        "questions", "shareholder", "directions", "path", "sustainability",
        "operations", "capital", "employed", "flow", "modified", "note",
        "ernst", "important", "voting", "stockholder", "grant", "date",
        "vesting", "all", "back", "contents", "section",
    }
    words = text.strip().split()
    if len(words) < 2:
        return False
    first_word = words[0].lower().rstrip(".")
    if first_word in skip:
        return False
    if not words[0][0].isupper():
        return False
    return True


def extract_neos_from_compensation_table(markdown_text):
    """
    Parse the Summary Compensation Table to extract NEO full names.

    Handles two common formats:
      A) Name and dollar amounts on the SAME row (GM, META style)
      B) Name on one row, dollar amounts on the NEXT row (AAPL, MSFT style)
    """
    # Strip zero-width spaces that some filings (e.g., UNH) embed everywhere
    clean_text = markdown_text.replace("\u200b", "").replace("\u2007", " ")
    lines = clean_text.split("\n")
    neos = []

    table_start = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "summary compensation table" not in low:
            continue
        # Find a pipe-delimited header row whose own multi-line span
        # actually contains "salary" (not from an unrelated context).
        header_line = None
        for j in range(i + 1, min(len(lines), i + 15)):
            if not lines[j].startswith("|"):
                continue
            # Collect this row and its continuation lines
            row_text = lines[j]
            for c in range(j + 1, min(len(lines), j + 12)):
                if lines[c].startswith(" ") or lines[c].startswith("|"):
                    row_text += " " + lines[c]
                else:
                    break
            if "salary" in row_text.lower():
                header_line = j
                break
        if header_line is None:
            continue
        # Skip the header and all its continuation lines, plus separator
        # rows, to reach the first data row.
        past_header = header_line + 1
        for k in range(past_header, min(len(lines), past_header + 15)):
            ln = lines[k]
            if ln.startswith(" ") and not ln.strip() == "":
                continue
            if ln.strip() == "":
                continue
            if ln.startswith("|"):
                if re.match(r"^\|[\s:\-|]+$", ln):
                    continue
                rl = ln.lower()
                if "salary" in rl or "name" in rl and "position" in rl:
                    continue
                table_start = k
                break
        if table_start:
            break

    if table_start is None:
        return neos

    NAME_RE = re.compile(
        r"([A-Z][a-zA-Z.\-\'\u2019]+(?:\s+[A-Z][a-zA-Z.\-\'\u2019]*)*"
        r"(?:,\s*(?:Jr\.|Sr\.|III|IV|II))?)"
    )

    gap = 0
    for i in range(table_start, min(len(lines), table_start + 250)):
        line = lines[i]

        if not line.startswith("|"):
            if line.strip() == "" or re.match(r"^\(\d\)", line.strip()):
                gap += 1
                if gap > 4:
                    break
                continue
            if line.startswith(" "):
                continue
            break

        gap = 0

        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not cells:
            continue
        first_cell = cells[0]

        if re.match(r"^\d{4}$", first_cell):
            continue
        if re.match(r"^[\d,\$\.\-\s\u2014]+$", first_cell):
            continue
        if first_cell.strip() == "":
            continue

        # Handle multi-line names: if first_cell is a single word
        # (e.g., "Sundar"), look at the next line for the last name.
        full_first_cell = first_cell
        words = first_cell.strip().split()
        if len(words) == 1 and words[0][0].isupper() and i + 1 < len(lines):
            next_ln = lines[i + 1].strip()
            if next_ln and not next_ln.startswith("|"):
                # Grab continuation text
                cont_words = next_ln.split()
                if cont_words and cont_words[0][0].isupper():
                    full_first_cell = first_cell.strip() + " " + next_ln.strip()

        has_dollars = bool(re.search(r"[\d,]{6,}", line))

        m = NAME_RE.match(full_first_cell)
        if not m:
            continue

        candidate = m.group(1).strip().rstrip(",")
        if len(candidate) <= 3:
            continue

        # Check dollars on current line, next line, or 2 lines down
        # (handles multi-line cell where name and data are split)
        next2 = " ".join(
            lines[j] for j in range(i, min(len(lines), i + 4))
        )
        has_dollars_nearby = bool(re.search(r"[\d,]{6,}", next2))

        if has_dollars_nearby and _is_plausible_name(candidate):
            if candidate not in neos:
                neos.append(candidate)

    return neos


def extract_neos_from_xbrl(proxy):
    """Fallback: try the XBRL named_executives attribute."""
    try:
        raw = proxy.named_executives or []
    except Exception:
        return []

    seen = set()
    names = []
    for neo in raw:
        name = neo.name.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def extract_proxy_data(ticker, company_name, industry):
    """
    Fetch the latest DEF 14A and extract NEO composition + gender data.
    Returns a dict row for the CSV, or None on failure.
    """
    from edgar import Company

    company = Company(ticker)
    filings = company.get_filings(form="DEF 14A")
    if not filings or len(filings) == 0:
        return None

    latest = filings[0]
    filing_date = str(latest.filing_date) if hasattr(latest, "filing_date") else ""

    proxy = latest.obj()
    md = latest.markdown()

    mr_set, ms_set = build_honorific_lookup(md)

    peo_name = proxy.peo_name or ""
    peo_gender = determine_gender(peo_name, mr_set, ms_set)

    neos = extract_neos_from_compensation_table(md)

    if len(neos) < 2:
        xbrl_neos = extract_neos_from_xbrl(proxy)
        if len(xbrl_neos) > len(neos):
            neos = xbrl_neos

    neo_details = []
    for name in neos:
        gender = determine_gender(name, mr_set, ms_set)
        neo_details.append({"name": name, "gender": gender})

    total = len(neo_details)
    female = sum(1 for n in neo_details if n["gender"] == "female")
    male = sum(1 for n in neo_details if n["gender"] == "male")
    unknown = sum(1 for n in neo_details if n["gender"] == "unknown")
    pct_female = round(female / total * 100, 1) if total > 0 else 0.0

    return {
        "ticker": ticker,
        "company": company_name,
        "industry": industry,
        "filing_date": filing_date,
        "ceo_name": peo_name,
        "ceo_gender": peo_gender,
        "total_neos": total,
        "female_neos": female,
        "male_neos": male,
        "unknown_neos": unknown,
        "pct_female_neos": pct_female,
        "neo_names_json": json.dumps(neo_details, ensure_ascii=False),
    }


def collect_all(retry_failed_only=False, companies=None):
    """
    Run extraction for all companies. Returns (rows, sec_index, failed).

    companies: list of (ticker, company_name, industry); required unless
    retry_failed_only loads an empty set (then returns empty results).
    """
    from edgar import set_identity

    set_identity("Leadership Research UZH research@uzh.ch")

    failed_file = DATA_DIR / "_failed_tickers.json"

    if companies is None:
        companies = []

    ticker_meta = {t: (t, n, i) for t, n, i in companies}

    if retry_failed_only and failed_file.exists():
        with open(failed_file) as f:
            retry_set = set(json.load(f))
        targets = [
            ticker_meta[t] for t in sorted(retry_set) if t in ticker_meta
        ]
        missing = retry_set - set(ticker_meta.keys())
        if missing:
            print(
                f"Warning: {len(missing)} failed tickers not in constituents "
                f"(skipped): {sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}"
            )
        print(f"Retrying {len(targets)} previously failed tickers...")
    else:
        targets = list(companies)

    rows = []
    failed = []
    sec_index = []

    for idx, (ticker, name, industry) in enumerate(targets, 1):
        print(f"[{idx}/{len(targets)}] {ticker} ({name})...", end=" ", flush=True)
        try:
            row = extract_proxy_data(ticker, name, industry)
            if row:
                rows.append(row)
                sec_index.append({
                    "ticker": ticker,
                    "company_name": name,
                    "industry": industry,
                    "filing_date": row["filing_date"],
                    "filing_type": "DEF 14A",
                    "source": "SEC EDGAR",
                })
                neos = json.loads(row["neo_names_json"])
                unknowns = [n["name"] for n in neos if n["gender"] == "unknown"]
                status = (
                    f"OK  NEOs={row['total_neos']}  "
                    f"F={row['female_neos']}  M={row['male_neos']}"
                )
                if unknowns:
                    status += f"  unknown=[{', '.join(unknowns)}]"
                print(status)
            else:
                failed.append(ticker)
                print("SKIP (no filing)")
        except Exception as e:
            failed.append(ticker)
            print(f"FAIL ({e})")

        if idx < len(targets):
            time.sleep(2)

    with open(failed_file, "w") as f:
        json.dump(failed, f)

    return rows, sec_index, failed


def save_to_csv(dataset, filename):
    """Save dataset to CSV."""
    filepath = DATA_DIR / filename
    if not dataset:
        print(f"No data to save for {filename}.")
        return
    fieldnames = list(dataset[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dataset)
    print(f"Saved {len(dataset)} rows -> {filepath}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Collect NEO gender data from DEF 14A filings."
    )
    p.add_argument(
        "--constituents",
        type=Path,
        default=DEFAULT_CONSTITUENTS_CSV,
        help=f"path to ticker CSV (default: {DEFAULT_CONSTITUENTS_CSV})",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="process only first N tickers (after load; for smoke tests)",
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help="retry tickers listed in data/_failed_tickers.json only",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()

    print("=" * 65)
    print("SEC EDGAR DEF 14A -- NEO Gender Composition Collector")
    print("=" * 65)

    companies = load_companies(args.constituents)
    if args.retry_failed:
        print(
            f"Loaded {len(companies)} tickers from {args.constituents} "
            "(full list; --limit ignored for retry metadata)."
        )
    elif args.limit is not None and args.limit > 0:
        companies = companies[: args.limit]
        print(f"Using first {len(companies)} tickers (--limit).")
    else:
        print(f"Loaded {len(companies)} tickers from {args.constituents}.")

    rows, sec_index, failed = collect_all(
        retry_failed_only=args.retry_failed,
        companies=companies,
    )

    save_to_csv(rows, "leadership_gender_data.csv")
    save_to_csv(sec_index, "sec_filings_index.csv")

    print(f"\nResults: {len(rows)} succeeded, {len(failed)} failed")
    if failed:
        print(f"Failed tickers: {failed}")
        print("Run with --retry-failed to retry only these.")

    print("\nDone.")
