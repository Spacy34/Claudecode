"""Conception sonore automatique et bibliothèque musicale."""
import shutil
from pathlib import Path

import pytest

from studio import audio, compile as comp, compose, sound_design
from studio.util import read_json

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("espeak-ng") is None or shutil.which("ffmpeg") is None, reason="espeak-ng/ffmpeg absents")


def test_auto_sfx_follow_events(episode, cfg):
    shutil.copy(ROOT / "episodes" / "ep_demo_grillepain" / "motion_design.json", episode / "motion_design.json")
    audio.build_voice(episode, cfg)
    man = comp.compile_episode(episode, cfg)
    tl = read_json(episode / "audio_timeline.json")
    cues = sound_design.auto_cues(episode, man["shots"], tl, cfg, existing=tl["sfx"])
    names = {c["name"] for c in cues}
    # niveau « discret » par défaut : seulement ce qui raconte quelque chose, bien sous la voix
    assert names <= sound_design.DISCRET and {"blip", "ding"} <= names, names
    assert all(c["gain_db"] <= -24 for c in cues), [c["gain_db"] for c in cues]
    assert all(c["file"].startswith("assets/sfx/") for c in cues)
    full = sound_design.auto_cues(episode, man["shots"], tl, {**cfg, "audio": {**cfg["audio"], "auto_sfx": "complet"}}, existing=tl["sfx"])
    assert "count_roll" in {c["name"] for c in full} and len(full) > len(cues)
    assert sound_design.auto_cues(episode, man["shots"], tl, {**cfg, "audio": {**cfg["audio"], "auto_sfx": "aucun"}}) == []
    starts = sorted(c["start_s"] for c in cues if c["name"] not in ("step", "tick"))
    assert all(b - a >= 0.12 for a, b in zip(starts, starts[1:])), "jamais d'empilement de bruitages"
    # tout le mixage passe (une entrée FFmpeg par fichier, pas par bruitage)
    out, used = compose.mix_audio(episode, tl, man["shots"], cfg, 0.0, man["shots"][-1]["end_s"], episode / "mix.wav")
    assert out.exists() and any(c["source"].startswith("auto:") for c in used)


def test_library_music_is_picked_by_mood_with_licence(episode, cfg, tmp_path, monkeypatch):
    lib = tmp_path / "assets"
    (lib / "music" / "library" / "tension").mkdir(parents=True)
    (lib / "music" / "library" / "comique").mkdir(parents=True)
    src = ROOT / "assets" / "music" / "goofy_bounce.wav"
    shutil.copy(src, lib / "music" / "library" / "comique" / "rigolo.wav")
    (lib / "music" / "library" / "comique" / "rigolo.wav.licence.txt").write_text("CC0, auteur X, usage commercial OK")
    shutil.copy(src, lib / "music" / "library" / "tension" / "suspense.wav")
    monkeypatch.setattr(audio, "music_library_dir", lambda c: lib / "music" / "library")
    script = read_json(episode / "story_script.json")
    pick, lic = audio.pick_library_music(episode, script, cfg)
    assert pick.name == "rigolo.wav" and "CC0" in lic                  # ton « humour noir / absurde » -> comique
    (episode / "audio" / "music").mkdir(parents=True)
    (episode / "audio" / "music" / "ambiance.txt").write_text("tension")
    pick, lic = audio.pick_library_music(episode, script, cfg)
    assert pick.name == "suspense.wav" and "non consignée" in lic        # ambiance forcée ; licence absente signalée


def test_motion_declutter_and_phone_fullscreen(episode, cfg):
    """Écran jamais surchargé : texte qui répète la voix retiré, un élément à la fois ; un seul téléphone à l'écran."""
    from studio import motion
    shutil.copy(ROOT / "episodes" / "ep_demo_grillepain" / "motion_design.json", episode / "motion_design.json")
    audio.build_voice(episode, cfg)
    comp.compile_episode(episode, cfg)
    tl = read_json(episode / "audio_timeline.json")
    kept, dropped = motion.prepare(motion.load(episode), tl, episode)
    ids = {e["id"]: e for e in kept}
    why = dict(dropped)
    assert "mo_fumee" in why and "voix" in why["mo_fumee"]          # « Puis à fumer » : déjà dit et sous-titré
    assert "mo_skull" in why                                          # sticker pendant l'écran du téléphone
    ordered = sorted(kept, key=lambda e: e["_t0"])
    assert all(a["_t1"] <= b["_t0"] + 1e-6 for a, b in zip(ordered, ordered[1:])), "un seul élément à la fois"
    assert ids["mo_tiktok_post"].get("_takeover"), "Kevin tient un téléphone 3D dans ce plan : écran 2D en plein écran"
