"""Pilote : Codex n'est appelé que pour les étapes de jugement ; arrêt propre sans progrès (pas de boucle)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pilot_stops_without_progress(tmp_path, episode):
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "codex").write_text("#!/bin/sh\necho codex-stub \"$@\"\n")
    (stub / "codex").chmod(0o755)
    script = tmp_path / "s.txt"
    script.write_text("Une poule devient maire.\nBernadette: Cot cot !\n", encoding="utf-8")
    env = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}")
    subprocess.run([str(ROOT / "scripts" / "studio"), "new", "ep_pilote_t", "--script-file", str(script)], check=True, env=env, capture_output=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pilote.py"), "ep_pilote_t", "--max-tours", "6"],
                       env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 4, r.stdout[-800:]
    journal = (Path(os.environ["STUDIO_PATHS_EPISODES_DIR"]) / "ep_pilote_t" / "checks" / "codex_journal.log").read_text()
    assert "étape `script`" in journal and "script IMPOSÉ" in journal
    assert "studio run" in journal and "ne lances PAS" in journal
