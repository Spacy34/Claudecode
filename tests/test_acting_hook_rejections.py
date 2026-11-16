"""Bouche par son, journal des refus, accroche automatique, postures (sans Blender) ; objets posés (avec Blender)."""
import json
import shutil

import pytest

from conftest import has_blender
from studio import motion, rejections, visemes
from studio.state import State
from studio.util import read_json, sha256_json, write_json


# ------------------------------------------------------------------ visèmes
def test_french_visemes():
    assert visemes.phonemes("bonjour") == ["M", "O", "U"]
    assert visemes.phonemes("une") == ["U"], "e muet final, « un » non nasal devant voyelle"
    assert visemes.phonemes("pomme") == ["M", "O", "M"]
    assert visemes.phonemes("fille")[0] == "F"
    assert visemes.phonemes("123") == []


def test_word_visemes_timing_and_rest():
    v = visemes.word_visemes("beaucoup", 1.0, 1.4, 24)
    assert [x[1] for x in v] == ["M", "O", "U", "M"] and v[0][0] == 1.0 and all(a[0] < b[0] for a, b in zip(v, v[1:]))
    fast = visemes.word_visemes("extraordinaire", 0.0, 0.15, 24)
    assert len(fast) <= 2 and all(s in visemes.VOWELS for _, s in fast), "débit trop rapide : voyelles seulement"
    seq = visemes.for_words([{"text": "salut", "start_s": 0.0, "end_s": 0.3}, {"text": "toi", "start_s": 0.9, "end_s": 1.1}], 24)
    assert ("rest" in [s for _, s in seq]) and seq[-1][1] == "rest", "la bouche revient à l'expression dans les pauses"


# ------------------------------------------------------------------ journal des refus
def test_rejection_parsing_and_summary(tmp_path):
    ep = tmp_path / "ep_x"
    ep.mkdir()
    st = State(ep)
    st.fail("storyboard", "pré-vérification : [sh_003] char_never_visible:ch_a : jamais visible | [sh_004] char_never_visible:ch_b : idem")
    st.fail("shots_check", "tour 1 : corriger (sans rendu) puis le pilote revérifie. [animator] sh_002:prop_in_character:pr_x:ch_k : tête")
    st.fail("storyboard", json.dumps({"storyboard": ["sh_002 : personnage inconnu ch_zz"]}))
    rejections.record_review(ep, "review_script", {"reviewer": "script-critic"},
                             [{"id": "F01", "category": "clarity", "description": "chute incompréhensible", "fix_owner": "story-architect"}])
    (ep / "checks" / "codex_tokens.jsonl").write_text(
        json.dumps({"at": "2000-01-01T00:00:00+00:00", "started": "2000-01-01T00:00:00+00:00", "stages": ["storyboard"], "tokens": 1000}) + "\n"
        + json.dumps({"at": "2999-01-01T00:00:00+00:00", "started": "2999-01-01T00:00:00+00:00", "stages": ["storyboard"], "tokens": 400}) + "\n")
    s = rejections.summary([ep])
    top = {m["motif"]: m["fois"] for m in s["top_motifs"]}
    assert top["char_never_visible"] == 2 and top["prop_in_character"] == 1 and top["script-critic/clarity"] == 1
    assert s["tokens_total"] == 1400 and s["tokens_corrections"] == 400, "seule la session APRÈS un refus est une correction"
    assert "char_never_visible" in rejections.format_text(s)


def test_review_refusal_is_not_double_counted(tmp_path):
    ep = tmp_path / "ep_y"
    ep.mkdir()
    State(ep).fail("script_review", "verdicts ['revise'], 1 bloquant(s) : corriger puis re-soumettre (tour 1)")
    assert rejections.load(ep) == [], "les critiques sont détaillés par record_review, pas par l'erreur générique"


# ------------------------------------------------------------------ accroche
def test_hook_title_injected_and_switchable(episode, monkeypatch):
    md = motion.load(episode)
    hook = md["elements"][0]
    assert hook["id"] == "mo_hook" and hook["style"] == "banner" and hook["at"]["word"] == 0
    assert hook["text"] == read_json(episode / "story_script.json")["hook"]["on_screen_text"]
    assert all(e["id"] != "mo_hook" for e in (motion.load(episode, with_hook=False) or {}).get("elements", []))
    from studio import util
    real = util.load_config

    def no_hook():
        c = real()
        c.setdefault("hook", {})["title"] = False
        return c
    monkeypatch.setattr(util, "load_config", no_hook)
    assert all(e["id"] != "mo_hook" for e in (motion.load(episode) or {}).get("elements", []))


def test_hook_title_survives_declutter_even_if_it_echoes_the_voice():
    tl = {"segments": [{"line_id": "l001", "start_s": 0.2, "end_s": 2.0,
                        "words": [{"text": w, "start_s": 0.2 + 0.3 * i, "end_s": 0.4 + 0.3 * i} for i, w in enumerate("mon grille-pain veut devenir une star".split())]}],
          "duration_s": 3.0}
    el = {"id": "mo_hook", "type": "text_pop", "_hook": True, "text": "Mon grille-pain veut devenir une star", "_t0": 0.2, "_t1": 2.1, "_msgs": []}
    kept, dropped = motion.declutter([el], tl)
    assert [e["id"] for e in kept] == ["mo_hook"] and not dropped


def test_no_sound_at_opening_by_default(tmp_path):
    """Retour utilisateur : le premier bruit (son d'attaque) était beaucoup trop fort -> aucun bruitage auto en ouverture."""
    from studio import sound_design
    from studio.util import load_config
    cfg = load_config()
    cues = sound_design.auto_cues(tmp_path, [], {"segments": [], "duration_s": 5}, cfg)
    assert not any(c["source"] == "auto:accroche" for c in cues)
    cfg.setdefault("hook", {})["sound"] = True   # réactivable volontairement
    cues = sound_design.auto_cues(tmp_path, [], {"segments": [], "duration_s": 5}, cfg)
    assert any(c["source"] == "auto:accroche" and c["start_s"] == 0.0 for c in cues)


def test_hook_title_appears_silently(episode, cfg):
    from studio import audio, sound_design
    from studio.compile import compile_episode
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng absent")
    audio.build_voice(episode, cfg)
    man = compile_episode(episode, cfg)
    tl = read_json(episode / "audio_timeline.json")
    cues = sound_design.auto_cues(episode, man["shots"], tl, cfg)
    assert not [c for c in cues if c["start_s"] < 0.6], [c for c in cues if c["start_s"] < 0.6]


needs_voice = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")


@needs_voice
def test_first_shot_never_static_and_visemes_compiled(episode, cfg, tmp_path):
    from studio import audio
    from studio.compile import compile_episode
    sb = read_json(episode / "storyboard.json")
    sb["shots"][0]["camera"]["move"] = "static"
    write_json(episode / "storyboard.json", sb)
    audio.build_voice(episode, cfg)
    man = compile_episode(episode, cfg, out_dir=tmp_path / "c")
    first = read_json(tmp_path / "c" / man["shots"][0]["spec_path"])
    assert first["camera"]["move"] == "push_in" and any("push_in automatique" in w for w in man["warnings"])
    talk = [t for s in man["shots"] for t in read_json(tmp_path / "c" / s["spec_path"])["talk"]]
    assert talk and all(t["visemes"] for t in talk) and {v[1] for t in talk for v in t["visemes"]} <= set(visemes.SHAPES) | {"rest"}
    spec_chars = [c for s in man["shots"] for c in read_json(tmp_path / "c" / s["spec_path"])["characters"]]
    assert any(c.get("acting", {}).get("posture") for c in spec_chars), "la posture du cast_bible arrive au moteur"


# ------------------------------------------------------------------ moteur (Blender)
@pytest.mark.blender
@pytest.mark.skipif(not has_blender(), reason="Blender indisponible")
@needs_voice
def test_props_settle_on_support_and_acting_runs(episode, cfg):
    """Empilement enceinte -> grille-pain -> tartine posé avec des hauteurs fausses : tout repose sur son support,
    aucun objet flottant ; posture + business automatique présents dans le rapport."""
    from studio import audio, render
    from studio.compile import compile_episode
    audio.build_voice(episode, cfg)
    man = compile_episode(episode, cfg)
    s = next(x for x in man["shots"] if x["id"] == "sh_007")
    spec = read_json(episode / s["spec_path"])
    for p in spec["props"]:
        p["height"] = p.get("height", 0) + 0.3      # hauteurs volontairement fausses (flottent de 30 cm)
    write_json(episode / "shots" / "settle.json", spec)
    rec = render.render_shot(cfg, episode, {"id": "sh_007", "spec_path": "shots/settle.json", "spec_sha256": sha256_json(spec),
                                            "frames": spec["frames"]}, "draft", mode="checks")
    rep = rec["scene_report"]
    assert any(a["type"] == "prop_settled" for a in rep.get("adjustments", [])), rep.get("adjustments")
    assert not [c for c in rep["checks"] if c["id"].startswith("floating_prop")], [c["id"] for c in rep["checks"]]
    assert any(str(e.get("what", "")).startswith("auto:") for e in rep["events"]), "business automatique entre les répliques"


# ------------------------------------------------------------------ étalonnage et boucle
def test_grade_filters_by_mood_and_switch():
    from studio import grade
    assert grade.grade_for("dramatic") == "conflict" and grade.grade_for("interior_warm") == "warm"
    assert grade.grade_for("interior_warm", "sad") == "sad" and grade.grade_for("night", "auto") == "night"
    f = grade.filters("conflict", {"grade": {"enabled": True}})
    assert f[0].startswith("colorbalance=") and any("contrast=1.2" in x for x in f) and f[-1].startswith("vignette")
    assert grade.filters("warm", {"grade": {"enabled": False}}) == []
    assert not any(x.startswith("vignette") for x in grade.filters("warm", {"grade": {"vignette": False}}))


@needs_voice
def test_loop_to_start_copies_first_framing_and_removes_final_fade(episode, cfg, tmp_path):
    from studio import audio, preflight
    from studio.compile import compile_episode
    sb = read_json(episode / "storyboard.json")
    sb["shots"][-1]["transition_out"] = "fade_black"
    write_json(episode / "storyboard.json", sb)
    audio.build_voice(episode, cfg)
    rep = preflight.run(episode, cfg, with_3d=False)
    assert any(a.startswith("[boucle]") and "loop_to_start" in a for a in rep["advice"])
    sb["shots"][-1]["loop_to_start"] = True
    sb["shots"][-1]["characters"] = sb["shots"][0]["characters"]
    write_json(episode / "storyboard.json", sb)
    man = compile_episode(episode, cfg, out_dir=tmp_path / "c")
    first = read_json(tmp_path / "c" / man["shots"][0]["spec_path"])["camera"]
    last = read_json(tmp_path / "c" / man["shots"][-1]["spec_path"])["camera"]
    assert last["framing"] == first["framing"] and last["subject"] == first["subject"]
    assert man["shots"][-1]["transition_out"] == "cut" and any("fondu au noir final" in w for w in man["warnings"])
