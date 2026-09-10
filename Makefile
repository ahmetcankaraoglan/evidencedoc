.PHONY: install run test
install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e '.[dev]'
run:
	.venv/bin/python -m uvicorn evidencedoc.app:app --host 127.0.0.1 --port 8765
test:
	.venv/bin/python -m pytest -q
