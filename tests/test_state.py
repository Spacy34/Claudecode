"""Test J (logique) — état persistant, interruption, péremption, validations liées aux hashes."""
import json

import pytest

from studio.state import State


def test_interrupted_stage_detected(episode):
    st = State(episode)
    st.finish("brief")
    st.start("script")
    st.st("script")["pid"] = 999999          # processus disparu (crash simulé)
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
