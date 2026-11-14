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
    calls = _fake_shots_check(episode, monkeypatch, [{"id": "char_never_visible:ch_a", "severity": "major", "status": "fail", "frame": 1, "message": "x"}])
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])
    assert len(calls) == 1 and State(episode).st("shots_check")["status"] == "needs_review"


def test_soft_scene_defects_are_reserves_not_blocks(episode, monkeypatch):
    """Tête coupée, profil… : réserves (listées), aucun tour de correction ni session Codex."""
    import studio.cli as cli
    from studio.state import ORDER
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "true")
    cli.CFG = None
    st = State(episode)
    for s in ORDER[:ORDER.index("shots_check")]:
        st.finish(s, "approved" if s.startswith("gate_") else "completed")
    _fake_shots_check(episode, monkeypatch, [{"id": "head_cropped:ch_a", "severity": "major", "status": "fail", "frame": 1, "message": "x"},
                                             {"id": "face_away:ch_a", "severity": "major", "status": "fail", "frame": 1, "message": "y"}])
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])
    assert State(episode).st("shots_check")["status"] == "completed"
    assert cli._qa_blockers(None, [{"id": "sh_001:head_cropped:ch_a", "severity": "major", "status": "fail", "category": "scene", "message": "m"}]) == []
    assert cli._qa_blockers(None, [{"id": "loudness", "severity": "major", "status": "fail", "category": "audio", "message": "m"}]) == []
    assert cli._qa_blockers(None, [{"id": "black_frames", "severity": "blocker", "status": "fail", "category": "technical", "message": "m"}])


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


def test_human_override_waives_blocked_review_and_is_recorded(episode, monkeypatch):
    """Revue bloquée après 2 tours (ex. droits) : l'humain tranche avec --override + note ; le blocage est levé,
    la décision consignée et le pilote n'est plus arrêté par ce `needs_review`."""
    import studio.cli as cli
    st = State(episode)
    for s in ("brief", "script"):
        st.finish(s)
    st.finish("script_review", "needs_review", note="F01 droits")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: episode.name)
    with pytest.raises(SystemExit):   # note obligatoire
        cli.main(["approve", episode.name, "gate_script", "--override"])
    with pytest.raises(SystemExit) as e:
        cli.main(["approve", episode.name, "gate_script", "--override", "--note", "parodie assumée, aucun visuel copié"])
    assert not e.value.code
    st = State(episode)
    assert st.st("gate_script")["status"] == "approved"
    assert st.st("script_review")["status"] == "completed"
    assert st.data["human_decisions"][0]["note"] == "parodie assumée, aucun visuel copié"
    assert "design" in st.ready()
    assert cli.next_summary(episode)["needs_review"] == []
    import importlib.util
    spec = importlib.util.spec_from_file_location("pilote", Path(__file__).resolve().parents[1] / "scripts" / "pilote.py")
    pil = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pil)
    prompt = pil.codex_prompt(episode.name, {"agent": [{"stage": "design", "owner": "character-artist", "outputs": ["cast_bible.json"]}], "review": [], "failed": {}})
    assert "DÉCISION HUMAINE" in prompt and "aucun visuel copié" in prompt


def _review(episode, rnd, findings, verdict="revise"):
    from studio.util import sha256_file
    r = {"contract": "review_report", "contract_version": "1.0", "episode_id": episode.name, "status": "draft",
         "provenance": {"created_by": "script-critic", "created_at": "2026-11-14T00:00:00Z"},
         "reviewer": "script-critic", "gate": "script", "round": rnd,
         "target": {"path": "story_script.json", "sha256": sha256_file(episode / "story_script.json")},
         "inspected": [{"path": "story_script.json", "method": "read_text"}],
         "scores": {"hook": {"score": 7, "rationale": "ok"}}, "findings": findings, "verdict": verdict, "limitations": "aucune"}
    (episode / "reviews").mkdir(exist_ok=True)
    f = episode / "reviews" / f"script-critic_script_r{rnd}.json"
    f.write_text(json.dumps(r, ensure_ascii=False))
    return f"reviews/{f.name}"


def _finding(fid, sev, owner="story-architect"):
    return {"id": fid, "severity": sev, "category": "clarte", "description": "d", "recommendation": "r", "fix_owner": owner}


def test_review_rules_notes_human_and_reserves(episode, monkeypatch):
    """Revues : major/minor = notes (pas de tour) ; blocker humain = arrêt immédiat ; budget épuisé = réserves."""
    import studio.cli as cli
    cli.CFG = None
    st = State(episode)
    for s in ("brief", "script"):
        st.finish(s)
    # 1) verdict « revise » mais aucune finding blocker : étape terminée, aucun tour
    rp = _review(episode, 1, [_finding("F01", "major"), _finding("F02", "minor")])
    try:
        cli.main(["submit", episode.name, "script_review", "--review", rp])
    except SystemExit:
        pass
    assert State(episode).st("script_review")["status"] == "completed"
    # 2) blocker « human » (droits) : décision humaine tout de suite, sans tour d'agents
    st = State(episode)
    st.st("script_review")["status"] = "pending"
    st.save()
    rp = _review(episode, 2, [_finding("F01", "blocker", "human")], "block")
    try:
        cli.main(["submit", episode.name, "script_review", "--review", rp])
    except SystemExit:
        pass
    s = State(episode).st("script_review")
    assert s["status"] == "needs_review" and "DÉCISION HUMAINE" in s["note"] and not s.get("revision_rounds")
    # 3) blocker d'agent persistant : 2 tours puis acceptation AVEC RÉSERVES (pas d'arrêt)
    st = State(episode)
    st.st("script_review").update(status="pending", revision_rounds=0)
    st.save()
    statuses = []
    for rnd in (3, 4, 5):
        rp = _review(episode, rnd, [_finding("F09", "blocker")])
        try:
            cli.main(["submit", episode.name, "script_review", "--review", rp])
        except SystemExit:
            pass
        statuses.append(State(episode).st("script_review")["status"])
    assert statuses == ["failed", "failed", "completed"], statuses
    assert "RÉSERVES" in State(episode).st("script_review")["note"]
    assert State(episode).data["reserves"][0]["items"][0].startswith("F09")


def test_retake_request_and_finishing_mode(episode, monkeypatch):
    """« Refaire ce plan » : demande consignée, visible par le pilote ; en mode finition, ni nouvelle critique ni
    nouveau passage des rédacteurs d'amont (seul le plan visé a changé)."""
    import studio.cli as cli
    from studio import retakes
    from studio.state import ORDER
    monkeypatch.setenv("STUDIO_QUALITY_AUTONOMOUS", "true")
    cli.CFG = None
    st = State(episode)
    for s in ORDER[:ORDER.index("compile")]:
        st.finish(s, "approved" if s.startswith("gate_") else "completed")
    with pytest.raises(ValueError):
        retakes.request(episode, "sh_002", "")
    rid = retakes.request(episode, "sh_002", "trop serré, montrer la cuisine")
    assert rid == "r001" and State(episode).data["finishing"] is True
    assert cli.next_summary(episode)["retakes"][0]["shot"] == "sh_002"
    # l'agent modifie le plan (storyboard) puis marque la retouche
    sb = json.loads((episode / "storyboard.json").read_text())
    sb["shots"][1]["camera"]["framing"] = "medium"
    (episode / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False))
    with pytest.raises(SystemExit) as e:
        cli.main(["retake-done", episode.name, "r001", "--note", "medium au lieu de close_up"])
    assert not e.value.code
    assert retakes.load(episode)[0]["status"] == "applied" and not cli.next_summary(episode)["retakes"]
    with pytest.raises(SystemExit):
        cli.main(["run", episode.name])   # s'arrête plus loin (pas de voix dans ce test), après le mode finition
    st = State(episode)
    for s in ("animation", "storyboard_review"):
        assert st.st(s)["status"] == "completed" and "finition" in (st.st(s).get("note") or ""), s
