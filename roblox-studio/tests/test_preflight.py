"""Pré-vérification (studio preflight), rééquilibrage des cadrages, figurants et réactions d'écoute."""

import shutil

import pytest

from conftest import has_blender
from studio import audio, preflight, render
from studio.compile import OPEN, balance_framings, compile_episode
from studio.util import read_json, sha256_json, write_json


def _shot(i, framing, set_id="set_a", n_lines=1, chars=1, secondary=False):
    cam = {"framing": framing}
    if secondary:
        cam["secondary_subject"] = "ch_b"
    return {"id": f"sh_{i:03d}", "set_id": set_id, "line_ids": [f"l{i}{k}" for k in range(n_lines)],
            "characters": [{"id": f"ch_{k}"} for k in range(chars)], "camera": cam}


def test_balance_opens_each_new_set_and_avoids_tight_chains():
    shots = [_shot(0, "close_up"), _shot(1, "close_up"), _shot(2, "medium_close"),
             _shot(3, "medium", set_id="set_b", chars=2), _shot(4, "close_up", set_id="set_b")]
    w = []
    fr = balance_framings(shots, {"quality": {"min_open_ratio": 0.0}}, w)
    assert fr[0] == "close_up", "le premier plan (accroche) n'est jamais touché"
    assert fr[3] == "wide", "changement de décor -> plan d'installation"
    tight = ("close_up", "extreme_close_up", "medium_close")
    assert not any(fr[i] in tight and fr[i - 1] in tight for i in range(1, len(fr)))
    assert w and all("élargi" in x for x in w)


def test_balance_reaches_open_ratio_by_widening_longest_shots():
    shots = [_shot(0, "medium"), _shot(1, "medium", n_lines=3, chars=2, secondary=True), _shot(2, "medium_close"),
             _shot(3, "medium", n_lines=2), _shot(4, "insert"), _shot(5, "medium")]
    fr = balance_framings(shots, {"quality": {"min_open_ratio": 0.4}}, [])
    assert sum(f in OPEN for f in fr) >= 0.4 * len(fr)
    assert fr[1] == "two_shot" and fr[3] == "full", "les plans les plus longs sont élargis en premier"
    assert fr[4] == "insert", "un insert reste un insert"


def test_balance_can_be_disabled():
    shots = [_shot(0, "close_up"), _shot(1, "close_up"), _shot(2, "close_up")]
    assert balance_framings(shots, {"quality": {"framing_balance": False}}, []) == ["close_up"] * 3


def test_preflight_blocks_on_contract_error_without_touching_episode(episode, cfg):
    sb = read_json(episode / "storyboard.json")
    sb["shots"][0]["characters"][0]["id"] = "ch_inconnu"
    write_json(episode / "storyboard.json", sb)
    before = sorted(p.name for p in episode.iterdir())
    rep = preflight.run(episode, cfg, with_3d=False)
    assert rep["ok"] is False and any("ch_inconnu" in b or "inconnu" in b for b in rep["blocking"])
    assert (episode / "checks" / "preflight.json").exists()
    assert sorted(p.name for p in episode.iterdir() if p.name != "checks") == [x for x in before if x != "checks"]
    assert not (episode / "shot_manifest.json").exists(), "la pré-vérification ne compile jamais dans l'épisode"


needs_voice = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")


@needs_voice
def test_preflight_dry_compile_ok_on_demo(episode, cfg):
    audio.build_voice(episode, cfg)
    rep = preflight.run(episode, cfg, with_3d=False)
    assert rep["ok"], rep["blocking"]
    st = rep["stats"]
    assert st["plans"] == 10 and "/" in st["decor_visible"]
    assert not (episode / "shot_manifest.json").exists() and not (episode / "shots").exists()


@needs_voice
def test_storyboard_extras_pass_validation_and_compile(episode, cfg, tmp_path):
    sb = read_json(episode / "storyboard.json")
    sb["shots"][6]["extras"] = {"count": 3, "activity": "chat", "zone": "back"}
    write_json(episode / "storyboard.json", sb)
    audio.build_voice(episode, cfg)
    man = compile_episode(episode, cfg, out_dir=tmp_path / "c")
    spec = read_json(tmp_path / "c" / man["shots"][6]["spec_path"])
    assert spec["extras"]["count"] == 3 and spec["extras"]["activity"] == "chat" and "seed" in spec["extras"]
    sb["shots"][6]["extras"]["count"] = 40
    write_json(episode / "storyboard.json", sb)
    rep = preflight.run(episode, cfg, with_3d=False)
    assert not rep["ok"], "count hors bornes refusé par le schéma"




@pytest.mark.blender
@pytest.mark.skipif(not has_blender(), reason="Blender indisponible")
@needs_voice
def test_extras_and_listener_reactions_in_scene(episode, cfg):
    """Figurants placés derrière l'action et ignorés par les contrôles ; l'écoutant regarde celui qui parle."""
    audio.build_voice(episode, cfg)
    man = compile_episode(episode, cfg)
    s = next(x for x in man["shots"] if x["id"] == "sh_008")
    spec = read_json(episode / s["spec_path"])
    a, b = [c["id"] for c in spec["characters"]][:2]
    for c in spec["characters"]:
        c.pop("facing_target", None)
        c["facing_deg"] = 0.0
    spec["talk"] = [{"char": a, "words": [[5, 20], [22, 40], [42, 58]]}]
    spec["extras"] = {"count": 3, "activity": "chat", "zone": "back", "seed": 1234}
    write_json(episode / "shots" / "rich.json", spec)
    rec = render.render_shot(cfg, episode, {"id": "sh_008", "spec_path": "shots/rich.json", "spec_sha256": sha256_json(spec),
                                            "frames": spec["frames"]}, "draft", mode="checks")
    assert rec["status"] == "rendered", rec.get("error")
    rep = rec["scene_report"]
    ex = [x for x in rep.get("adjustments", []) if x["type"] == "extras"]
    assert ex and ex[0]["placed"] >= 1, rep.get("adjustments")
    assert not [c for c in rep["checks"] if ":ex" in c["id"]], "les figurants ne sont jamais contrôlés"
    assert any(e.get("what") == f"écoute {a}" and e["char"] == b for e in rep["events"]), rep["events"]
    assert not [c for c in rep["checks"] if c["id"] == f"face_away:{b}"], "l'écoutant garde le visage lisible"
