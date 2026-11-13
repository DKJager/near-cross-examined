"""Build out/index.html (static, no external scripts) from out/metrics.json and out/panel.json."""
import json
import html
import math
import datetime as dt


def money(v: float) -> str:
    """Format a dollar amount for human display.

    |v| >= 1e9  -> "$X.XX billion"
    |v| >= 1e6  -> "$X.X million"
    else        -> "$Y,YYY" (no decimals, thousands separator)
    Same rendering rule as thesis_doc.money.
    """
    if abs(v) >= 1e9:
        return f"${v/1e9:,.2f} billion"
    if abs(v) >= 1e6:
        return f"${v/1e6:,.1f} million"
    return f"${v:,.0f}"


def line(
    series: dict[str, float],
    title: str,
    unit: str = "",
    color: str = "#6c5ce7",
    log: bool = False,
    w: int = 560,
    h: int = 200,
    query: str = "",
    says: str = "",
) -> str:
    """Build an SVG line-chart ``<figure>`` string from a date-keyed *series*.

    *series*  : dict mapping ISO-date strings (YYYY-MM-DD or YYYY-MM) to float values.
    Returns a self-contained HTML string (figure, SVG, optional caption paragraphs).
    """
    ks = list(series)
    vs = [series[k] for k in ks]
    f = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    ys = [f(v) for v in vs]
    lo, hi = min(ys), max(ys)
    hi = hi if hi > lo else lo + 1
    px = lambda i: 40 + i * (w - 50) / max(len(ks) - 1, 1)
    py = lambda y: 10 + (h - 40) * (1 - (y - lo) / (hi - lo))
    pts = " ".join(f"{px(i):.1f},{py(y):.1f}" for i, y in enumerate(ys))
    ticks = "".join(
        f'<text x="{px(i):.0f}" y="{h-8}" class="t">{ks[i]}</text>'
        for i in range(0, len(ks), max(1, len(ks) // 6))
    )
    fmt = lambda v: f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.3g}"
    caption_says = f'<p class="says">{html.escape(says)}</p>' if says else ""
    # Determine metric path and source file based on title and query
    # Metric path pattern: section.YYYY-MM.key (or intents_weekly.YYYY-MM-DD.key)
    # Use the first key to get the month/date part.
    first_key = ks[0] if ks else ""
    if first_key:
        if len(first_key) == 7:  # YYYY-MM
            date_part = first_key
        else:                     # YYYY-MM-DD
            date_part = first_key

    if "Daily active accounts" in title:
        metric_path = f"monthly.{date_part}.active"
        source_file = "charts_raw.json"
        sql_extra = '. SQL: <code>sql/active_accounts_daily.sql</code>'
    elif "Daily transactions" in title:
        metric_path = f"monthly.{date_part}.txns"
        source_file = "charts_raw.json"
        sql_extra = '. SQL: <code>sql/transactions_daily.sql</code>'
    elif title.startswith("BigQuery:") and "accounts" in title:
        metric_path = "crosscheck.bq_active_vs_nearblocks_pct"
        source_file = "bq_active_accounts_daily.csv"
        sql_extra = '. SQL: <code>sql/active_accounts_daily.sql</code> (run once on 13 Nov 2026)'
    elif title.startswith("BigQuery:"):
        metric_path = "crosscheck.bq_txns_largest_daily_drop_pct"
        source_file = "bq_transactions_daily.csv"
        sql_extra = '. SQL: <code>sql/transactions_daily.sql</code> (run once on 13 Nov 2026)'
    elif "NEAR price" in title:
        metric_path = f"monthly.{date_part}.price"
        source_file = "coingecko_near.json"
        sql_extra = ''
    elif "Fees paid per month, USD" in title and "chart" in query.lower():
        metric_path = f"monthly.{date_part}.fee_usd"
        source_file = "charts_raw.json"
        sql_extra = ''
    elif "Fees per active account" in title:
        metric_path = f"monthly.{date_part}.fee_per_active_calc"
        source_file = "charts_raw.json"
        sql_extra = ''
    elif "NEAR Intents swap volume on sampled Sundays" in title:
        metric_path = f"intents_weekly.{first_key}.usd"
        source_file = "intents_days.json"
        sql_extra = ''
    elif "NEAR Intents successful swaps" in title:
        metric_path = f"intents_weekly.{first_key}.swaps"
        source_file = "intents_days.json"
        sql_extra = ''
    elif "Fees users paid to apps" in title:
        metric_path = f"monthly2.{date_part}.app_fees"
        source_file = "llama_fees_near.json"
        sql_extra = ''
    elif "Gas fees paid to the chain" in title:
        metric_path = f"monthly2.{date_part}.gas_fees"
        source_file = "llama_gas_fees_near.json"
        sql_extra = ''
    elif "NEAR Intents revenue kept by NEAR" in title:
        metric_path = f"monthly2.{date_part}.intents_revenue"
        source_file = "llama_intents_revenue.json"
        sql_extra = ''
    elif "Total value locked on NEAR" in title:
        metric_path = f"monthly2.{date_part}.tvl"
        source_file = "llama_tvl_near.json"
        sql_extra = ''
    else:
        metric_path = f"monthly.{date_part}.unknown"
        source_file = "charts_raw.json"
        sql_extra = ''
    details_caption = (
        f'<details><summary>How this is computed</summary><p>Metric path: <code>{metric_path}</code>. '
        f'Source: <code>{source_file}</code>. Query: <code>{html.escape(query)}</code>{sql_extra}.</p></details>'
    )
    return (
        f'<figure><figcaption>{html.escape(title)}</figcaption><svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>{ticks}'
        f'<text x="42" y="20" class="t">max {fmt(max(vs))}{unit}</text><text x="42" y="{h-26}" class="t">min {fmt(min(vs))}{unit}{" (log scale)" if log else ""}</text></svg>'
        + caption_says
        + details_caption
        + "</figure>"
    )


def build() -> None:
    """Read out/metrics.json and out/panel.json, write out/index.html.

    Side-effect: overwrites ``out/index.html``.
    """
    m = json.load(open("out/metrics.json"))
    p = json.load(open("out/panel.json"))

    # Load optional JSONs safely
    tw = {}
    fc = {}
    try:
        with open("tripwires.json") as f:
            tw = json.load(f)
    except FileNotFoundError:
        pass
    try:
        with open("forecasts.json") as f:
            fc = json.load(f)
    except FileNotFoundError:
        pass

    hero_tiles = f"""
    <p class="thesis"><b>NEAR is a one-product network priced for that product to keep compounding.</b></p>
    <div class="heroes">
        <div class="hero"><div class="l">App fees, last 365 days</div><div class="n">${m['apps']['fees_usd_365d']/1e6:,.1f}M</div></div>
        <div class="hero"><div class="l">NEAR Intents share of app fees, last 30 days</div><div class="n">{m['apps']['intents_share_30d']*100:.0f}%</div></div>
        <div class="hero"><div class="l">Active accounts, 30-day average vs a year ago</div><div class="n">{m['active']['yoy_pct']:+.0f}%</div></div>
    </div>
    """

    # KPI tiles list
    kp = [
        ("Active accounts, 30-day mean", f'{m["active"]["avg_30d"]:,.0f}', f'{m["active"]["yoy_pct"]:+.0f}% vs a year ago'),
        ("Transactions per day", f'{m["txns"]["avg_30d"]:,.0f}', f'{m["txns"]["yoy_pct"]:+.0f}%'),
        ("Fees per day, USD", f'${m["fee_usd"]["avg_30d"]:,.0f}', f'{m["fee_usd"]["yoy_pct"]:+.0f}%'),
        ("Transfer value per day, USD", f'${m["vol_usd"]["avg_30d"]/1e6:,.0f}M', f'{m["vol_usd"]["yoy_pct"]:+.0f}%'),
        ("Supply growth, 12 months", f'{m["supply"]["growth_pct"]:.1f}%', f'≈ ${m["fees"]["issuance_usd_365d"]/1e6:,.0f}M issued vs ${m["fees"]["fees_usd_365d"]/1e6:,.1f}M fees'),
        ("Market cap ÷ annual gas fees", f'{m["fees"]["mcap_to_fees"]:,.0f}×', ""),
        ("App fees, last 365 days", f'${m["apps"]["fees_usd_365d"]/1e6:,.1f}M', f'{m["apps"]["x_gas_fees"]:,.0f}× the chain\'s gas fees'),
        ("NEAR Intents share of app fees", f'{m["apps"]["intents_share_30d"]*100:.0f}%', "last 30 days"),
        ("NEAR's Intents revenue, a year at today's pace", f'${m["intents_daily"]["revenue_annualised"]/1e6:,.1f}M', f'{m["intents_daily"]["revenue_yoy_pct"]:+.0f}% vs a year ago'),
        ("Buybacks cover of new issuance", f'{m["holders"]["cover_of_issuance_pct"]:.0f}%', f'since {m["holders"]["first_day"]}'),
        ("Market cap ÷ Intents revenue", f'{m["valuation"]["mcap_to_intents_revenue_annualised"]:,.0f}×', f'{m["valuation"]["mcap_to_app_fees"]:,.0f}× app fees'),
        ("Gas fees, two providers", f'{m["crosscheck"]["gas_fees_abs_diff_pct"]:.2f}% apart', "NearBlocks vs DefiLlama, 365 days"),
    ]
    kpis = "".join(
        f'<div class="kpi"><div class="l">{a}</div><div class="n">{b}</div><div class="d">{c}</div></div>'
        for a, b, c in kp
    )

    mon = {k: v for k, v in m["monthly"].items() if k >= "2022-01" and k < m["as_of"][:7]}
    fpa = {k: v["fee_usd"] / max(v["active"] * 30.4, 1) for k, v in mon.items()}

    charts = (
        line({k: v["active"] for k, v in mon.items()}, "Daily active accounts (monthly mean)", log=True,
             query="GET api.nearblocks.io/v1/charts -> mean(active_accounts) by month", says=f"Active accounts are {m['active']['yoy_pct']:+.0f}% against a year ago and {m['active_peak']['current_vs_peak_pct']:+.0f}% against the {m['active_peak']['date'][:4]} peak.")
      + line({k: v["txns"] for k, v in mon.items()}, "Daily transactions (monthly mean)", color="#d63031", log=True,
             query="GET api.nearblocks.io/v1/charts -> mean(txns) by month", says=f"Transactions fell {abs(m['txn_step']['change_pct']):.0f}% in one month ({m['txn_step']['month']}): a step, not a slide.")
      + line({k: v["price"] for k, v in mon.items()}, "NEAR price, USD (monthly mean)", color="#00b894",
             query="GET api.nearblocks.io/v1/charts -> mean(near_price) by month", says=f"Price is {m['price']['yoy_pct']:+.0f}% against a year ago while accounts and transactions fell.")
      + line({k: v["fee_usd"] for k, v in mon.items()}, "Fees paid per month, USD", color="#e17055",
             query="GET api.nearblocks.io/v1/charts -> sum(txn_fee_usd) by month", says=f"Fees over 365 days were ${m['fees']['fees_usd_365d']/1e6:,.1f}M against ${m['fees']['issuance_usd_365d']/1e6:,.0f}M of new issuance.")
      + line(fpa, "Fees per active account per day, USD", color="#0984e3", log=True,
             query="GET api.nearblocks.io/v1/charts -> sum(txn_fee_usd) / (mean(active_accounts) * 30.4) by month", says=f"Each remaining account pays {m['fee_per_active']['now']/m['fee_per_active']['year_ago']:.1f} times the fees of a year ago.")
    )
    if m.get("intents_weekly"):
        iw = m["intents_weekly"]
        charts += line({k: v["usd"] / 1e6 for k, v in iw.items()}, "NEAR Intents swap volume on sampled Sundays, $M", color="#fdcb6e",
                       query="NEAR Intents Explorer API, successful 1Click swaps, one full UTC Sunday per week -> sum(usd) per day", says=f"Swap dollar volume moved {m['intents']['usd_change_pct']:+.0f}% from the first four samples to the last four.")
        charts += line({k: v["swaps"] for k, v in iw.items()}, "NEAR Intents successful swaps on sampled Sundays", color="#a29bfe",
                       query="NEAR Intents Explorer API, successful 1Click swaps, one full UTC Sunday per week -> count(swaps) per day", says=f"Swap count moved {m['intents']['swaps_change_pct']:+.0f}% over the same samples.")

    m2 = m.get("monthly2", {})
    as_of_month = m["as_of"][:7]
    chart_months = {k: v for k, v in m2.items() if k < as_of_month}
    
    if any("app_fees" in v for v in chart_months.values()):
        app_fees_series = {k: v["app_fees"] for k, v in chart_months.items() if k >= "2024-01" and "app_fees" in v}
        charts += line(app_fees_series, "Fees users paid to apps on NEAR, per month, USD", color="#6c5ce7", log=True,
                       query="GET api.llama.fi/overview/fees/near?dataType=dailyFees -> sum(fees) by month",
                       says=f"Users paid apps {money(m['apps']['fees_usd_365d'])} in 365 days, {m['apps']['x_gas_fees']:,.0f} times the chain's gas fees; {m['apps']['intents_share_30d']*100:.0f}% of the last 30 days came from NEAR Intents.")

    if any("gas_fees" in v for v in chart_months.values()):
        gas_fees_series = {k: v["gas_fees"] for k, v in chart_months.items() if k >= "2024-01" and "gas_fees" in v}
        charts += line(gas_fees_series, "Gas fees paid to the chain, per month, USD (DefiLlama)", color="#e17055", log=True,
                       query="GET api.llama.fi/summary/fees/near?dataType=dailyFees -> sum(fees) by month",
                       says=f"Over 365 days this agrees with NearBlocks to {m['crosscheck']['gas_fees_abs_diff_pct']:.2f}%.")

    if any("intents_revenue" in v for v in chart_months.values()):
        intents_rev_series = {k: v["intents_revenue"] for k, v in chart_months.items() if "intents_revenue" in v}
        charts += line(intents_rev_series, "NEAR Intents revenue kept by NEAR, per month, USD", color="#00b894",
                       query="GET api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue -> sum(revenue) by month",
                       says=f"NEAR keeps {m['intents_daily']['kept_share_30d']*100:.0f}% of Intents fees: {money(m['intents_daily']['revenue_annualised'])} a year at the last 30 days' pace, used to buy back NEAR since {m['holders']['first_day']}.")

    if any("tvl" in v for v in chart_months.values()):
        tvl_series = {k: v["tvl"] for k, v in chart_months.items() if k >= "2022-01" and "tvl" in v}
        charts += line(tvl_series, "Total value locked on NEAR, USD (monthly mean)", color="#0984e3",
                       query="GET api.llama.fi/v2/historicalChainTvl/Near -> mean(tvl) by month",
                       says=f"TVL is {m['tvl']['yoy_pct']:+.0f}% and stablecoin supply {m['stables']['yoy_pct']:+.0f}% against a year ago.")

    import os as _os, csv as _csv
    _bq = _os.path.join("data", "bq_transactions_daily.csv")
    if _os.path.exists(_bq) and "bq_txns_largest_drop_date" in m.get("crosscheck", {}):
        _d = {r["block_date"]: float(r["value"]) for r in _csv.DictReader(open(_bq))}
        _cc = m["crosscheck"]
        charts += line(_d, "BigQuery: transactions per day, last 365 days", color="#e17055",
                       query="SELECT block_date, COUNT(DISTINCT transaction_hash) FROM bigquery-public-data.crypto_near_mainnet_us.transactions WHERE block_date BETWEEN '2025-11-10' AND '2026-11-09' GROUP BY block_date",
                       says=f"Same chain data as NearBlocks (equal on all {_cc['bq_txns_bigquery_days']} days). The biggest one-day fall is {_cc['bq_txns_largest_daily_drop_pct']:.0f}% on {_cc['bq_txns_largest_drop_date']}: the transaction decline is mostly one step, and daily active accounts did not step that day, so the account trend (30-day means) is the better usage measure.")

    _bqa = _os.path.join("data", "bq_active_accounts_daily.csv")
    if _os.path.exists(_bqa) and "bq_txns_largest_drop_date" in m.get("crosscheck", {}):
        _da = {r["block_date"]: float(r["value"]) for r in _csv.DictReader(open(_bqa))}
        _ks = sorted(_da)
        charts += line(_da, "BigQuery: daily active accounts, last 365 days", color="#6c5ce7",
                       query="SELECT block_date, COUNT(DISTINCT signer_account_id) FROM bigquery-public-data.crypto_near_mainnet_us.transactions WHERE block_date BETWEEN '2025-11-10' AND '2026-11-09' GROUP BY block_date",
                       says=f"Equal to NearBlocks on all {len(_da)} days. Daily counts have short bursts, so the tiles use 30-day means: the mean of the first 30 days here is {sum(_da[k] for k in _ks[:30])/30:,.0f}, of the last 30 days {sum(_da[k] for k in _ks[-30:])/30:,.0f}.")
    px, st = m["paradox"], m["txn_step"]

    what_we_can = " ".join([
        "What we can and cannot say: this data cannot name the cause.",
        f"The numbers are consistent with fewer small, everyday transactions and a larger average transfer: NEAR moved per transaction rose {px['near_per_txn_x']:.1f}x (`paradox.near_per_txn_x`).",
        "No transaction-size distribution is measured here, so we do not know which kinds of transactions stopped, or whether larger transfers took their place.",
    ])
    so_paradox = " ".join([
        "So the paradox is not a contradiction.",
        "The data shows fewer transactions and more NEAR moved per transaction.",
        "That is consistent with a chain that lost many small transactions and kept larger ones, but it does not prove it.",
    ])

    paradox = (
        f'<div class="wrap"><table><tr><th>Piece</th><th>Now vs a year ago</th><th>Metric</th></tr>'
        f'<tr><td>Dollar transfer value</td><td>{px["usd_volume_x"]:.2f}x</td><td><code>paradox.usd_volume_x</code></td></tr>'
        f'<tr><td>of which: price</td><td>{px["price_x"]:.2f}x</td><td><code>paradox.price_x</code></td></tr>'
        f'<tr><td>of which: NEAR actually moved</td><td>{px["near_volume_x"]:.2f}x</td><td><code>paradox.near_volume_x</code></td></tr>'
        f'<tr><td>Transactions</td><td>{px["txns_x"]:.2f}x</td><td><code>paradox.txns_x</code></td></tr>'
        f'<tr><td>NEAR moved per transaction</td><td>{px["near_per_txn_x"]:.1f}x ({px["near_per_txn_year_ago"]:.1f} to {px["near_per_txn_now"]:.1f} NEAR)</td><td><code>paradox.near_per_txn_x</code></td></tr></table></div>'
        f"<p>About {px['share_of_usd_growth_from_price']*100:.0f}% of the dollar growth is the price rise. In {st['month']} transactions fell {abs(st['change_pct']):.0f}% in one month while active accounts fell {abs(st['active_change_pct_same_month']):.0f}%; that month is {st['share_of_12m_txn_fall']*100:.0f}% of the year's fall.</p>"
        f"<p>{what_we_can}</p>"
        f"<p>{so_paradox}</p>"
    )

    import score as _score

    def _rows(items):
        out = ""
        for r, sc in zip(items, _score.score(items, m)):
            v = sc["value"]
            val = "no data" if v is None else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.3g}")
            out += (f'<tr><td><b>{r["id"]}</b> <span class="side">{html.escape(r["side"])}</span><br>{html.escape(r["statement"])}</td><td><code>{r["path"]}</code> {html.escape(r["op"])} {r["threshold"]:,}</td>'
                    f'<td>{val}</td><td>{sc["status"]}</td><td>{r["due"]}</td></tr>')
        return out

    trip_rule = tw.get("rule", "") if isinstance(tw, dict) else ""
    trip = (f'<p>{html.escape(trip_rule)}</p><div class="wrap"><table><tr><th>Tripwire or forecast</th><th>Test</th><th>Today</th><th>Status</th><th>Due</th></tr>'
            + _rows(tw.get("tripwires", []))
            + _rows(fc.get("forecasts", []))
            + '</table></div>')

    vc = {"SUPPORTED": "ok", "CONTRADICTED": "no", "MIXED": "mix", "SPLIT": "mix", "NOT_TESTABLE": "na"}
    rows = ""
    for c in p["claims"]:
        ev = "<br>".join(f'<code>{html.escape(e["path"])}</code> = {e["value"]:,.4g}' for e in c["evidence"] if isinstance(e["value"], (int, float)))
        votes = "<br>".join(f'{html.escape(n.split(" (")[0])}: {html.escape(v)}' for n, v in c["votes"].items())
        cav = html.escape(c["caveats"][0][1]) if c["caveats"] else ""
        rows += (f'<tr><td><b>{c["id"]}</b> <span class="side {c["side"]}">{c["side"]}</span><br>{html.escape(c["claim"])}</td>'
                 f'<td><span class="v {vc.get(c["verdict"],"na")}">{c["verdict"]}</span><br><small>{c["agreement"]} judges</small></td>'
                 f'<td><small>{ev}</small></td><td><small>{votes}</small></td><td><small>{cav}</small></td></tr>')

    th = "".join(f'<blockquote><b>{html.escape(n)}</b>: {html.escape(t["thesis"] or "")}<br><i>Would change its mind:</i> {html.escape(t["would_change_my_mind"] or "")}</blockquote>' for n, t in p["theses"].items())

    import re as _re
    _figs = _re.findall(r"<figure>.*?</figure>", charts, _re.S)
    hero_chart = next(f for f in _figs if f.startswith("<figure><figcaption>Daily active accounts"))
    other_charts = "".join(f for f in _figs if f is not hero_chart)
    thesis_line = '<p class="thesis"><b>NEAR is a one-product network priced for that product to keep compounding.</b></p>'
    _means = [
        f"{m['apps']['x_gas_fees']:,.0f} times the chain's gas fees: a different flow of money, so a scale comparison only.",
        "Almost all of it runs through NEAR Intents.",
        "Far fewer people use the chain.",
    ]
    _tiles = _re.findall(r'<div class="hero">.*?</div></div>', hero_tiles, _re.S)
    hero_row = "".join(f'<div class="herocell">{t}<p class="means">{mm}</p></div>' for t, mm in zip(_tiles, _means))

    css = """body {
    background: #0b0f14;
    color: #c9d1d9;
    font: 17px/1.6 system-ui, -apple-system, sans-serif;
    margin: 0;
    padding: 40px 20px;
    overflow-x: hidden;
}

.wide-container {
    max-width: 1040px;
    margin: 0 auto;
}

h1 {
    font-size: 2.5em;
    font-weight: 700;
    margin: 0 0 0.5em;
    line-height: 1.1;
    letter-spacing: -0.02em;
}

.thesis {
    font-size: 1.25em;
    color: #8b949e;
    margin: 0 0 3em;
    font-weight: 400;
    max-width: 760px;
}

.hero-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 40px;
}

.herocell {
    display: flex;
    flex-direction: column;
}

.hero {
    background: #121a22;
    border: 1px solid #26313c;
    border-radius: 8px;
    padding: 24px;
    flex: 0 0 auto;
    min-height: 168px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.hero .l {
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9aa4ae;
    margin-bottom: 12px;
}

.hero .n {
    font-size: 3.5em;
    font-weight: 700;
    color: #00ec97;
    line-height: 1;
    margin-bottom: 16px;
    letter-spacing: -0.03em;
}

.means {
    min-height: 4.2em;
    margin-top: 12px !important;
    font-size: 0.95em;
    color: #a9b3bd;
    margin: 0;
    line-height: 1.4;
}

.verify {
    font-size: 0.95em;
    color: #9aa4ae;
    margin: -20px 0 40px;
    padding-top: 10px;
    border-top: 1px solid #26313c;
}

.hero-chart {
    max-width: 1040px;
    margin: 0 auto 60px;
}

.hero-chart figure {
    margin: 0;
    background: #121a22;
    border: 1px solid #26313c;
    border-radius: 8px;
    padding: 20px;
}

details.sec {
    border-bottom: 1px solid #26313c;
    margin: 0;
    padding: 20px 0;
}

details.sec summary {
    font-weight: 600;
    font-size: 1.1em;
    cursor: pointer;
    list-style: none;
    color: #e6edf3;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

details.sec summary::-webkit-details-marker {
    display: none;
}

details.sec summary::after {
    content: "+";
    font-size: 1.2em;
    color: #00ec97;
}

details.sec[open] summary::after {
    content: "−";
}

.sec .content {
    margin-top: 16px;
    color: #8b949e;
    max-width: 760px;
}

.kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 2em 0;
}

.kpi {
    background: #121a22;
    border: 1px solid #26313c;
    border-radius: 6px;
    padding: 16px;
}

.kpi .l {
    font-size: 0.8em;
    color: #484f58;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.kpi .n {
    font-size: 1.8em;
    font-weight: 700;
    color: #00ec97;
}

.kpi .d {
    font-size: 0.85em;
    color: #8b949e;
}

.charts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 24px;
    margin: 2em 0;
}

figcaption {
    font-weight: 600;
    font-size: 0.95em;
    color: #e6edf3;
    margin-bottom: 12px;
}

.says {
    margin: 8px 0 0;
    font-size: 0.95em;
    color: #9aa4ae;
}

svg {
    width: 100%;
    height: auto;
    overflow: visible;
}

.t {
    font-size: 8px;
    fill: #9aa4ae;
}

polyline {
    fill: none;
    stroke: #00ec97;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9em;
    margin: 1.5em 0;
}

td, th {
    border-bottom: 1px solid #26313c;
    padding: 12px 16px;
    text-align: left;
    color: #c9d1d9;
}

.v {
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
}

.ok { background: rgba(46, 230, 166, 0.15); color: #00ec97; }
.no { background: rgba(248, 81, 73, 0.15); color: #f85149; }
.mix { background: rgba(210, 153, 34, 0.15); color: #d29922; }
.na { background: rgba(110, 118, 129, 0.15); color: #6e7681; }

.side {
    font-size: 0.75em;
    padding: 2px 6px;
    border-radius: 4px;
    background: #26313c;
    color: #8b949e;
}

blockquote {
    background: #121a22;
    margin: 1.5em 0;
    padding: 16px 20px;
    border-left: 3px solid #00ec97;
    border-radius: 0 6px 6px 0;
    color: #8b949e;
}

code {
    background: #161b22;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
    color: #00ec97;
}

a {
    color: #00ec97;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

@media (max-width: 768px) {
    body { padding: 20px 16px; font-size: 16px; }
    h1 { font-size: 2em; }
    .thesis { font-size: 1.1em; margin-bottom: 2em; }
    .hero-row { grid-template-columns: 1fr; gap: 16px; margin-bottom: 24px; }
    .hero .n { font-size: 3em; }
    .charts { grid-template-columns: 1fr; }
    .t { font-size: 20px; }
    svg text.t:nth-child(even) { display: none; }
}
h1 { color: #f0f6fc; }
@media (max-width: 768px) { .means { min-height: 0; } .hero { min-height: 0; } }

.thesis { color: #e6edf3; font-size: 1.45em; line-height: 1.35; font-weight: 600; max-width: 820px; margin: 0 0 36px; border-left: 4px solid #00ec97; padding-left: 16px; }
.thesis b { font-weight: 600; }
.hero .n { font-size: 4.2em; }
.verify { margin: 0 0 36px; padding-top: 14px; }
.verify code { color: #00ec97; }
details.sec > summary { padding: 18px 0; font-size: 1.1em; }
@media (max-width: 768px) { .thesis { font-size: 1.2em; } .hero .n { font-size: 3.2em; } }

details.sec { max-width: 1040px; margin: 12px auto; border: 1px solid #26313c; border-radius: 10px; background: #121a22; }
details.sec > summary { padding: 16px 22px; font-size: 1.05em; font-weight: 600; cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; border: 0; }
details.sec[open] > summary { border-bottom: 1px solid #26313c; }
details.sec > .content { padding: 18px 22px 22px; max-width: 760px; }
body > p.mut, .wrap > p.mut { max-width: 1040px; margin: 28px auto 0; font-size: 0.9em; line-height: 1.55; }

figure { margin: 0 0 1.5em; }
.hero-chart figure { margin: 2em 0; }
details.sec > .content { overflow-x: auto; }
body { background: #0b0f14; }
.hero { background: #121a22; }
@media (max-width: 768px) { details.sec > .content { padding: 14px 14px 18px; } table { display: block; overflow-x: auto; } }

/* first screen: thesis, headline numbers, how to verify; everything else below the fold */
@media (min-width: 769px) { .wide-container { min-height: 84vh; display: flex; flex-direction: column; justify-content: center; } }
.verify { font-size: 1.05em; }
.ctx { max-width: 820px; margin: 0 0 22px; font-size: 1.12em; line-height: 1.5; color: #c9d4de; }
.ctx code { color: #00ec97; }
.thesis { margin-top: 0; }
"""

    _w = m.get("windows", {})
    windows_html = ""
    if _w:
        _st = m["crosscheck"].get("bq_txns_largest_drop_date", "")
        windows_html = (
            "<p>The headline compares 30-day averages with a year ago. Other windows, same data:</p><ul>"
            f"<li>Daily active accounts, 30-day mean against 30, 90, 180, 365 and 730 days earlier: "
            f"{_w['active_accounts_30d_mean_vs_30d_ago_pct']:+.1f}%, {_w['active_accounts_30d_mean_vs_90d_ago_pct']:+.1f}%, "
            f"{_w['active_accounts_30d_mean_vs_180d_ago_pct']:+.1f}%, {_w['active_accounts_30d_mean_vs_365d_ago_pct']:+.1f}%, "
            f"{_w['active_accounts_30d_mean_vs_730d_ago_pct']:+.1f}%.</li>"
            f"<li>App fees: last 30 days against the 30 before {_w['app_fees_last_30d_vs_prior_30d_pct']:+.1f}%; "
            f"last 90 against the 90 before {_w['app_fees_last_90d_vs_prior_90d_pct']:+.1f}%; "
            f"last 365 against the 365 before {_w['app_fees_last_365d_vs_prior_365d_pct']:+.1f}%. The most recent month fell.</li>"
            f"<li>The step in transactions on {_st}: its cause is unknown, and no source we found names it. "
            f"Transactions {_w.get('step_transactions_change_pct', float('nan')):+.1f}%, new accounts {_w.get('step_new_accounts_change_pct', float('nan')):+.1f}%, "
            f"active contracts {_w.get('step_active_contracts_change_pct', float('nan')):+.1f}%, active accounts {_w.get('step_active_accounts_change_pct', float('nan')):+.1f}% "
            "(14 days after against 14 days before). That fits one automated actor stopping, but it is a guess.</li>"
            "<li>Definitions: app fees are the fees DefiLlama tracks for apps on NEAR, which may not cover every app. "
            "The app-fees-to-gas-fees multiple compares two different flows of money, so it shows scale only.</li></ul>"
        )

    import collections as _co
    _vc = _co.Counter(c["verdict"] for c in p["claims"])
    _order = [k for k in ("SUPPORTED", "CONTRADICTED", "SPLIT") if k in _vc] + sorted(k for k in _vc if k not in ("SUPPORTED", "CONTRADICTED", "SPLIT"))
    _parts = [f"{_vc[k]} {html.escape(k)}" for k in _order]
    _vtxt = ", ".join(_parts[:-1]) + ", and " + _parts[-1] if len(_parts) > 2 else " and ".join(_parts)
    _nw = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(len(p["judges"]), str(len(p["judges"])))
    ctx_line = (f'<p class="ctx">One claim about NEAR, tested point by point against on-chain data by AI judges from {_nw} different makers: '
                f'<b>{_vtxt}</b> of {len(p["claims"])} points (SPLIT means no majority of judges). '
                'Check every number yourself: run <code>make verify</code>, no key and no network.</p>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEAR, Cross-Examined</title><style>{css}</style></head><body>
<div class="wide-container">
    <h1>NEAR, Cross-Examined</h1>
    {ctx_line}
    {thesis_line}
    <div class="hero-row">{hero_row}</div>
</div>

<div class="hero-chart">{hero_chart}</div>

<details class="sec"><summary>The numbers</summary><div class="content">
    <div class="kpis">{kpis}</div>
</div></details>

<details class="sec"><summary>All charts</summary><div class="content">
    <div class="charts">{other_charts}</div>
</div></details>

<details class="sec"><summary>Other windows, and what we do not know</summary><div class="content">
    {windows_html}
</div></details>

<details class="sec"><summary>The volume paradox: value up, transactions down</summary><div class="content">
    {paradox}
</div></details>

<details class="sec"><summary>What would prove this wrong (checked on a fixed date)</summary><div class="content">
    {trip}
</div></details>

<details class="sec"><summary>Claims cross-examined</summary><div class="content">
    <div class="wrap"><table><tr><th>Claim</th><th>Panel verdict</th><th>Evidence (computed)</th><th>Each judge</th><th>Caveat</th></tr>{rows}</table></div>
</div></details>

<details class="sec"><summary>What each judge concluded</summary><div class="content">
    {th}
</div></details>

<details class="sec"><summary>Context from public sources</summary><div class="content">
    <ul>
    <li>Nansen's Q3 2025 NEAR report found one app, HOT Wallet, had more than 100 times the active addresses of the next entity and 56.1% of transactions. That concentration is why account counts swing so hard: <a href="https://research.nansen.ai/articles/nansen-s-near-quarterly-report-q3-2025">Nansen, Q3 2025</a>.</li>
    <li>NEAR governance passed HSP-027 in 2026 to stop rebating part of gas fees to contract owners and burn them instead, so fees now offset issuance a little more than before: <a href="https://thedefiant.io/news/blockchains/near-governance-votes-to-scrap-developer-gas-rebate">The Defiant</a>. Over 365 days gas fees equal {m['holders']['gas_cover_of_issuance_pct']:.1f}% of new issuance; the NEAR Intents buybacks are the larger offset, {m['holders']['cover_of_issuance_pct']:.0f}%.</li>
    <li>Price and USD volume move together, so transfer value is also shown in NEAR tokens (claim C9).</li>
    </ul>
</div></details>

<details class="sec"><summary>Weak points</summary><div class="content">
    <p>Every known weak point, with its source, is in <a href="https://github.com/DKJager/near-cross-examined/blob/main/WEAKNESSES.md">WEAKNESSES.md</a>. The short version: account and transaction counts come from one provider; NEAR Intents swap counts are sampled one Sunday a week; staking is not measured.</p>
</div></details>

<details class="sec"><summary>Method, verification and data sources</summary><div class="content">
    <p><code>git clone</code> the repository, then <code>make thesis</code>. It downloads the data (NEAR Intents needs a free partner key in <code>INTENTS_JWT</code>), recomputes every metric (<code>out/metrics.json</code>), re-runs the panel (<code>out/panel.json</code>, needs an OpenAI-compatible API key) and rebuilds this page. <code>make verify</code> needs no key and no network: from a fresh clone it checks the derived numbers against their recorded hashes, rebuilds the BigQuery numbers, checks each judge's citations and the documents, and scores the tripwires; with the source files downloaded it rebuilds every number. <code>make verify-online</code> downloads every source again and rebuilds all the numbers. The source files are not shipped because of their providers' terms; <code>cd data &amp;&amp; sha256sum -c --ignore-missing SHA256SUMS</code> checks the ones you have.</p>
    <p class="mut">Data: NearBlocks, DefiLlama, Intents Explorer, Google BigQuery public dataset (NEAR). Prices: Powered by CoinGecko. The raw files belong to their providers and are not shipped; their hashes are.</p>
    <p class="mut">Built at NEAR HACKATHON by 3Dogs Nexus (3dogs.ai). Judges: {html.escape(', '.join(p['judges']))}.{(' Failed judges: ' + html.escape(', '.join(p['failed_judges']))) if p['failed_judges'] else ''} Built on 3Dogs wisdom of crowds, three reviewers for speed, five when one stands alone. This entry uses a {len(p['judges'])}-judge panel.</p>
</div></details>

<p class="mut">An evidence-first long-term thesis on NEAR. Every number below is computed from public data: NearBlocks daily chain data, DefiLlama fees and revenue, CoinGecko prices and the NEAR Intents Explorer (as of {m['as_of']}; {m['n_days']} days of chain data) by <code>make thesis</code>, and every claim is judged separately by {len(p['judges'])} AI models from different makers. Judges can only cite metric paths; the numbers are filled in by code, so none can be invented. Research, not financial advice.</p>
</body></html>"""
    
    import os
    os.makedirs("out", exist_ok=True)
    with open("out/index.html", "w") as f:
        f.write(page)
    print("wrote out/index.html", len(page))


if __name__ == "__main__":
    build()
