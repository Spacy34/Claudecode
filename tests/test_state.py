"""Test J (logique) — état persistant, interruption, péremption, validations liées aux hashes."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from studio.state import State


def test_interrupted_stage_detected(episode):
    st = State(episode)
    st.finish("brief")
    st.st("script").update(status="running", pid=999999)   # ancien job sans verrou (crash simulé)
    st.save()
    st2 = State(episode)
    changes = st2.refresh()
    assert ("script", "interrupted") in changes
    assert "script" in st2.ready()


def test_stale_propagation_on_input_change(episode):
    st = State(episode)
    for s in ("brief", "script", "script_review"):
        st.finish(s)
    st.approve("gate_script", "human")
    st.finish("design")
    assert st.approval_valid("gate_script")
    sc = json.loads((episode / "story_script.json").read_text())
    sc["lines"][0]["text"] += " Vraiment."
    (episode / "story_script.json").write_text(json.dumps(sc, ensure_ascii=False))
    st.refresh()
    assert st.st("script_review")["status"] == "stale"
    assert st.st("gate_script")["status"] == "stale"
    assert not st.approval_valid("gate_script"), "une validation humaine ne survit pas à une modification"
    st.refresh()
    assert st.st("design")["status"] == "stale"


def test_approve_requires_artifacts(episode):
    (episode / "story_script.json").unlink()
    with pytest.raises(RuntimeError):
        State(episode).approve("gate_script", "human")


def test_autonomous_mode_auto_approves_and_refuses(episode, monkeypatch):
    """Mode autonome : gate validée seule après revue approuvée ; refusée si la QA requise manque."""
    import studio.cli as cli
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "true")
    cli.CFG = None
    st = State(episode)
    for s in ("brief", "script", "script_review"):
        st.finish(s)
    assert cli.human_gates() == []
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name, "--until", "gate_script"])
    st = State(episode)
    assert st.st("gate_script")["status"] == "approved"
    assert st.approval_valid("gate_script")
    assert st.data["approvals"][-1]["by"] == "auto:studio"
    ok, why = cli.auto_gate_ok(episode, "gate_prototype")
    assert not ok and "qa_prototype" in why


def test_human_mode_never_auto_approves(episode, monkeypatch):
    import studio.cli as cli
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "false")
    cli.CFG = None
    st = State(episode)
    for s in ("brief", "script", "script_review"):
        st.finish(s)
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])
    assert State(episode).st("gate_script")["status"] == "pending"


def test_autonomous_qa_refusal_gives_correction_rounds(episode, monkeypatch):
    """QA bloquante : 2 tours de correction (défaut + rôle responsable transmis), puis arrêt pour humain."""
    import json as _j
    import studio.cli as cli
    from studio.state import ORDER
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "true")
    cli.CFG = None
    st = State(episode)
    for s in ORDER[:ORDER.index("gate_prototype")]:
        st.finish(s, "approved" if s.startswith("gate_") else "completed")
    qa = {"checks": [{"id": "sh_002:char_never_visible:ch_chloe", "category": "scene", "severity": "major", "status": "fail",
                      "message": "sh_002 : ch_chloe jamais visible", "method": "blender_scene_check"}],
          "summary": {"blocking": True}}
    (episode / "qa_prototype.json").write_text(_j.dumps(qa))
    statuses = []
    for _ in range(3):
        try:
            cli.main(["run", episode.name])
        except SystemExit:
            pass
        s = State(episode).st("gate_prototype")
        statuses.append((s["status"], s.get("revision_rounds")))
    assert statuses == [("failed", 1), ("failed", 2), ("needs_review", 3)], statuses
    err = State(episode).st("gate_prototype")
    assert "[director] sh_002:char_never_visible" in (err.get("note") or err.get("error") or "")


def test_concurrent_status_preserves_active_stage_then_recovers_after_crash(episode, tmp_path):
    """Contribution de Codex (VPS) : un `status` lancé ailleurs ne déclare pas « interrompue » une étape en cours ;
    après la mort du processus (verrou relâché par l'OS), elle l'est bien."""
    st = State(episode)
    st.finish("brief")
    ready = tmp_path / "ready"
    code = ("import pathlib,sys,time; from studio.state import State; "
            "job=State(pathlib.Path(sys.argv[1])); job.start('script'); "
            "pathlib.Path(sys.argv[2]).write_text('ready'); time.sleep(60)")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "pipeline"))
    proc = subprocess.Popen([sys.executable, "-c", code, str(episode), str(ready)], env=env)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "le processus simulé n'a pas démarré"
        observer = State(episode)
        assert observer.refresh() == []
        assert observer.st("script")["status"] == "running"
        assert "script" not in observer.ready()
        with pytest.raises(RuntimeError, match="déjà exécutée"):
            State(episode).start("script")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    observer = State(episode)
    assert ("script", "interrupted") in observer.refresh()
    assert "script" in observer.ready()


def test_legacy_running_record_without_lock_is_interrupted(episode):
    st = State(episode)
    st.finish("brief")
    st.st("script").update(status="running", pid=os.getpid())
    st.save()
    assert ("script", "interrupted") in State(episode).refresh()


def _fake_shots_check(episode, monkeypatch, checks):
    """shots_check sans Blender : rendus simulés renvoyant les contrôles donnés."""
    import studio.cli as cli
    lid = json.loads((episode / "story_script.json").read_text())["lines"][0]["id"]
    fdir = episode / "_fake_frames"
    fdir.mkdir(exist_ok=True)
    (fdir / "f0001.png").write_bytes(b"png")
    man = {"episode_id": episode.name, "shots": [{"id": "sh_008", "frames": 2, "line_ids": [lid], "start_s": 0.0, "end_s": 1.0}]}
    calls = []
    monkeypatch.setattr(cli, "_manifest", lambda p: man)
    monkeypatch.setattr(cli.render, "render_shots", lambda *a, **k: calls.append(1) or
                        [{"status": "rendered", "frames_dir": str(fdir), "scene_report": {"checks": checks, "rendered_frames": [1]}}])
    monkeypatch.setattr(cli.qframes, "contact_sheet", lambda items, out, **k: out)
    return calls


def test_shots_check_defects_never_loop_and_give_correction_rounds(episode, monkeypatch):
    """Bug VPS : shots_check en needs_review était relancé à l'infini par `studio run`. En autonome : tours de
    correction transmis au pilote (rôle responsable), puis escalade ; jamais plus d'une exécution par `run`."""
    import studio.cli as cli
    from studio.state import ORDER
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "true")
    cli.CFG = None
    st = State(episode)
    for s in ORDER[:ORDER.index("shots_check")]:
        st.finish(s, "approved" if s.startswith("gate_") else "completed")
    calls = _fake_shots_check(episode, monkeypatch, [{"id": "char_never_visible:ch_dylan", "severity": "major", "status": "fail",
                                                       "frame": 1, "message": "ch_dylan jamais visible"}])
    statuses = []
    for _ in range(3):
        with pytest.raises(SystemExit):
            cli.main(["run", episode.name])
        s = State(episode).st("shots_check")
        statuses.append((s["status"], s.get("revision_rounds")))
    assert len(calls) == 3, "une seule exécution de shots_check par `studio run`"
    assert statuses == [("failed", 1), ("failed", 2), ("needs_review", 3)], statuses
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])
    assert len(calls) == 3, "needs_review : attendre la correction, ne pas relancer"


def test_shots_check_human_mode_stops_once(episode, monkeypatch):
    import studio.cli as cli
    from studio.state import ORDER
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "false")
    cli.CFG = None
    st = State(episode)
    for s in ORDER[:ORDER.index("shots_check")]:
        st.finish(s, "approved" if s.startswith("gate_") else "completed")
    calls = _fake_shots_check(episode, monkeypatch, [{"id": "head_cropped:ch_a", "severity": "major", "status": "fail", "frame": 1, "message": "x"}])
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])
    assert len(calls) == 1 and State(episode).st("shots_check")["status"] == "needs_review"


def test_new_optional_input_does_not_invalidate_existing_episode(episode):
    """Ajout de motion_design.json aux entrées de first_cut : un épisode déjà avancé ne devient pas périmé."""
    from studio.state import ORDER
    st = State(episode)
    for s_ in ORDER[:ORDER.index("first_cut") + 1]:
        st.finish(s_, "approved" if s_.startswith("gate_") else "completed")
    old = dict(st.st("first_cut")["inputs"])
    old.pop("motion_design.json")          # état enregistré avant l'existence de motion_design.json
    st.st("first_cut")["inputs"] = old
    st.save()
    st = State(episode)
    assert not [c for c in st.refresh() if c[0] == "first_cut"]
    assert st.st("first_cut")["status"] == "completed"
    (episode / "motion_design.json").write_text("{}")
    st = State(episode)
    assert ("first_cut", "stale:inputs") in st.refresh(), "une fois créé, motion_design.json invalide bien le montage"
