# verify: no key, no network. With the full local data it rebuilds every number; from a fresh clone (the source files are not shipped) it checks the derived numbers against their recorded hashes, rebuilds the BigQuery numbers, and checks the citations and documents. verify-online re-fetches every source and rebuilds all the numbers.
PY ?= python3
.PHONY: verify verify-online thesis numbers data csv panel page docs score test
verify:
	@$(PY) -c "import pytest" 2>/dev/null || { echo "make verify needs pytest. Install it first: python3 -m venv .venv && . .venv/bin/activate && pip install pytest   then run make verify again"; exit 1; }
	$(PY) -m pytest -q tests
	$(PY) verify.py
	$(PY) thesis_doc.py --check
	$(PY) score.py
	$(PY) score.py --forecasts tripwires.json
verify-online:
	$(PY) verify_online.py
# Full rebuild: needs the internet, and an OpenAI-compatible key in NEBIUS_API_KEY for the panel.
thesis: data numbers panel page docs
data:
	$(PY) fetch.py
	$(PY) export_csv.py
csv:
	$(PY) export_csv.py
numbers:
	mkdir -p out && $(PY) metrics.py && $(PY) verify.py --record
panel:
	$(PY) panel.py
page:
	$(PY) dashboard.py
docs:
	$(PY) thesis_doc.py
score:
	$(PY) score.py && $(PY) score.py --forecasts tripwires.json
test:
	$(PY) -m pytest -q tests
