"""Build out/index.html (static, no external scripts) from out/metrics.json and out/panel.json."""
import json, html, datetime as dt

def line(series, title, unit="", color="#6c5ce7", log=False, w=560, h=200):
    import math
    ks = list(series); vs = [series[k] for k in ks]
    f = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    ys = [f(v) for v in vs]; lo, hi = min(ys), max(ys); hi = hi if hi > lo else lo + 1
    px = lambda i: 40 + i * (w - 50) / max(len(ks) - 1, 1)
    py = lambda y: 10 + (h - 40) * (1 - (y - lo) / (hi - lo))
    pts = " ".join(f"{px(i):.1f},{py(y):.1f}" for i, y in enumerate(ys))
    ticks = "".join(f'<text x="{px(i):.0f}" y="{h-8}" class="t">{ks[i]}</text>' for i in range(0, len(ks), max(1, len(ks)//6)))
    fmt = lambda v: f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.3g}"
    return (f'<figure><figcaption>{html.escape(title)}</figcaption><svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>{ticks}'
            f'<text x="42" y="20" class="t">max {fmt(max(vs))}{unit}</text><text x="42" y="{h-26}" class="t">min {fmt(min(vs))}{unit}{" (log scale)" if log else ""}</text></svg></figure>')

def build():
    m = json.load(open("out/metrics.json")); p = json.load(open("out/panel.json"))
    mon = {k: v for k, v in m["monthly"].items() if k >= "2022-01" and k < m["as_of"][:7]}
    fpa = {k: v["fee_usd"] / max(v["active"] * 30.4, 1) for k, v in mon.items()}
    charts = (line({k: v["active"] for k, v in mon.items()}, "Daily active accounts (monthly mean)", log=True)
              + line({k: v["price"] for k, v in mon.items()}, "NEAR price, USD (monthly mean)", color="#00b894")
              + line({k: v["fee_usd"] for k, v in mon.items()}, "Fees paid per month, USD", color="#e17055")
              + line(fpa, "Fees per active account per day, USD", color="#0984e3", log=True))
    if m.get("intents_weekly"):
        iw = m["intents_weekly"]
        charts += line({k: v["usd"] / 1e6 for k, v in iw.items()}, "NEAR Intents swap volume on sampled Sundays, $M", color="#fdcb6e")
        charts += line({k: v["swaps"] for k, v in iw.items()}, "NEAR Intents successful swaps on sampled Sundays", color="#a29bfe")
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
    k = lambda path: m[path]
    kp = [("Active accounts, 30-day mean", f'{m["active"]["avg_30d"]:,.0f}', f'{m["active"]["yoy_pct"]:+.0f}% vs a year ago'),
          ("Transactions per day", f'{m["txns"]["avg_30d"]:,.0f}', f'{m["txns"]["yoy_pct"]:+.0f}%'),
          ("Fees per day, USD", f'${m["fee_usd"]["avg_30d"]:,.0f}', f'{m["fee_usd"]["yoy_pct"]:+.0f}%'),
          ("Transfer value per day, USD", f'${m["vol_usd"]["avg_30d"]/1e6:,.0f}M', f'{m["vol_usd"]["yoy_pct"]:+.0f}%'),
          ("Supply growth, 12 months", f'{m["supply"]["growth_pct"]:.1f}%', f'≈ ${m["fees"]["issuance_usd_365d"]/1e6:,.0f}M issued vs ${m["fees"]["fees_usd_365d"]/1e6:,.1f}M fees'),
          ("Market cap ÷ annual fees", f'{m["fees"]["mcap_to_fees"]:,.0f}×', "")]
    kpis = "".join(f'<div class="kpi"><div class="l">{a}</div><div class="n">{b}</div><div class="d">{c}</div></div>' for a, b, c in kp)
    css = """:root{--bg:#fff;--fg:#1d1d24;--mut:#666;--card:#f5f5fa;--line:#ddd}
@media (prefers-color-scheme:dark){:root{--bg:#121218;--fg:#eee;--mut:#aaa;--card:#1d1d26;--line:#333}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.6em;margin:.2em 0}.mut{color:var(--mut)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.kpi{background:var(--card);border-radius:10px;padding:10px}.kpi .l{font-size:.8em;color:var(--mut)}.kpi .n{font-size:1.5em;font-weight:700}.kpi .d{font-size:.8em}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}figure{margin:0;background:var(--card);border-radius:10px;padding:8px}
figcaption{font-weight:600;font-size:.9em}svg{width:100%;height:auto}.t{font-size:10px;fill:var(--mut)}
table{border-collapse:collapse;width:100%;font-size:.9em}td,th{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:left}
.v{font-weight:700;padding:1px 6px;border-radius:4px}.ok{background:#2ecc7133}.no{background:#e74c3c33}.mix{background:#f1c40f44}.na{background:#9993}
.side{font-size:.75em;padding:0 5px;border-radius:4px;background:#9992}.bull{color:#27ae60}.bear{color:#c0392b}
blockquote{background:var(--card);margin:8px 0;padding:8px 12px;border-left:4px solid #6c5ce7;border-radius:6px}.wrap{overflow-x:auto}"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEAR, Cross-Examined</title><style>{css}</style></head><body>
<h1>NEAR, Cross-Examined</h1>
<p class="mut">An evidence-first long-term thesis on NEAR. Every number below is computed from public NearBlocks daily data (as of {m['as_of']}, {m['n_days']} days) by <code>make thesis</code>, and every claim is judged separately by {len(p['judges'])} AI models from different makers. Judges can only cite metric paths; the numbers are filled in by code, so none can be invented. Research, not financial advice.</p>
<h2>The numbers</h2><div class="kpis">{kpis}</div>
<h2>Charts (monthly, Jan 2022 on)</h2><div class="charts">{charts}</div>
<h2>Claims, cross-examined</h2><div class="wrap"><table><tr><th>Claim</th><th>Panel verdict</th><th>Evidence (computed)</th><th>Each judge</th><th>Caveat</th></tr>{rows}</table></div>
<h2>What each judge concluded</h2>{th}
<h2>Context from public sources (checked by an independent audit)</h2>
<ul>
<li>Nansen's Q3 2025 NEAR report found one app, HOT Wallet, had more than 100 times the active addresses of the next entity and 56.1% of transactions. That concentration is why account counts swing so hard: <a href="https://research.nansen.ai/articles/nansen-s-near-quarterly-report-q3-2025">Nansen, Q3 2025</a>.</li>
<li>NEAR governance passed HSP-027 in 2026 to stop rebating part of gas fees to contract owners and burn them instead, so fees now offset issuance a little more than before: <a href="https://thedefiant.io/news/blockchains/near-governance-votes-to-scrap-developer-gas-rebate">The Defiant</a>. At current fee levels the offset is still under 1% of issuance.</li>
<li>Price and USD volume move together, so transfer value is also shown in NEAR tokens (claim C9).</li>
</ul>
<h2>Reproduce</h2><p><code>git clone</code> the repository, then <code>make thesis</code>. It downloads the data (NEAR Intents needs a free partner key in <code>INTENTS_JWT</code>), recomputes every metric (<code>out/metrics.json</code>), re-runs the panel (<code>out/panel.json</code>, needs an OpenAI-compatible API key) and rebuilds this page. <code>make numbers</code> recomputes the numbers alone, with no key.</p>
<p class="mut">Built at NEAR HACKATHON by 3Dogs Nexus (3dogs.ai). Judges: {html.escape(', '.join(p['judges']))}.{' Failed judges: ' + html.escape(', '.join(p['failed_judges'])) if p['failed_judges'] else ''}</p>
</body></html>"""
    open("out/index.html", "w").write(page); print("wrote out/index.html", len(page))

if __name__ == "__main__":
    build()
