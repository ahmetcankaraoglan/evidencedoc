#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ -x .venv/bin/python ]]; then
  evidence_python=.venv/bin/python
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -e '.[dev]'
  evidence_python=.venv/bin/python
fi
printf 'EvidenceDoc: http://127.0.0.1:8765\nStop: Control+C\n'
"$evidence_python" -m uvicorn evidencedoc.app:app --host 127.0.0.1 --port 8765
