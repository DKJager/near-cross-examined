"""Sample NEAR Intents 1Click swap activity: one full UTC day per week (Sundays) for the last 52 weeks.
Explorer API (JWT from the NEAR Intents Partner Dashboard in env INTENTS_JWT, or AWS secret 3dogs/near-intents-jwt).
Rate limit is 1 request / 5 s, so this takes ~45 minutes. Resumable: finished days are kept in data/intents_days.json."""
import json, os, time, datetime as dt, urllib.request, urllib.error

API = "https://explorer.near-intents.org/api/v0/transactions"
OUT = "data/intents_days.json"

def jwt():
    v = os.environ.get("INTENTS_JWT")
    if v: return v.strip()
    import boto3
    return boto3.client("secretsmanager", region_name="us-east-2").get_secret_value(SecretId="3dogs/near-intents-jwt")["SecretString"].strip()

def get(q, key):
    for a in range(6):
        try:
            r = urllib.request.Request(API + "?" + q, headers={"Authorization": "Bearer " + key})
            return json.load(urllib.request.urlopen(r, timeout=90))
        except urllib.error.HTTPError as e:
            time.sleep(15 if e.code == 429 else 10)
        except Exception:
            time.sleep(10)
    raise RuntimeError("failed " + q)

def day_stats(day, key):
    s = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp()); e = s + 86400 - 1
    n = 0; usd = 0.0; chains = {}; last = None; pages = 0
    while True:
        q = f"numberOfTransactions=1000&statuses=SUCCESS&startTimestampUnix={s}&endTimestampUnix={e}"
        if last: q += "&lastDepositAddress=" + urllib.request.quote(last["depositAddress"]) + ("&lastDepositMemo=" + urllib.request.quote(last["depositMemo"]) if last.get("depositMemo") else "")
        d = get(q, key); pages += 1; time.sleep(5.2)
        for x in d:
            n += 1; u = float(x.get("amountInUsd") or 0); usd += u
            c = (x.get("originAsset") or "").split(":")[1].split("-")[0] if ":" in (x.get("originAsset") or "") else "?"
            chains[c] = chains.get(c, 0) + u
        if len(d) < 1000: break
        last = d[-1]
    top = sorted(chains.items(), key=lambda kv: -kv[1])[:5]
    return {"date": day.isoformat(), "swaps": n, "usd": usd, "pages": pages, "top_origin": top}

def main(weeks=52):
    key = jwt(); os.makedirs("data", exist_ok=True)
    done = {d["date"]: d for d in json.load(open(OUT))} if os.path.exists(OUT) else {}
    today = dt.datetime.now(dt.timezone.utc).date()
    last_sun = today - dt.timedelta(days=(today.weekday() + 1) % 7 or 7)
    days = [last_sun - dt.timedelta(weeks=i) for i in range(weeks)]
    for d in sorted(days):
        if d.isoformat() in done: continue
        done[d.isoformat()] = day_stats(d, key)
        json.dump(sorted(done.values(), key=lambda r: r["date"]), open(OUT, "w"), indent=1)
        print(done[d.isoformat()]["date"], done[d.isoformat()]["swaps"], round(done[d.isoformat()]["usd"]), flush=True)

if __name__ == "__main__":
    main()
