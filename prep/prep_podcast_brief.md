# Women in S&P 500 Leadership — Full Project Brief

**Author:** Gian Senpinar · University of Zurich · Leadership Research (Spring 2026) · Dr. Ryan Miller

**Purpose of this document:** A complete, narrative walkthrough of the project — the research question, the data, the scraping pipeline, the gender-inference logic, current results, and limitations. Written so it reads naturally as a podcast script when fed to Google NotebookLM.

---

## 1. Elevator pitch

This project asks a simple question: **what firm-level factors predict women's representation in the top leadership of America's largest companies?** The sample is the S&P 500. Instead of running surveys, I use publicly mandated regulatory filings — specifically, the annual DEF 14A proxy statements every public company files with the SEC — as the data source. From each filing I extract the Named Executive Officers, infer their gender, and compute the share of women in each firm's top leadership team. I then test whether that share is predicted by whether the CEO is female and by what industry the firm operates in.

The project is **cross-sectional and observational**, not causal. It's a firm-level pilot built on a scalable, reproducible pipeline that could, in principle, be extended to the full Russell 3000 or to a time series.

---

## 2. Why this question matters

Women make up roughly half the U.S. workforce. Yet only about 9% of S&P 500 CEOs are women, and board representation sits near one-third. Decades of leadership research have focused on *individual-level* explanations — stereotype threat, work-family conflict, imposter phenomenon. These matter, but they leave something important on the table: **firms themselves vary enormously in how many women they promote to the top**, and that variation is observable, measurable, and potentially actionable.

This study shifts the unit of analysis from the individual woman to the firm. If we can identify which organizational characteristics correlate with higher female leadership representation, we generate empirical traction for interventions — things like board-composition policy, succession-planning reform, or industry-specific pipeline programs — that individual-level research cannot directly inform.

---

## 3. The research question and hypotheses

**RQ.** What firm-level factors predict women's representation in top leadership positions of S&P 500 firms?

**H1.** Board gender diversity (percentage of women on the board) is positively associated with the proportion of women in the C-suite.

**H2.** Firms with a female CEO or CFO have a higher proportion of women among their Named Executive Officers.

**H3.** Industry moderates the relationship between board diversity and C-suite diversity. The relationship is stronger in industries with historically lower female representation — energy, industrials, materials — because diverse boards have more slack to move the needle there.

> **Honest scope note.** The current dataset directly supports testing H2 and H3-as-main-effect. H1 requires a second layer of scraping — extracting the Director table from each DEF 14A — which is planned but not yet merged. I disclose this upfront rather than overclaiming the pilot's reach.

---

## 4. Research design

- **Design type:** Cross-sectional, observational, archival.
- **Unit of analysis:** Firm. One row equals one S&P 500 company.
- **Sample frame:** Current S&P 500 constituents (snapshot of the Wikipedia list).
- **N:** 500 firms targeted and written to the dataset. 340 rows contain non-zero NEO counts — the remaining 160 are parser misses, not missing filings, and are a coverage caveat the analysis must acknowledge.
- **Time window:** Each firm's most recent DEF 14A. In practice, filings range from 2024 through early 2026.
- **Why DEF 14A:** The Securities and Exchange Commission requires every U.S. public firm to file this annual proxy statement ahead of its shareholder meeting. SEC Regulation S-K, Item 402, specifically mandates disclosure of the Named Executive Officers — the principal executive officer, the principal financial officer, and the next three most highly compensated executives — along with their compensation. That means NEO identity is *auditable*, *legally standardized*, and *available for every firm in the sample*. No self-report bias. No recruitment problems.

---

## 5. Variables

**Dependent variable.** Percent female among Named Executive Officers, calculated as the number of female NEOs divided by total NEOs, multiplied by one hundred. Operationalized per firm from the latest DEF 14A's Summary Compensation Table.

**Key independent variables.**

- `ceo_gender` — binary. One if the principal executive officer listed in the proxy is female; zero otherwise. Inferred via the three-tier cascade described below.
- `industry` — categorical, using the eleven GICS sectors reported on Wikipedia (Information Technology, Financials, Industrials, Health Care, Consumer Discretionary, Consumer Staples, Utilities, Real Estate, Materials, Energy, Communication Services).

**Planned additions.**

- Percent women on the board — extracted from the same DEF 14A's Director nominees table. This becomes the direct test of H1.
- Log firm size (employees) and log revenue — for size controls.
- Fortune 500 rank — additional control.

**Moderator.** Industry, interacted with board diversity (once H1 becomes testable) or with CEO gender (in the current pilot specification).

---

## 6. Data sources

There are exactly two data sources, and they are both fully public.

**Source one: Wikipedia's "List of S&P 500 companies" page.** This provides the universe — ticker, legal name, and GICS sector for every current constituent. The script `scripts/fetch_sp500_constituents.py` fetches the page, parses the first table that contains a "Symbol" column, normalizes class-share tickers (for example, `BRK.B` becomes `BRK-B` because that's the format SEC EDGAR uses), and writes `data/sp500_constituents.csv` with approximately 503 rows.

**Source two: SEC EDGAR.** The official archive of every U.S. public company filing. I access it through the `edgartools` Python library, which handles authentication headers and structured parsing. For each ticker, I request the latest `DEF 14A` proxy statement. The library returns both a structured XBRL object (useful for the `named_executives` attribute, when populated) and a rendered Markdown version of the filing body (which is what the parser actually walks).

SEC guidelines require identifying yourself in requests. The scraper sets `set_identity("Leadership Research UZH research@uzh.ch")` and sleeps two seconds between tickers to stay polite. The full pull takes one to three hours end-to-end.

---

## 7. How the scraper actually works, step by step

Here's what `scripts/collect_sec_data.py` does, in the order it does it.

**Step one: load tickers.** Read `data/sp500_constituents.csv` into a list of `(ticker, company, industry)` tuples.

**Step two: fetch the latest DEF 14A per ticker.** For each ticker, call `Company(ticker).get_filings(form="DEF 14A")` and take the first (most recent) filing. From it, extract the structured proxy object and the rendered Markdown.

**Step three: extract NEO names from the Summary Compensation Table.** This is the trickiest piece, because every company's proxy is laid out slightly differently. The function `extract_neos_from_compensation_table` does the following:

1. Scans the Markdown for the string "summary compensation table" (case-insensitive).
2. Walks forward looking for a pipe-delimited Markdown table header row whose text contains the word "salary" — this anchors us to the correct table (not an unrelated compensation reference).
3. Once past the header, iterates over subsequent rows. For each row, the first cell is checked against a regular expression looking for a plausible person name — two to four capitalized words, optionally followed by a suffix like "Jr." or "III".
4. To distinguish names from other table content (section headers, footnotes, year labels), a `_is_plausible_name` helper rejects common non-name patterns — words like "chief", "executive", "officer", "the", "board", "committee", plus a long list of known table-boilerplate terms.
5. A name is only accepted if dollar-denominated compensation figures (a run of six or more digits with commas) appear either on the same line, the next line, or within the following three lines. This is what confirms we're reading a real compensation row.
6. The parser handles two common proxy layouts: one where the name and the dollar amounts appear on the same row (General Motors and Meta use this style), and one where the name is on one row and the numbers are on the next (Apple and Microsoft use this style). It also handles multi-line names, where a first name like "Sundar" appears on one row and "Pichai" wraps to the next.
7. Finally, if fewer than two NEOs are detected by the Markdown parser, the script falls back to the XBRL attribute `proxy.named_executives` as a safety net.

**Step four: build an honorific lookup across the entire filing.** Before gender-coding any NEO, the script scans the *full* Markdown of the filing for every occurrence of "Mr.", "Ms.", or "Mrs." followed by a word. It collects two sets of last names — one the filing treats as male-honorific, one as female-honorific. This harvests the firm's *own* gender coding of its executives from anywhere in the document.

**Step five: assign gender, count, and write.** For each NEO, apply the three-tier cascade (next section). Count totals, compute `pct_female_neos`, append a row to `leadership_gender_data.csv`, and log any ticker that failed to `_failed_tickers.json`. This last file enables incremental recovery: the next run can use `--retry-failed` to reprocess only the failures.

---

## 8. The gender-inference cascade

Because DEF 14A filings don't explicitly label executive gender, I infer it. The function `determine_gender(full_name, mr_set, ms_set)` runs three tiers in order.

**Tier one — honorific in the name itself.** If the name parses as "Mr. Cook" or "Ms. Adams", gender is assigned from the honorific. No inference needed.

**Tier two — last-name lookup against the filing-wide honorific sets.** This is the clever part. Even when the NEO is listed as "Tim Cook" without an honorific in the Summary Compensation Table, elsewhere in the filing the firm almost always refers to him as "Mr. Cook" — in the CD&A, the Pay vs Performance section, or director biographies. The honorific-lookup harvests those references, so when the NEO "Tim Cook" comes through, his last name is checked against the harvested Mr. and Ms./Mrs. sets. If it matches, gender is assigned from the firm's own usage. **This is the strongest signal in the whole pipeline because it is the firm's own language, not my guess.**

**Tier three — first-name heuristic.** If no honorific is available, the cleaned first name is checked against two curated lists in the script: `FEMALE_NAMES` and `MALE_NAMES`. These lists cover common American first names plus a long tail of executive-specific names observed in practice (Satya, Sundar, Jensen, Safra, Deirdre, Dhivya, and so on).

**Unknown.** Anything that doesn't match any tier is marked `unknown`, preserved in the data, and flagged for manual verification. These are not silently dropped. Currently about 15% of all NEO names are `unknown`, many of which are likely foreign first names or ambiguous cases.

**Why this is defensible.** Gender inference from names is standard practice in accounting and finance research — Adams and Ferreira 2009 for boards, Xu 2023 for executive promotions, and countless papers since use either name-based inference, external databases, or both. The honorific-lookup tier is an improvement on pure name-heuristics because it exploits the firm's own gendered pronouns embedded in the filing text. That moves a meaningful share of cases from "Gian's guess" to "the company's published language".

---

## 9. Output files

The pipeline produces four CSVs and one JSON, all under `data/`.

- `sp500_constituents.csv` — the universe of 503 tickers with company name and GICS sector.
- `leadership_gender_data.csv` — one row per firm with the extracted NEOs, gender counts, and percent female. The column `neo_names_json` preserves the full list of NEO name/gender pairs for auditability.
- `sec_filings_index.csv` — filing dates and types per firm. This is the audit trail: which filing did each row come from?
- `merged_leadership_data.csv` — the analysis-ready merged table that joins the gender data with the filing index.
- `_failed_tickers.json` — currently contains three tickers (BX, PSKY, Q) that failed collection and can be retried.

---

## 10. What the data actually shows

Descriptive statistics computed from the current `merged_leadership_data.csv`:

- **Sample size:** N = 500 firms written; 340 with non-zero NEO data.
- **Female CEOs:** 43 of 500, or approximately 9 percent.
- **Mean percent female NEOs per firm:** 10.4 percent (standard deviation 17.3, median 0, maximum 100).
- **Total NEO counts across all firms:** 1,184 male, 273 female, 264 unknown. Total 1,721 NEO observations.

**Ranking by industry — mean percent female NEOs, highest to lowest:**

| Industry (GICS)         | N firms | Mean % female NEOs |
|-------------------------|---------|--------------------|
| Consumer Discretionary  | 48      | 15.0%              |
| Health Care             | 60      | 14.6%              |
| Communication Services  | 22      | 13.7%              |
| Real Estate             | 31      | 11.3%              |
| Utilities               | 31      | 10.8%              |
| Information Technology  | 70      | 9.3%               |
| Industrials             | 79      | 9.0%               |
| Materials               | 26      | 8.9%               |
| Consumer Staples        | 36      | 8.8%               |
| Energy                  | 22      | 8.1%               |
| Financials              | 75      | 7.3%               |

The headline takeaway: **Consumer Discretionary leads at about fifteen percent, Financials trails at about seven percent.** That roughly twofold gap is the strongest descriptive signal in the dataset and foreshadows why industry is the most interesting moderator to test.

---

## 11. Analysis plan

All inferential analysis is in R.

1. **Descriptives and correlations.** Compute means, medians, standard deviations, and a correlation matrix across all numeric variables.
2. **Primary regression.** Ordinary least squares of `pct_female_neos` on a female-CEO dummy, GICS industry dummies, and controls (log firm size, log revenue). This tests H2 and, via the industry dummies, captures baseline industry differences.
3. **Interaction term.** Add `female_ceo × industry` (in the pilot version) or `board_diversity × industry` (once board data is merged) to test H3.
4. **Assumption checks.** Linearity via residual plots, normality via QQ plot, homoscedasticity via Breusch-Pagan, multicollinearity via variance inflation factors (target VIF under five).
5. **Robustness checks.** Re-specify the DV as a *count* of female NEOs using Poisson or negative-binomial regression. Drop firms with any `unknown_neos > 0`. Drop firms with `total_neos < 3` because parser coverage there is suspect. Run subgroup regressions by industry to check for specification fragility.

---

## 12. Limitations and caveats

Five real limitations, to own openly.

**First, parser coverage.** 160 of 500 firms returned zero NEOs. These are parser misses, not missing filings — every company in the S&P 500 files a DEF 14A. The parser handles two dominant table layouts but fails on edge cases: image-based PDFs, filings with embedded zero-width Unicode characters (UnitedHealth Group is one example), or atypical table structures. The analytic sample should therefore be the 340 firms with non-zero data, with a sensitivity check confirming the missing 160 don't differ systematically on observable characteristics.

**Second, binary gender inference.** The pipeline codes every NEO as male, female, or unknown. It cannot capture non-binary or self-identified gender identities. Results should be read as "presumed gender from filing text", not "self-reported gender".

**Third, cross-sectional snapshot.** One filing per firm means no within-firm change over time, no Granger-style causal analysis. Relationships are associations only. A time-series extension using multi-year filings is a natural next step.

**Fourth, selection on the S&P 500.** These are the largest, most successful U.S. public firms — survivors, in market-cap terms. Results don't generalize to small-cap, private, or non-U.S. firms. The question "what firms have more women in leadership?" conditional on being in the S&P 500 is narrower than "what firms in general do?".

**Fifth, unknown NEOs bias the DV downward if truly female.** About 15 percent of NEO names remain unknown. Because under-represented groups are often inferred less confidently by name-based heuristics (shorter lookup coverage, more foreign names in executive ranks), the unknown pool likely contains a non-random mix. I report `pct_female_neos` both with unknowns in the denominator and (as a sensitivity check) dropped from the denominator.

---

## 13. How the project evolved

The research proposal began with a manually-collected pilot of fifty firms across ten industries. That pilot used corporate governance reports scraped by hand and produced descriptive numbers that made it into the proposal: mean board size near twelve, mean percent women on board around thirty-three percent, mean percent women in the C-suite around eighteen percent, eight percent female CEOs in the pilot sample.

During implementation, two things shifted. First, **the data pipeline was automated** by replacing manual governance-report scraping with a full SEC EDGAR pull via `edgartools`. This made it feasible to scale from fifty firms to all five hundred. Second, **the dependent variable was narrowed** from "C-suite representation" (which is not standardized across firms — some report ten executives, some five, with no canonical definition) to "Named Executive Officer representation" (which is SEC-mandated and uniformly disclosed). The DV is now auditable against the filings.

These shifts made the paper more defensible methodologically but slightly narrower substantively. The tradeoff was intentional: a smaller, cleaner claim from 500 firms beats a larger, messier claim from 50.

---

## 14. Expected contributions

Three.

**One: a shift of focus.** Most prior leadership-and-gender research studies individual barriers. This project studies *firm enablers*, using observable firm-level data. The practical upshot is that interventions at the firm level — pipeline programs, board reforms, succession-planning audits — become testable with similar data.

**Two: a methodological contribution.** The pipeline is fully reproducible and uses only public, free data. Any researcher can rerun it, extend it to other indices (Russell 1000, FTSE 100), or add years. This matters because much existing work relies on proprietary datasets (Boardex, ISS) that limit replication.

**Three: an industry lens.** By treating industry not as a nuisance but as a moderator, the analysis aligns with the "leadership in context" program (Martin, Ono, Russo, and Thomas, 2023) — leadership is not uniform across sectors, and policy prescriptions shouldn't be either.

---

## 15. Anticipated questions from the advisor

**Why Named Executive Officers and not the C-suite?** Because NEO is the legally defined, uniformly disclosed category. Every firm reports the same set of officers to the SEC, so the measure is comparable across all 500 firms.

**How confident are you in the gender inference?** The strongest tier — filing-wide honorific lookup — is a near-certain signal because it uses the firm's own gendered language. The weakest tier — first-name heuristic — introduces noise. Remaining unknowns (around 15 percent) are preserved in the data and treated in sensitivity analysis, not dropped silently.

**Why is the coverage only 340 out of 500?** Because proxy filings vary enormously in layout. The parser handles two dominant formats plus an XBRL fallback; remaining misses are filings with image-based tables, embedded non-printing characters, or atypical structures. This is a parser problem, not a data problem, and it's the most tractable improvement axis for the final version.

**Endogeneity?** Yes — firms with female CEOs differ systematically on industry, culture, and prior gender-diversity trajectories. The analysis is observational. Industry fixed effects and size controls help; a causal claim would require either a natural experiment or an instrument, both beyond the paper's scope.

**What's the next step if this works?** Merge in board-composition data (directly available from the same DEF 14A Director table) to test H1. Then expand to multi-year panel to test within-firm change. Then potentially extend to Russell 3000 for external validity on smaller firms.

---

## 16. Key phrases and numbers to remember

- One row per firm; 500 processed; 340 analyzable.
- Data source: SEC EDGAR DEF 14A proxy filings, accessed via `edgartools`.
- DV: percent female among NEOs.
- IV: CEO gender (binary), industry (GICS, eleven categories).
- 43 female CEOs in the sample (9 percent).
- Mean percent female NEOs: 10.4 percent.
- Industry spread: Consumer Discretionary leads at 15.0 percent; Financials trails at 7.3 percent.
- Analysis: OLS with industry fixed effects; robustness with Poisson count model and drop-unknown.
- Contribution: firm-level lens, reproducible public-data pipeline, industry moderator.

---

*End of brief.*
