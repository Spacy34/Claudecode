"""Onglet Mixage : réglages par piste et par bruitage, application au mixage, nouveau montage sans rendu 3D."""
import json
import shutil

import pytest

from conftest import has_blender
from studio import mixer
from studio.util import read_json


def test_settings_clamped_and_cleaned(tmp_path):
    m = mixer.save(tmp_path, {"voice_db": 99, "music_db": "-6", "sfx_db": -100, "mute": {"music": True, "bogus": True},
                              "cues": {"a": {"gain_db": 0, "mute": False}, "b": {"gain_db": -8}, "c": {"mute": True}}})
    assert m["voice_db"] == 12 and m["music_db"] == -6 and m["sfx_db"] == -40
    assert m["mute"] == {"voice": False, "music": True, "sfx": False}
    assert set(m["cues"]) == {"b", "c"}, "les bruitages laissés à 0 ne sont pas stockés"
    assert mixer.load(tmp_path) == m and read_json(tmp_path / "audio" / "mix.json") == m


def test_apply_gains_and_mutes():
    cues = [{"source": "script", "name": "whoosh", "start_s": 1.0, "gain_db": -15, "file": "x"},
            {"source": "auto:pas", "name": "step", "start_s": 2.345, "gain_db": -29, "file": "y"}]
    mix = json.loads(json.dumps(mixer.DEFAULT))
    mix["sfx_db"] = -6
    mix["cues"] = {mixer.cue_key(cues[0]): {"gain_db": -10, "mute": False}, mixer.cue_key(cues[1]): {"gain_db": 0, "mute": True}}
    out = mixer.apply(cues, mix)
    assert len(out) == 1 and out[0]["gain_db"] == -31
    assert mixer.cue_key(cues[1]) == "auto:pas|step|2.35"
    mix["mute"]["sfx"] = True
    assert mixer.apply(cues, mix) == []


needs_voice = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")


@pytest.mark.blender
@pytest.mark.skipif(not has_blender(), reason="Blender indisponible")
@needs_voice
def test_remix_redoes_last_montage_sound_only(episode, cfg, monkeypatch):
    """Prototype monté, puis bruitages coupés + voix baissée : `studio remix` refait CE montage sans rendu 3D,
    le son change (mesuré), l'image vient du cache, les étapes en aval ne deviennent pas périmées."""
    import subprocess
    from studio import audio, cli, compose, render
    from studio.compile import compile_episode
    from test_blender_e2e import TINY
    cfg["profiles"]["tiny"] = dict(TINY)
    monkeypatch.setattr(cli, "CFG", cfg)
    audio.build_voice(episode, cfg)
    compile_episode(episode, cfg)
    ids = ["sh_001", "sh_002"]
    res = cli._render_and_assemble(episode, ids, "tiny", "renders/prototype.mp4", "prototype")
    assert res["rendered"] == 2

    def loud(p):
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(p), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        return float(r.stderr.split("max_volume:")[1].split("dB")[0])
    lm = mixer.latest_montage(episode)
    assert lm["kind"] == "prototype" and lm["shots"] == ids
    mixer.save(episode, {"voice_db": -20, "mute": {"sfx": True, "music": True}})
    before = (episode / "renders" / "prototype.mp4").stat().st_mtime
    cues_seen = []
    real = compose.mix_audio

    def spy(*a, **k):
        out, cues = real(*a, **k)
        cues_seen.append(cues)
        return out, cues
    monkeypatch.setattr(compose, "mix_audio", spy)
    with pytest.raises(SystemExit) as ex:
        cli.main(["remix", episode.name])
    assert ex.value.code == 0
    assert (episode / "renders" / "prototype.mp4").stat().st_mtime > before
    assert cues_seen and cues_seen[-1] == [], "bruitages coupés"
    rm = read_json(episode / "render_manifest_tiny.json")
    assert all(s["status"] == "cached" for s in rm["shots"]), "aucun rendu 3D refait"
    from studio.state import State
    assert State(episode).data["history"][-1]["event"] == "remix"
    assert loud(episode / "renders" / "prototype.mp4") < 0


def test_script_sfx_capped_at_mix(tmp_path):
    """Les bruitages du script ne dépassent plus le niveau studio (un whoosh à -8 dB était bien trop fort)."""
    from studio import compose
    from studio.util import load_config
    cfg = load_config()
    tl = {"sfx": [{"name": "whoosh", "file": "assets/sfx/whoosh.wav", "start_s": 0.25, "gain_db": -8, "source": "script"},
                  {"name": "pop", "file": "assets/sfx/pop.wav", "start_s": 1.0, "gain_db": -25, "source": "script"}],
          "segments": [], "duration_s": 5}
    cues = compose.sfx_cues(tl, [], cfg)
    assert cues[0]["gain_db"] == cfg["audio"]["script_sfx_max_db"] and cues[1]["gain_db"] == -25
