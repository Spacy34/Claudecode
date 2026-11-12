"""Pilote : Codex n'est appelé que pour les étapes de jugement ; arrêt propre sans progrès (pas de boucle)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


POSIX = __import__("pytest").mark.skipif(os.name == "nt", reason="faux Codex en script shell (Linux/macOS)")


@POSIX
def test_pilot_stops_without_progress(tmp_path, episode):
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "codex").write_text("#!/bin/sh\necho codex-stub \"$@\"\ncat\n")   # consigne reçue sur stdin
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


@POSIX
def test_pilot_without_codex_stops_cleanly(tmp_path, episode):
    """PC sans Codex : le pilote s'arrête avec un message clair (code 6) au lieu de planter."""
    script = tmp_path / "s.txt"
    script.write_text("Une poule devient maire.\nBernadette: Cot cot !\n", encoding="utf-8")
    env = dict(os.environ, PATH=os.path.dirname(sys.executable) + os.pathsep + "/usr/bin:/bin")
    subprocess.run([sys.executable, "-m", "studio", "new", "ep_sans_codex", "--script-file", str(script)], check=True,
                   env=dict(env, PYTHONPATH=str(ROOT / "pipeline")), capture_output=True)
    if __import__("shutil").which("codex", path=env["PATH"]):
        import pytest
        pytest.skip("codex installé dans /usr/bin")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pilote.py"), "ep_sans_codex", "--max-tours", "3"],
                       env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 6, r.stdout[-800:]
    assert "Codex introuvable" in r.stdout


@POSIX
def test_launcher_start_stop_and_lock(tmp_path, episode, monkeypatch):
    """Lancement détaché, verrou « production en cours » (pas de double lancement), arrêt de l'arbre de processus."""
    import time
    from studio import launcher
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "codex").write_text("#!/bin/sh\ncat > /dev/null\nsleep 30\n")
    (stub / "codex").chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub}:{os.environ['PATH']}")
    ok, out = launcher.create_episode("ep_lance_t", "Une poule devient maire.\nBernadette: Cot cot !\n", mode="script")
    assert ok, out
    assert launcher.slug("La Poule à Paris.txt") == "ep_la_poule_a_paris"
    pid = launcher.start_pilot("ep_lance_t")
    deadline = time.time() + 20
    while not launcher.pilot_running("ep_lance_t") and time.time() < deadline:
        time.sleep(0.2)
    assert launcher.pilot_running("ep_lance_t")
    import pytest
    with pytest.raises(RuntimeError):
        launcher.start_pilot("ep_lance_t")
    assert launcher.stop_pilot("ep_lance_t")
    deadline = time.time() + 20
    while launcher.pilot_running("ep_lance_t") and time.time() < deadline:
        time.sleep(0.2)
    assert not launcher.pilot_running("ep_lance_t")
    assert "ARRÊT demandé" in launcher.journal("ep_lance_t").read_text(encoding="utf-8")
    assert pid > 0
