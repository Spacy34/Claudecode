"""Tests E, F, G, H, I, J avec un VRAI rendu Blender (profil minuscule pour rester rapide).

Marqués `blender` : `python3 -m pytest -m blender`. Ignorés si ni binaire Blender ni module bpy.
Ils prouvent que la scène se construit et se rend ; ils ne prouvent PAS que l'image est belle.
"""
import json
import os
import shutil

import pytest

from conftest import has_blender
from studio import audio, compile as comp, compose, render
from studio.qa import tech
from studio.util import read_json, sha256_json, write_json

pytestmark = [pytest.mark.blender, pytest.mark.skipif(not has_blender(), reason="Blender indisponible"),
              pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")]

TINY = {"description": "test", "resolution": [144, 256], "render_every_n_frames": 6, "cycles_samples": 2, "eevee_samples": 2,
        "denoise": False, "outlines": True, "upscale_to_delivery": True}


@pytest.fixture
def compiled(episode, cfg):
    cfg["profiles"]["tiny"] = dict(TINY)
    audio.build_voice(episode, cfg)
    man = comp.compile_episode(episode, cfg)
    return episode, cfg, man


def _luma_stats(png):
    from PIL import Image, ImageStat
    st = ImageStat.Stat(Image.open(png).convert("L"))
    return st.mean[0], st.stddev[0]


def test_E_scene_builds_and_renders(compiled):
    ep, cfg, man = compiled
    shot = man["shots"][0]
    rec = render.render_shot(cfg, ep, shot, "tiny", mode="stills", frames="1,60")
    assert rec["status"] == "rendered", rec.get("error")
    rep = rec["scene_report"]
    assert rep["render_engine"] in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")
    assert rep["camera"]["framing"] == "medium" and rep["events"], "animation : évènements d'actions/expressions"
    for f in (1, 60):
        mean, std = _luma_stats(os.path.join(rec["frames_dir"], f"f{f:04d}.png"))
        assert 35 < mean < 235 and std > 12, "image ni noire, ni brûlée, ni uniforme"


def test_H_J_cache_and_resume(compiled):
    ep, cfg, man = compiled
    shot = next(s for s in man["shots"] if s["id"] == "sh_009")
    r1 = render.render_shot(cfg, ep, shot, "tiny")
    assert r1["status"] == "rendered", r1.get("error")
    assert render.render_shot(cfg, ep, shot, "tiny")["status"] == "cached"
    d = r1["frames_dir"]
    frames = sorted(f for f in os.listdir(d) if f.startswith("f") and f.endswith(".png"))
    keep = {f: os.path.getmtime(os.path.join(d, f)) for f in frames[:-1]}
    os.remove(os.path.join(d, frames[-1]))
    os.remove(os.path.join(d, "done.json"))            # simule une interruption en fin de plan
    r3 = render.render_shot(cfg, ep, shot, "tiny")
    assert r3["status"] == "rendered" and os.path.exists(os.path.join(d, frames[-1]))
    assert all(os.path.getmtime(os.path.join(d, f)) == t for f, t in keep.items()), "frames valides non recalculées"


def test_G_offscreen_character_detected(compiled):
    ep, cfg, man = compiled
    shot = next(s for s in man["shots"] if s["id"] == "sh_002")
    spec = read_json(ep / shot["spec_path"])
    spec["camera"]["subject"] = {"kind": "point", "pos": [-5.0, 0.5, 1.2]}
    spec["camera"]["framing"] = "close_up"
    p = ep / "shots" / "injected.json"
    write_json(p, spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_002", "spec_path": "shots/injected.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    ids = [c["id"] for c in rec["scene_report"]["checks"]]
    assert "char_never_visible:ch_kevin" in ids


def test_F_I_preview_extract_with_audio_and_subtitles(compiled):
    ep, cfg, man = compiled
    ids = ["sh_008", "sh_009"]
    recs = [render.render_shot(cfg, ep, s, "tiny") for s in man["shots"] if s["id"] in ids]
    assert all(r["status"] in ("rendered", "cached") for r in recs)
    prof = render.profile_dict(cfg, "tiny")
    tl = read_json(ep / "audio_timeline.json")
    out = ep / "renders" / "extract.mp4"
    out.parent.mkdir(exist_ok=True)
    res = compose.assemble(cfg, ep, man, tl, recs, prof, out, fps=30)
    assert res["subtitle_events"] > 0
    checks, dur = tech.check_video(out, expected_duration=res["end_s"] - res["start_s"], expected_frames=res["expected_frames"],
                                   subs_path=out.with_suffix(".ass"), cfg=cfg)
    bad = [c for c in checks if c["status"] == "fail" and c["id"] not in ("loudness",)]
    assert bad == [], json.dumps(bad, ensure_ascii=False)
