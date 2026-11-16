"""Tests voix + compilation (sans Blender) — dont la logique du test H : une correction limitée ne change
que les specs des plans concernés (donc seuls ces plans seront re-rendus)."""
import json
import shutil

import pytest

from studio import audio, compile as comp, subtitles
from studio.util import read_json

needs_espeak = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")


def test_word_timings_monotonic():
    w = audio.word_timings("Le grille-pain a commencé à vibrer.".split(), 1.0, 3.0)
    assert w[0]["start_s"] == 1.0 and all(a["end_s"] <= b["start_s"] + 1e-6 for a, b in zip(w, w[1:]))
    assert w[-1]["end_s"] <= 3.0


@needs_espeak
def test_voice_compile_and_targeted_invalidation(episode, cfg):
    r = audio.build_voice(episode, cfg)
    assert r["synthesized_lines"] == 9
    tl = read_json(episode / "audio_timeline.json")
    starts = [s["start_s"] for s in tl["segments"]]
    assert starts == sorted(starts) and tl["duration_s"] > 20
    m1 = comp.compile_episode(episode, cfg)
    assert m1["total_frames"] == int(-(-tl["duration_s"] * 30 // 1))
    assert m1["shots"][0]["start_frame"] == 0 and m1["shots"][-1]["end_frame"] == m1["total_frames"]
    for a, b in zip(m1["shots"], m1["shots"][1:]):
        assert a["end_frame"] == b["start_frame"]
    # correction limitée : une expression d'un seul plan
    ap = read_json(episode / "animation_plan.json")
    ap["shots"]["sh_004"].setdefault("fx", []).append({"type": "sparkles", "at": {"line": "l004", "word": 3}, "target": "pr_toaster"})
    (episode / "animation_plan.json").write_text(json.dumps(ap, ensure_ascii=False))
    m2 = comp.compile_episode(episode, cfg)
    changed = [a["id"] for a, b in zip(m1["shots"], m2["shots"]) if a["spec_sha256"] != b["spec_sha256"]]
    assert changed == ["sh_004"]
    # modification d'une réplique : la compilation refuse une timeline obsolète, la voix ne resynthétise qu'elle
    sc = read_json(episode / "story_script.json")
    sc["lines"][7]["text"] = "La vidéo a fait quatre millions de vues."
    (episode / "story_script.json").write_text(json.dumps(sc, ensure_ascii=False))
    with pytest.raises(comp.CompileError):
        comp.compile_episode(episode, cfg)
    assert audio.build_voice(episode, cfg)["synthesized_lines"] == 1
    comp.compile_episode(episode, cfg)


@needs_espeak
def test_subtitles_ass(episode, cfg, tmp_path):
    audio.build_voice(episode, cfg)
    tl = read_json(episode / "audio_timeline.json")
    n = subtitles.build_ass(tl, cfg, tmp_path / "s.ass", 0, 8.0)
    txt = (tmp_path / "s.ass").read_text()
    assert n > 5 and "PlayResY: 1920" in txt and "COLOC" in txt
