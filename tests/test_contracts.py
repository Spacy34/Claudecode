"""Test D — les contrats d'exemple traversent la validation ; les erreurs sont réellement détectées."""
import copy
import json

from studio import contracts
from conftest import DEMO


def test_demo_episode_valid():
    rep = contracts.validate_episode(DEMO)
    assert {k: v for k, v in rep.items() if v} == {}


def test_schema_vocab_matches_engine():
    assert contracts.capability_errors() == []


def test_schema_rejects_unknown_action():
    ap = json.loads((DEMO / "animation_plan.json").read_text())
    ap["shots"]["sh_001"]["actions"][0]["action"] = "moonwalk"
    assert any("moonwalk" in e for e in contracts.schema_errors("animation_plan", ap))


def test_cross_rules_detect_desync():
    arts = contracts.load_episode(DEMO)
    a = copy.deepcopy(arts)
    a["story_script"]["lines"] = a["story_script"]["lines"][:-1]          # réplique supprimée
    errs = contracts.cross_errors(a)
    assert any("réplique inconnue l009" in e for e in errs)
    b = copy.deepcopy(arts)
    b["animation_plan"]["shots"]["sh_002"]["actions"][0]["at"]["word"] = 99   # mot hors réplique
    assert any("mot 99" in e for e in contracts.cross_errors(b))
    c = copy.deepcopy(arts)
    c["storyboard"]["shots"][0]["characters"][0]["id"] = "ch_inconnu"
    assert any("personnage inconnu" in e for e in contracts.cross_errors(c))


def test_review_report_schema():
    r = {"contract": "review_report", "contract_version": "1.0", "episode_id": "ep_demo_grillepain", "status": "draft",
         "provenance": {"created_by": "visual-critic", "created_at": "2026-11-10T00:00:00Z"}, "reviewer": "visual-critic",
         "gate": "prototype", "round": 1, "target": {"path": "renders/prototype.mp4", "sha256": "0" * 64},
         "inspected": [{"path": "checks/frames_prototype/contact.png", "method": "view_image"}],
         "scores": {"lisibilite_mobile": {"score": 6, "rationale": "ok"}},
         "findings": [{"id": "F01", "severity": "major", "category": "cadrage", "shot_id": "sh_001", "time_s": 1.2,
                       "description": "x", "recommendation": "y", "fix_owner": "director"}],
         "verdict": "revise", "limitations": "aucune"}
    assert contracts.schema_errors("review_report", r) == []
    r["inspected"] = []
    assert contracts.schema_errors("review_report", r)
