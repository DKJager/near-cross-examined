"""Download the raw data: NearBlocks daily charts (public, no key)."""
import urllib.request, json, os, time
os.makedirs("data", exist_ok=True)
for name, url in [("charts_raw.json", "https://api.nearblocks.io/v1/charts"), ("stats_raw.json", "https://api.nearblocks.io/v1/stats")]:
    req = urllib.request.Request(url, headers={"User-Agent": "near-cross-examined/1.0"})
    b = urllib.request.urlopen(req, timeout=120).read()
    json.loads(b)
    open(os.path.join("data", name), "wb").write(b)
    print(name, len(b), "bytes", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
