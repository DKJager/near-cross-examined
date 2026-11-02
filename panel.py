"""Cross-examine each thesis claim with a panel of models from different makers.
Judges may only cite metric PATHS (e.g. "active.yoy_pct"); the reconciler looks the
numbers up itself, so no judge can put an invented number into the result."""
import json, os, re, sys, time, urllib.request, concurrent.futures as cf
from collections import Counter

CLAIMS = [
 ("C1", "bear", "Usage is collapsing: NEAR's daily active accounts and transactions are far below a year ago."),
 ("C2", "bull", "The remaining usage is worth more: fees and transfer value per active account have risen, so the drop in accounts overstates the drop in real economic activity."),
 ("C3", "bear", "Account counts were inflated: the drop in new accounts and active contracts since the 2024 peak points to automated or incentive-driven activity that has since left."),
 ("C4", "bull", "Value moving on NEAR is growing: USD transfer volume is well above a year ago."),
 ("C5", "bear", "Fees do not pay for security: annual fee revenue is tiny next to the value of new token issuance, so holders are diluted far more than fees return."),
 ("C6", "bear", "The valuation is far ahead of usage: market cap is thousands of times annual fees."),
 ("C7", "neutral", "Activity is not a leading indicator of price on NEAR: changes in active accounts barely predict the next quarter's price."),
 ("C8", "bull", "Supply inflation is modest: total supply grew only a few percent in the last year."),
 ("C9", "bull", "Transfer value grew even after removing the price rise: transfer volume measured in NEAR tokens is above a year ago."),
 ("C10", "bull", "Real usage moved to cross-chain swaps: NEAR Intents swap count and USD volume are higher now than a year ago, while account counts fell."),
]

def neb_key():
    import boto3
    key = os.environ.get("NEBIUS_API_KEY") or boto3.client("secretsmanager", region_name="us-east-2").get_secret_value(SecretId="3dogs/nebius-api-key")["SecretString"]
    try:
        d = json.loads(key)
        if isinstance(d, dict):
            vals = [v for v in d.values() if isinstance(v, str) and v]
            key = d.get("api_key") or d.get("key") or (vals[0] if vals else next(iter(d.keys())))
    except Exception: pass
    return key.strip()

JUDGES = {"gpt-oss-120b (OpenAI, open-weight)": "openai/gpt-oss-120b",
          "DeepSeek-V4-Flash (DeepSeek)": "deepseek-ai/DeepSeek-V4-Flash-0731",
          "GLM-5.2 (Zhipu)": "zai-org/GLM-5.2",
          "Qwen3-235B (Alibaba)": "Qwen/Qwen3-235B-A22B-Instruct-2507"}

def ask(model, key, msgs):
    body = {"model": model, "messages": msgs, "max_tokens": 8000, "temperature": 0}
    for attempt in range(3):
        try:
            r = urllib.request.Request("https://api.tokenfactory.nebius.com/v1/chat/completions", data=json.dumps(body).encode(),
                                       headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(r, timeout=300))
            m = d["choices"][0]["message"]
            return m.get("content") or m.get("reasoning_content") or ""
        except Exception as e:
            err = str(e); time.sleep(20)
    return "ERROR " + err

def flat(m, pre=""):
    out = {}
    for k, v in m.items():
        if k in ("monthly", "intents_weekly"): continue
        p = pre + k
        if isinstance(v, dict): out.update(flat(v, p + "."))
        elif isinstance(v, (int, float)): out[p] = v
    return out

def prompt(metrics):
    nums = flat(metrics)
    table = "\n".join(f"{k} = {v:.6g}" for k, v in nums.items())
    calcs = "\n".join(f"{k}: {v['calc']}" for k, v in metrics.items() if isinstance(v, dict) and "calc" in v)
    mon = metrics["monthly"]; ks = sorted(mon)[-24:]
    mt = "\n".join(f"{k}: active={mon[k]['active']:.0f} txns={mon[k]['txns']:.0f} fees_usd={mon[k]['fee_usd']:.0f} new_acc={mon[k]['new_acc']:.0f} price={mon[k]['price']:.3f}" for k in ks)
    iw = metrics.get("intents_weekly", {})
    it = ("\nNEAR INTENTS 1CLICK SWAPS, one full UTC Sunday per week (cite as metric paths under intents.*):\n" + "\n".join(f"{k}: swaps={v['swaps']} usd={v['usd']:.0f}" for k, v in iw.items())) if iw else "\n(No NEAR Intents data available: mark C10 NOT_TESTABLE.)"
    cl = "\n".join(f"{c} [{s}] {t}" for c, s, t in CLAIMS)
    return f"""You are one judge on an evidence panel testing an investment thesis about the NEAR blockchain.
Use ONLY the data below (NearBlocks daily chart data, as of {metrics['as_of']}). Do not use outside knowledge for numbers.

METRICS (path = value):
{table}

HOW EACH WAS COMPUTED:
{calcs}

MONTHLY MEANS (last 24 months; fees_usd is the monthly sum):
{mt}
{it}

CLAIMS:
{cl}

For each claim give a verdict: SUPPORTED, CONTRADICTED, MIXED, or NOT_TESTABLE (the data cannot settle it).
Cite evidence ONLY as metric paths from the METRICS list (e.g. "active.yoy_pct") or month keys like "monthly.2025-06.active". Do not write numbers yourself.
Also give a one-sentence caveat per claim (what could make this reading wrong).
Then write "thesis": 2-3 sentences stating the long-term case for or against NEAR that this evidence best supports, and "would_change_my_mind": one observable result that would reverse it.
Return ONLY JSON: {{"claims":[{{"id":"C1","verdict":"...","evidence":["path",...],"caveat":"..."}}...],"thesis":"...","would_change_my_mind":"..."}}"""

def parse(t):
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    for m in re.finditer(r"\{", t):
        try:
            d = json.loads(t[m.start():t.rfind("}") + 1])
            if "claims" in d: return d
        except Exception: pass
    return None

def resolve(path, metrics, nums):
    if path in nums: return nums[path]
    m = re.match(r"monthly\.(\d{4}-\d{2})\.(\w+)$", path)
    if m and m.group(1) in metrics["monthly"]: return metrics["monthly"][m.group(1)].get(m.group(2))
    return None

def run(metrics_path="out/metrics.json", out_path="out/panel.json"):
    metrics = json.load(open(metrics_path)); nums = flat(metrics); key = neb_key()
    msgs = [{"role": "user", "content": prompt(metrics)}]
    with cf.ThreadPoolExecutor(4) as ex:
        futs = {n: ex.submit(ask, mdl, key, msgs) for n, mdl in JUDGES.items()}
        raw = {n: f.result() for n, f in futs.items()}
    votes = {}
    for n, t in raw.items():
        d = parse(t)
        votes[n] = d if d else {"error": t[:500]}
    rec = []
    for c, side, text in CLAIMS:
        vs, ev, cav, bad = [], Counter(), [], []
        for n, d in votes.items():
            if "claims" not in d: continue
            x = next((y for y in d["claims"] if y.get("id") == c), None)
            if not x: continue
            vs.append((n, x.get("verdict", "").upper()))
            for p in x.get("evidence", []):
                (ev.update([p]) if resolve(p, metrics, nums) is not None else bad.append(p))
            cav.append((n, x.get("caveat", "")))
        cnt = Counter(v for _, v in vs)
        top, k = cnt.most_common(1)[0] if cnt else ("NONE", 0)
        rec.append({"id": c, "side": side, "claim": text, "votes": dict(vs), "verdict": top if k > len(vs) / 2 else "SPLIT",
                    "agreement": f"{k}/{len(vs)}", "evidence": [{"path": p, "value": resolve(p, metrics, nums), "cited_by": n} for p, n in ev.most_common(6)],
                    "rejected_citations": bad, "caveats": cav})
    res = {"as_of": metrics["as_of"], "judges": list(JUDGES), "claims": rec,
           "theses": {n: {"thesis": d.get("thesis"), "would_change_my_mind": d.get("would_change_my_mind")} for n, d in votes.items() if "claims" in d},
           "failed_judges": [n for n, d in votes.items() if "claims" not in d], "raw": raw}
    json.dump(res, open(out_path, "w"), indent=1)
    for r in rec: print(r["id"], r["verdict"], r["agreement"], r["votes"], "rejected:", r["rejected_citations"])
    print("failed:", res["failed_judges"])

if __name__ == "__main__":
    run()
