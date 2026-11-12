"""Supervision du processus Blender (contribution de Codex, VPS) : ne pas attendre un Blender bloqué après succès."""
import sys
import time

from studio.render import _run_until_done


def test_completed_render_does_not_wait_for_stuck_blender(tmp_path):
    done = tmp_path / "done.json"
    command = [sys.executable, "-c", "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('{}'); time.sleep(30)", str(done)]
    started = time.monotonic()
    with (tmp_path / "render.log").open("w") as output:
        assert _run_until_done(command, output, done, timeout_s=10, exit_grace_s=0.1) == 0
    assert done.exists()
    assert time.monotonic() - started < 3


def test_incomplete_render_keeps_failure_and_timeout(tmp_path):
    done = tmp_path / "done.json"
    with (tmp_path / "render.log").open("w") as output:
        assert _run_until_done([sys.executable, "-c", "import sys; sys.exit(7)"], output, done, timeout_s=2) == 7
    with (tmp_path / "render.log").open("w") as output:
        assert _run_until_done([sys.executable, "-c", "import time; time.sleep(30)"], output, done, timeout_s=0.1) == -999
