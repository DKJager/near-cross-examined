PY ?= python3
.PHONY: thesis numbers data panel page test
thesis: data numbers panel page
data:
	$(PY) fetch.py
numbers:
	mkdir -p out && $(PY) metrics.py
panel:
	$(PY) panel.py
page:
	$(PY) dashboard.py
test:
	$(PY) -m pytest -q tests
