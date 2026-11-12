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
    nv = [c for c in rec["scene_report"]["checks"] if c["id"] == "char_never_visible:ch_kevin"]
    assert nv and nv[0]["severity"] == "minor", "plan serré sur autre chose (contrechamp) : simple avertissement"
    # plan large : un personnage listé mais invisible est un vrai défaut bloquant
    spec["camera"] = {**spec["camera"], "framing": "wide", "subject": {"kind": "point", "pos": [0.0, 0.5, 1.0]}}
    spec["characters"][0]["pos"] = [40.0, 0.0]
    write_json(p, spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_002", "spec_path": "shots/injected.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    nv = [c for c in rec["scene_report"]["checks"] if c["id"] == "char_never_visible:ch_kevin"]
    assert nv and nv[0]["severity"] == "major" and nv[0]["status"] == "fail"


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


def test_G_foreground_occluder_detected(compiled):
    """Défaut constaté sur une vidéo de référence : un meuble au premier plan masque les personnages."""
    ep, cfg, man = compiled
    shot = next(s for s in man["shots"] if s["id"] == "sh_008")
    spec = read_json(ep / shot["spec_path"])
    spec["set"] = dict(spec["set"], dressing=[{"type": "counter", "pos": [0.0, -0.2], "scale": 1.6}])
    spec["camera"]["avoid_occluders"] = False   # on teste le CONTRÔLE, pas l'esquive automatique de la caméra
    p = ep / "shots" / "injected_fg.json"
    write_json(p, spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_008", "spec_path": "shots/injected_fg.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    ids = [c["id"] for c in rec["scene_report"]["checks"]]
    assert "foreground_occluder" in ids, ids


def test_camera_looks_over_foreground_obstacle(compiled):
    """Avec l'esquive active, la caméra monte au-dessus d'une table au premier plan : personnages visibles,
    premier plan non bouché (cas de la vidéo de référence : table qui masque 40 % de l'image)."""
    ep, cfg, man = compiled
    shot = next(s for s in man["shots"] if s["id"] == "sh_008")
    spec = read_json(ep / shot["spec_path"])
    spec["set"] = dict(spec["set"], dressing=[{"type": "table", "pos": [0.0, -0.6], "scale": 1.2}])
    p = ep / "shots" / "injected_fg2.json"
    write_json(p, spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_008", "spec_path": "shots/injected_fg2.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    ids = [c["id"] for c in rec["scene_report"]["checks"] if c["status"] == "fail"]
    assert not any(i.startswith(("char_never_visible", "foreground_occluder")) for i in ids), ids


CUBE_OBJ = """o cube
v -0.5 -0.5 0
v 0.5 -0.5 0
v 0.5 0.5 0
v -0.5 0.5 0
v -0.5 -0.5 1
v 0.5 -0.5 1
v 0.5 0.5 1
v -0.5 0.5 1
f 1 2 3 4
f 5 8 7 6
f 1 5 6 2
f 2 6 7 3
f 3 7 8 4
f 4 8 5 1
"""


def test_vocab_composite_external_animal(compiled, tmp_path):
    """Objet improvisé (composite), modèle externe (OBJ fabriqué par le test), animal, nouveau lieu."""
    ep, cfg, man = compiled
    model = tmp_path / "cube.obj"
    model.write_text(CUBE_OBJ)
    spec = read_json(ep / next(s for s in man["shots"] if s["id"] == "sh_001")["spec_path"])
    spec["set"] = {"id": "set_resto", "kit": "restaurant", "source": "procedural", "license": {"spdx": "original", "commercial_use": True}}
    spec["props"] = [
        {"id": "pr_machine", "type": "composite", "pos": [1.0, 1.2], "height": 0, "parts": [
            {"shape": "box", "size": [0.5, 0.4, 0.8], "pos": [0, 0, 0.4], "color": "#C0C0C0"},
            {"shape": "cone", "size": [0.3, 0, 0.3], "pos": [0, 0, 0.95], "color": "#E63946"},
            {"shape": "text", "size": [0.08, 0, 0], "pos": [0, -0.22, 0.6], "text": "OK", "glow": True}]},
        {"id": "pr_cube", "type": "custom", "external_path_abs": str(model), "target_height": 0.4, "pos": [-1.0, 1.2], "height": 0},
        {"id": "pr_dog", "type": "dog", "pos": [-0.4, 0.4], "height": 0}]
    spec["prop_actions"], spec["actions"], spec["fx"] = [], [], []
    write_json(ep / "shots" / "vocab.json", spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_001", "spec_path": "shots/vocab.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    assert rec["status"] == "rendered", rec.get("error")
    assert not rec["scene_report"].get("warnings"), rec["scene_report"].get("warnings")
    # fichier externe manquant : repli VISIBLE + avertissement, jamais un plan vide silencieux
    spec["props"][1]["external_path_abs"] = str(tmp_path / "absent.glb")
    write_json(ep / "shots" / "vocab2.json", spec)
    rec2 = render.render_shot(cfg, ep, {"id": "sh_001", "spec_path": "shots/vocab2.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    assert rec2["status"] == "rendered"
    assert any("pr_cube" in w for w in rec2["scene_report"]["warnings"])


def test_intended_offscreen_character_not_flagged(compiled):
    """Personnage volontairement hors champ (voix off) : pas de char_never_visible."""
    ep, cfg, man = compiled
    spec = read_json(ep / next(s for s in man["shots"] if s["id"] == "sh_002")["spec_path"])
    spec["camera"]["subject"] = {"kind": "point", "pos": [-5.0, 0.5, 1.2]}
    spec["camera"]["framing"] = "close_up"
    spec["characters"][0]["offscreen"] = True
    write_json(ep / "shots" / "off.json", spec)
    rec = render.render_shot(cfg, ep, {"id": "sh_002", "spec_path": "shots/off.json", "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "tiny", mode="stills", frames="1")
    assert not any(c["id"].startswith(("char_never_visible", "char_offscreen")) for c in rec["scene_report"]["checks"])


def _frame_rgb(video, t, out_png):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(out_png)], check=True)
    from PIL import Image
    return Image.open(out_png).convert("RGB")


def test_motion_design_overlay_and_progress_bar(compiled):
    """La couche motion design (téléphone, compteur…) et la barre de progression sont incrustées dans la vidéo."""
    from pathlib import Path
    from studio import motion
    ep, cfg, man = compiled
    ids = ["sh_008", "sh_009"]
    recs = [render.render_shot(cfg, ep, s, "tiny") for s in man["shots"] if s["id"] in ids]
    prof = render.profile_dict(cfg, "tiny")
    tl = read_json(ep / "audio_timeline.json")
    (ep / "renders").mkdir(exist_ok=True)
    plain = compose.assemble(cfg, ep, man, tl, recs, prof, ep / "renders" / "plain.mp4", fps=30)
    assert not plain["motion_overlay"] and not plain["progress_bar"]
    shutil.copy(Path(__file__).resolve().parents[1] / "episodes" / "ep_demo_grillepain" / "motion_design.json", ep / "motion_design.json")
    res = compose.assemble(cfg, ep, man, tl, recs, prof, ep / "renders" / "motion.mp4", fps=30)
    assert res["motion_overlay"] and res["progress_bar"]
    phone = next(e for e in motion.resolve(motion.load(ep), tl) if e["id"] == "mo_expulse")
    t = phone["_t0"] + 1.2 - res["start_s"]
    a = _frame_rgb(ep / "renders" / "plain.mp4", t, ep / "renders" / "a.png")
    b = _frame_rgb(ep / "renders" / "motion.mp4", t, ep / "renders" / "b.png")
    # le téléphone (côté droit) modifie nettement l'image ; la barre de progression est rouge en haut à gauche
    box = (600, 450, 940, 1000)
    from PIL import ImageChops, ImageStat
    diff = ImageStat.Stat(ImageChops.difference(a.crop(box), b.crop(box)).convert("L")).mean[0]
    assert diff > 25, diff
    r, g, _ = b.getpixel((60, int(1920 * 0.012) + 3))
    assert r > 170 and g < 120, (r, g)
