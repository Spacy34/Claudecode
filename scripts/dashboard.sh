#!/usr/bin/env bash
# Tableau de bord du studio : http://127.0.0.1:8765 (sur un VPS : tunnel SSH, voir VPS.md).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
exec env STUDIO_PYTHON="$PY" "$ROOT/scripts/studio" dashboard "$@"
