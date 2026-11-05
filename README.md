# NEAR, Cross-Examined

**An investment thesis on NEAR that four AI models from four different makers were forced to argue over, claim by claim, against on-chain numbers they could not change.**

Built for the NEAR Hackathon (Nov 2026), Track 02 Investment Thesis and Track 13 Open Innovation. By 3Dogs Nexus (https://3dogs.ai).

## Do X, see Y

- **See the result now:** open `out/index.html` in a browser. It is a self-contained page: charts, the 10 claims, each judge's vote, and where the judges split.
- **Re-check the numbers:** `python3 -m pytest -q tests` (3 tests, no network). Then `python3 metrics.py` recomputes `out/metrics.json` from `data/charts_raw.json` and prints nothing it cannot cite.
- **Re-run the whole pipeline:** `make thesis` with `NEBIUS_API_KEY` set (and an internet connection). `make data` pulls fresh NearBlocks charts, `make numbers` computes the metrics, `make panel` asks the four judges, `make page` rebuilds the dashboard.

## What it does

1. **Fetch.** `fetch.py` pulls daily chain data (active accounts, transactions, new accounts, fees, transfer volume, supply, price) from the NearBlocks charts API. `intents.py` samples NEAR Intents 1Click swaps, one full UTC Sunday per week for 52 weeks, from the Intents Explorer API.
2. **Compute.** `metrics.py` turns that into 30-day and 90-day year-over-year comparisons, fee and issuance totals, transfer volume counted in NEAR rather than dollars (so price moves do not fake growth), and the correlation between activity and price. Every number carries a `calc` line saying exactly how it was made.
3. **Cross-examine.** `panel.py` puts 10 claims, bull and bear, in front of four judges from four makers (gpt-oss-120b, DeepSeek-V4.1-Flash, GLM-5.2, Qwen3-30B; the archived 1 Nov run used DeepSeek-V4-Flash and Qwen3-235B, see "Model retirement" below). Each judge may cite only metric paths from `out/metrics.json`. Each returns SUPPORTED, REJECTED or MIXED per claim, plus a thesis and what would change its mind.
4. **Show.** `dashboard.py` renders `out/index.html`: charts, votes, splits, dissent.

## What the data says (as of 31 Oct 2026, 30-day means vs a year earlier)

| Metric | Change |
|---|---|
| Daily active accounts | -74% |
| Daily transactions | -84% |
| Daily new accounts | -96% |
| Daily transfer volume in USD | +216% |
| Daily transfer volume in NEAR | +56% |
| Fees per active account | 2.7x higher |
| Total supply | +2.5% |
| Fees collected, last 365 days | ~$1.2M, vs ~$136M of new issuance |
| Market cap / annual fees | ~4,700x |
| NEAR Intents swaps per sampled Sunday | +18% (USD volume -11%) |

## What the judges concluded

Nine of the ten claims got the same vote from all four judges. The one split is the Intents claim (C10): all four marked it MIXED, because swap counts rose while swap dollar volume fell. All four theses land bearish on valuation versus usage, while agreeing the remaining usage is worth more per account than a year ago. Each judge's "what would change my mind" is in `out/panel.json` and on the page.

Nothing here is investment advice. It is a reproducible argument with its sources attached.

## Model retirement, 9 Nov 2026

**The published results in `out/panel.json` and on the page come from the 1 Nov 2026 run with gpt-oss-120b, `deepseek-ai/DeepSeek-V4-Flash-0731`, `zai-org/GLM-5.2` and `Qwen/Qwen3-235B-A22B-Instruct-2507`. They are kept unchanged as the archived record.**

On 9 Nov 2026 Nebius retires two of those models from serverless use ([Nebius notice](https://docs.tokenfactory.nebius.com/november-2026-deprecation-notice)). So that `panel.py` keeps running, its defaults now use Nebius's recommended replacements: `deepseek-ai/DeepSeek-V4.1-Flash-1017` and `Qwen/Qwen3-30B-A3B-Instruct-2507`. The four judges still come from four different makers. To list the models currently served, call `curl -H "Authorization: Bearer $NEBIUS_API_KEY" https://api.tokenfactory.nebius.com/v1/models`.

**The new models do not give identical votes. These are measured differences, larger than our 5% tolerance:**

The 4 Nov 2026 runs used the same 1 Nov metrics and the same prompt, and the data is in `docs/model-retirement-2026-11/`.

| Seat | Model | Votes matching the archive |
|---|---|---|
| Qwen | Qwen3-235B, re-run (baseline) | 10/10 |
| Qwen | **Qwen3-30B-A3B (replacement)** | **9/10**: C10 MIXED becomes SUPPORTED |
| DeepSeek | V4-Flash-0731, re-run (baseline) | 10/10 |
| DeepSeek | **V4.1-Flash-1017 (replacement)** | **8/10**: C2 and C3 SUPPORTED become MIXED |

When the full panel was re-run with the new defaults (`panel_post_swap_summary.json`), none of the ten panel-level verdicts changed. Agreement fell on C3 and C10.

In that run the GLM-5.2 output was cut off once. A retry matched the archive 10/10. Every citation in every run resolved to a real metric.

**Do not treat a re-run on the new models as the same panel. For any decision that matters, re-validate on your own question.**

## Files

| File | Role |
|---|---|
| `fetch.py` | NearBlocks charts -> `data/charts_raw.json` |
| `intents.py` | NEAR Intents Explorer -> `data/intents_days.json` (resumable, rate-limited) |
| `metrics.py` | all computed numbers -> `out/metrics.json` |
| `panel.py` | the four-judge cross-examination -> `out/panel.json` |
| `dashboard.py` | `out/index.html` |
| `tests/test_metrics.py` | checks on the metric math |

Python 3.12, standard library only. No keys are in this repo.

## License

Apache-2.0.
