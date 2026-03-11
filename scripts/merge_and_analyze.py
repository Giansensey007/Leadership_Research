#!/usr/bin/env python3
"""
Merge leadership gender dataset with SEC filing index and produce
summary statistics and an analysis-ready dataset.

Expects the new schema from collect_sec_data.py:
  leadership_gender_data.csv: ticker, company, industry, filing_date,
    ceo_name, ceo_gender, total_neos, female_neos, male_neos,
    unknown_neos, pct_female_neos, neo_names_json
"""
import csv
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"


def load_csv(filename):
    filepath = DATA_DIR / filename
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def merge_datasets():
    """Merge leadership gender data with SEC filings index by ticker."""
    gender_data = load_csv("leadership_gender_data.csv")
    sec_data = load_csv("sec_filings_index.csv")

    sec_lookup = {row["ticker"]: row for row in sec_data}

    merged = []
    for row in gender_data:
        ticker = row["ticker"]
        sec_info = sec_lookup.get(ticker, {})
        merged_row = {**row}
        merged_row["sec_filing_date"] = sec_info.get("filing_date", "")
        merged_row["sec_filing_type"] = sec_info.get("filing_type", "")
        merged_row["data_source"] = "SEC EDGAR DEF 14A"
        merged.append(merged_row)

    return merged


def compute_summary_statistics(dataset):
    """Compute descriptive statistics for the dataset."""
    n = len(dataset)
    numeric_fields = [
        "total_neos", "female_neos", "male_neos",
        "unknown_neos", "pct_female_neos",
    ]

    stats = {}
    for field in numeric_fields:
        values = [float(row[field]) for row in dataset if row.get(field)]
        if values:
            values.sort()
            mean = sum(values) / len(values)
            median = values[len(values) // 2]
            stats[field] = {
                "n": len(values),
                "mean": round(mean, 2),
                "median": round(median, 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "sd": round(
                    (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5, 2
                ),
            }

    by_industry = defaultdict(list)
    for row in dataset:
        val = row.get("pct_female_neos")
        if val:
            by_industry[row["industry"]].append(float(val))

    industry_stats = {}
    for industry, values in by_industry.items():
        industry_stats[industry] = {
            "n": len(values),
            "mean_pct_female_neos": round(sum(values) / len(values), 1),
        }

    female_ceo_count = sum(
        1 for row in dataset if row.get("ceo_gender", "").lower() == "female"
    )

    return stats, industry_stats, female_ceo_count


def save_merged_csv(dataset, filename):
    filepath = DATA_DIR / filename
    if not dataset:
        return
    fieldnames = list(dataset[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dataset)
    print(f"Saved merged dataset: {filepath} ({len(dataset)} rows)")


def print_summary(stats, industry_stats, female_ceo_count, n):
    print("\n" + "=" * 65)
    print("DESCRIPTIVE STATISTICS  --  NEO Gender Composition")
    print("=" * 65)
    print(f"\nSample size: N = {n} S&P 500 companies\n")

    print(
        f"{'Variable':<25} {'Mean':>8} {'Median':>8} "
        f"{'SD':>8} {'Min':>8} {'Max':>8}"
    )
    print("-" * 75)
    for field, s in stats.items():
        label = field.replace("_", " ").title()
        print(
            f"{label:<25} {s['mean']:>8.1f} {s['median']:>8.1f} "
            f"{s['sd']:>8.1f} {s['min']:>8.1f} {s['max']:>8.1f}"
        )

    print(f"\nFemale CEOs: {female_ceo_count}/{n} ({female_ceo_count / n * 100:.0f}%)")

    print("\n" + "-" * 55)
    print("NEO GENDER DIVERSITY BY INDUSTRY")
    print("-" * 55)
    print(f"{'Industry':<20} {'N':>5} {'Mean % Female NEOs':>22}")
    print("-" * 55)
    for industry, s in sorted(
        industry_stats.items(), key=lambda x: -x[1]["mean_pct_female_neos"]
    ):
        print(f"{industry:<20} {s['n']:>5} {s['mean_pct_female_neos']:>21.1f}%")


if __name__ == "__main__":
    print("Merging datasets...")
    merged = merge_datasets()
    save_merged_csv(merged, "merged_leadership_data.csv")

    stats, industry_stats, ceo_count = compute_summary_statistics(merged)
    print_summary(stats, industry_stats, ceo_count, len(merged))
