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
    assert {"blip", "ding", "pop", "count_roll"} <= names, names          # messages, notification, textes/stickers, compteur
    assert all(c["file"].startswith("assets/sfx/") for c in cues)
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
