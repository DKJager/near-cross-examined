# NEAR, Cross-Examined

**Judge's 5-minute path**

1. `pip install pytest && make verify` (in a virtual environment, see Install): prints the VERIFY OK and DOCS OK lines.
2. Open `docs/index.html` (or the hosted page, see Disclosures): the thesis, three numbers, 13 charts, each with its method.
3. Read the section "The track's question" in `THESIS.md`.
4. `python3 bq_fetch.py` prints the three SQL queries for the NEAR BigQuery public dataset; their results, run once on 13 Nov 2026, are in `data/bq_*.csv`.

**An investment thesis on NEAR that four AI models from four makers argued over claim by claim, against on-chain numbers they could not change.**

Built for the NEAR Hackathon (Nov 2026), Track 02 Investment Thesis and Track 13 Open Innovation. By 3Dogs Nexus (https://3dogs.ai). Built on 3Dogs wisdom of crowds, three reviewers for speed, five when one stands alone. This entry uses a four-judge panel.

## The thesis in one line

NEAR is a one-product network priced for that product to keep compounding. (Read the full thesis and evidence in [THESIS.md](THESIS.md).)

## Why it matters

- **For someone deciding about NEAR:** it separates what the data supports (app fees through NEAR Intents are large and growing; daily active accounts and transactions are far below a year ago) from what it does not (neither Intents fees nor price leads account activity over 79 weeks).
- **For builders and analysts:** it shows how concentrated the economy is (87% of the last 30 days' app fees came through NEAR Intents) and gives six dated tripwires that say what would prove the thesis wrong.
- **For anyone with their own claim:** the method is reusable. Add a claim, re-run the panel, keep every number traceable to a committed file.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install pytest
make verify
```

Use `make verify PY=/path/to/python` to choose the interpreter.

## Do X, see Y

- **`make verify`** — no API key, no network. In a fresh clone (the source files are not shipped, see below) it runs offline: it checks `out/metrics.json` and `out/panel.json` against the hashes recorded when they were built (`data/DERIVED_SHA256SUMS`), rebuilds the BigQuery numbers from the shipped `data/bq_*.csv`, checks the judges' citations, the hashes of the shipped files, and the three documents, and scores the tripwires. Expected output includes `VERIFY OK (offline): ...` and `DOCS OK: ...`. If you have downloaded the source files (`python3 fetch.py`), the same command rebuilds all 954 numbers and prints `VERIFY OK: 954 numbers rebuilt from the full local data`.
- **What offline mode proves, and what it does not.** It proves that the numbers in `out/metrics.json` and the citations are the ones recorded when they were built, and that the BigQuery numbers rebuild from the shipped CSVs. It does not rebuild the numbers that come from the four unshipped sources, and a hash list is not a signature: anyone who can edit the repository can edit the hashes too (git history is the audit trail). To check those numbers against the sources, run `make verify-online`, or `python3 fetch.py` and then `make verify`, which checks each file against its recorded hash and rebuilds all 954.
- **`make verify-online`** (`python3 verify_online.py`) — needs the internet, no key, about two minutes: downloads every source again for the same dates into `data_online/`, rebuilds all the numbers and compares them with `out/metrics.json`. Sources revise recent days, so it allows 2% (or 0.02 for numbers near zero) and lists the raw files that changed since the recorded fetch. The NEAR Intents Explorer sample needs a partner key (`INTENTS_JWT`); without it those numbers are skipped and the count says so.
- **`cd data && sha256sum -c --ignore-missing SHA256SUMS`** — check every file you have against its recorded hash.
- **Read [THESIS.md](THESIS.md)** — the full investment thesis with all evidence and counter-evidence.
- **Read [TRIPWIRES.md](TRIPWIRES.md)** — the conditions that would prove the thesis wrong, and three dated forecasts.
- **Read [WEAKNESSES.md](WEAKNESSES.md)** — every known weak point with its source.
- **Open `docs/index.html`** — the interactive dashboard with 12 key performance indicators and 13 charts.

## Use it on your own claim

Add a claim to `CLAIMS` in `panel.py`, then run `make panel page`. Add a dated test to `tripwires.json` to check it on a fixed schedule.

## What it does

1. **Fetch**: downloads daily chain data from NearBlocks, fees and revenue from DefiLlama, prices from CoinGecko, and NEAR Intents swap data from the Intents Explorer.
2. **Export**: produces `data/nearblocks_daily.csv`, `data/intents_sundays.csv`, and `data/SHA256SUMS`, which lists every data file with its SHA-256 hash as fetched (the source files are hashed but not shipped).
3. **Compute**: derives 954 metrics from the raw data.
4. **Cross-examine**: 20 claims, including one planted false claim as a control, are judged by four AI models from four different makers. Each model cites only metric paths; the numbers are filled in by code.
5. **Show**: a dashboard of tiles, charts, tripwires, and the panel's verdicts.

**Lead-lag test (the track's question).** Is NEAR Intents activity a better leading indicator of network usage than the NEAR price? We measured how well changes in fees or price predict later changes in active accounts, using a standard correlation test (Pearson correlation between the weekly % change of the indicator and the weekly % change of daily active accounts, with the indicator leading by 0, 4, 8 and 12 weeks, over 79 weeks). n is the number of weekly pairs used; the 95% interval and p-value use the Fisher z transform.

| Indicator | Lead (weeks) | r | n | 95% interval | p |
|---|---|---|---|---|---|
| Intents fees | 0 | -0.02 | 78 | -0.24 to +0.21 | 0.90 |
| Price | 0 | -0.20 | 51 | -0.45 to +0.07 | 0.15 |
| Intents fees | 4 | +0.01 | 74 | -0.22 to +0.23 | 0.96 |
| Price | 4 | +0.03 | 47 | -0.26 to +0.32 | 0.82 |
| Intents fees | 8 | -0.01 | 70 | -0.25 to +0.22 | 0.93 |
| Price | 8 | -0.08 | 43 | -0.37 to +0.22 | 0.60 |
| Intents fees | 12 | -0.02 | 66 | -0.26 to +0.22 | 0.87 |
| Price | 12 | +0.02 | 39 | -0.30 to +0.33 | 0.90 |

Every interval includes zero, so none of these correlations can be read as a leading indicator; neither Intents fees nor price leads. The r, n, interval and p values are all in `out/metrics.json` (`leadlag.*`), and `make verify` rebuilds them when the source files are present (`python3 fetch.py`), or `make verify-online` from a fresh download; a test checks that this table equals those values.

**What is committed, and why (terms read 13 Nov 2026).** Three of the five sources bar republishing or redistribution, or say nothing clear, so this repository ships only what is ours or unrestricted:
- Shipped: the three BigQuery result files (`data/bq_*.csv`, 365 daily values each, results of our own queries on `bigquery-public-data.crypto_near_mainnet_us`; neither Google's public-dataset page nor NEAR's docs states a licence or an attribution rule, NEAR pays the storage and Google charges for queries), the derived numbers (`out/metrics.json`, aggregates computed by this code), and the hashes.
- Not shipped, but hashed as fetched (dates in `data/MANIFEST.json`, hashes in `data/SHA256SUMS`, list in `data/RAW_NOT_COMMITTED.txt`): DefiLlama (its site terms limit use to personal, non-commercial purposes and bar mirroring or republishing its data without permission), CoinGecko (its API terms bar redistribution, discourage storing data and require the notice "Powered by CoinGecko"), NearBlocks (its free plan is listed for personal use with attribution; no redistribution terms found) and the NEAR Intents Explorer (no terms for the Explorer found; the 1Click API terms cap retention of API data at 24 hours). Where terms are unclear we did the same as where they bar it.
- To get them: `python3 fetch.py` downloads the same series for the same dates (CoinGecko's public API serves only the last 365 days, so a later fetch starts a few days later). Sources revise recent days, so a re-fetch can differ slightly from the recorded hashes; this means verification is not fully reproducible for recent data points and may affect the reliability of time-sensitive metrics. The full copy is kept by the authors for their own checks.
- Attribution: data from NearBlocks, DefiLlama, the NEAR Intents Explorer, CoinGecko ("Powered by CoinGecko") and the Google BigQuery public dataset for NEAR. This entry is non-commercial research. Earlier commits of this repository, before this change, contained some of these files; ask us to remove a provider's data and we will.

**Other windows, and what is unknown.** The headline year-on-year figures compare 30-day averages. The file out/metrics.json (key windows) also holds the 30/90/180/365/730-day comparisons for active accounts and transactions, and app fees for the last 30, 90 and 365 days against the period before; THESIS.md prints them. The most recent 30 days of app fees fell against the 30 before. The cause of the 2 Apr 2026 one-day step in transactions is unknown; no source we found names it. App fees are what DefiLlama tracks for apps on NEAR, and the multiple against chain gas fees compares two different flows, so it shows scale only.

**BigQuery: run once, 13 Nov 2026.** The three queries in sql/ were run in the owner's own Google console on 13 Nov 2026 on bigquery-public-data.crypto_near_mainnet_us (window 2025-11-10 to 2026-11-09, on-demand), results committed as data/bq_*.csv with SHA-256 hashes; the active-account and transaction series equal NearBlocks' on all 365 days (same chain data, so this shows reproduction, not independence); the contract-usage series uses a different definition from NearBlocks and is not cross-checked; `python3 bq_fetch.py --run` re-runs them with your own Google credentials; `--from-fixture DIR` loads recorded CSVs. No claim about staking.

## Data sources

None of these files is shipped except where noted in "What is committed, and why"; `python3 fetch.py` downloads them.

| File | Provider | URL | What |
|---|---|---|---|
| charts_raw.json | NearBlocks | https://api.nearblocks.io/v1/charts | Daily chain activity (accounts, transactions, fees, supply) |
| coingecko_near.json | CoinGecko | https://api.coingecko.com/api/v3/coins/near/market_chart/range | Historical NEAR prices |
| intents_days.json | NEAR Intents Explorer | https://explorer.near-intents.org/api/v0/transactions | Sunday sample of swap counts and volumes |
| llama_dex_near.json | DefiLlama | https://api.llama.fi/overview/dexes/near | DEX volumes on NEAR |
| llama_fees_near.json | DefiLlama | https://api.llama.fi/overview/fees/near | App fees on NEAR |
| llama_gas_fees_near.json | DefiLlama | https://api.llama.fi/summary/fees/near | Chain gas fees (cross-check with NearBlocks) |
| llama_holders_revenue_near.json | DefiLlama | https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue | NEAR Intents revenue (buyback source) |
| llama_intents_fees.json | DefiLlama | https://api.llama.fi/overview/fees/near-intents | NEAR Intents fees (all Intents protocols) |
| llama_intents_revenue.json | DefiLlama | https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue | NEAR's kept revenue from Intents |
| llama_revenue_near.json | DefiLlama | https://api.llama.fi/summary/fees/near | Total chain fees and revenue |
| llama_stablecoins_near.json | DefiLlama | https://api.llama.fi/stablecoins/near | Stablecoin supply on NEAR |
| llama_tvl_near.json | DefiLlama | https://api.llama.fi/v2/historicalChainTvl/Near | Total value locked on NEAR |
| stats_raw.json | NearBlocks | https://api.nearblocks.io/v1/stats | Additional chain statistics |

## Weak points

Every known weak point, with its source, is in [WEAKNESSES.md](WEAKNESSES.md). The short version:
- Account and transaction counts come from one provider (NearBlocks).
- NEAR Intents swap counts are sampled one Sunday a week, not every day.
- Staking is not measured.

## Model retirement, 9 Nov 2026

On 9 Nov 2026 Nebius retired two of the original judge models from serverless use ([Nebius notice](https://docs.tokenfactory.nebius.com/november-2026-deprecation-notice)). `panel.py` now defaults to the recommended replacements, `deepseek-ai/DeepSeek-V4.1-Flash-1017` and `Qwen/Qwen3-30B-A3B-Instruct-2507`, and the published `out/panel.json` (20 claims, data as of 2026-11-09) was produced with them. The four judges still come from four different makers:

<!-- MODELS:BEGIN -->
| Judge model | Maker |
|---|---|
| gpt-oss-120b | OpenAI |
| DeepSeek-V4.1-Flash | DeepSeek |
| GLM-5.2 | Zhipu |
| Qwen3-30B | Alibaba |
<!-- MODELS:END -->

The replacements did not vote identically to the models they replaced. On the earlier baseline run (data in `docs/model-retirement-2026-11/`): Qwen3-30B matched the Qwen3-235B baseline on 9 of 10 baseline claims (C10 MIXED became SUPPORTED); DeepSeek-V4.1-Flash matched DeepSeek-V4-Flash on 8 of 10 baseline claims (C2 and C3 SUPPORTED became MIXED). A panel on new models is not the same panel; for a decision that matters, re-run it on your own question. Source of these figures: `docs/model-retirement-2026-11/regress_near.json`. The planted false claim C20 was CONTRADICTED by all four judges in the published run (see THESIS.md).

## Files

| File | Purpose |
|---|---|
| Makefile | Build targets |
| thesis_doc.py | Write and check THESIS.md, TRIPWIRES.md and WEAKNESSES.md |
| verify.py | Offline: check derived numbers against recorded hashes, rebuild the BigQuery numbers, check citations and file hashes; with the source files present, rebuild all numbers |
| verify_online.py | Re-download every source for the same dates, rebuild all numbers, compare |
| export_csv.py | Export raw daily charts and NEAR Intents Sundays as CSV and generate data/SHA256SUMS |
| dashboard.py | Build out/index.html |
| panel.py | Run AI judges on all claims (needs API key) |
| metrics.py | Compute 954 metrics from raw data |
| score.py | Score tripwires and forecasts |
| fetch.py | Download raw daily data (no API key) |
| intents.py | Fetch NEAR Intents transactions (no API key) |
| panel.py.example | Example with claims |
| CLAIMS | List of claims to judge |
| tripwires.json | Conditions that would prove the thesis wrong (T1,T2,T3), two provider checks (T5,T6) and two other tripwires (T4) |
| forecasts.json | Three dated forecasts (F1,F2,F3) |
| out/panel.json | AI judges' verdicts on all claims (2026-11-09) |
| out/metrics.json | 954 computed metrics (2026-11-09) |
| out/index.html | Interactive dashboard |
| data/*.json | Raw daily exports |
| data/nearblocks_daily.csv | Exported NearBlocks daily charts |
| data/intents_sundays.csv | Exported NEAR Intents Sundays |
| data/SHA256SUMS | Hashes of all data files as fetched (source files are hashed, not shipped) |
| data/DERIVED_SHA256SUMS | Hashes of out/metrics.json and out/panel.json |
| data/RAW_NOT_COMMITTED.txt | The source files that are not shipped (python3 fetch.py downloads them) |
| data/MANIFEST.json | Metadata for every data file: sha256, bytes, url, what |
| THESIS.md | Full investment thesis |
| TRIPWIRES.md | Conditions that would prove the thesis wrong and three forecasts |
| WEAKNESSES.md | Full list of known weak points, each with source |

## Disclosures

- AI tools: the code, documents and tests in this repository were written with AI coding tools, not typed by hand. Claude (Anthropic) wrote the first versions of the data download, the metrics, the judge-panel code and the dashboard (commits from 2 Nov 2026), and wrote the specification that the later build followed. The later parts (the document generator, the CSV export and hash check, the Makefile, the README and the tests) were written by DeepSeek (a Flash model) and gpt-oss-120b through an automated build process, with other AI coding models making repairs and two further AI models reviewing the result. A person, Alan Finney, directed the work.
- The judge panel is four AI models, listed in the table under "Model retirement".
- Libraries: the Python standard library only for `make verify`; `pytest` for the tests; `boto3` only in `panel.py` and `intents.py`, for an optional credential lookup that `make verify` never runs.
- Hosted page: https://yxq5uhabxag4cytbo6blvklida0dkobj.lambda-url.us-east-2.on.aws/ (same content as `out/index.html`).
- Commits: all are dated 2026-11-02 or later, inside the hackathon window.

## License

Apache-2.0
