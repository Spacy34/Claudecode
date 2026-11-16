"""Spécifique au studio Roblox : avatars R15 (procéduraux et importés), décor maison, emotes."""
import shutil

import pytest

from conftest import has_blender
from studio import contracts, rbx_assets
from studio.util import read_json, sha256_json, write_json

# pièces R15 (studs) : nom, taille, centre — comme un export de Roblox Studio (Y vers le haut, avatar regardant -Z)
PARTS = [("LeftFoot1", (1, .3, 1), (.5, .15, 0)), ("RightFoot1", (1, .3, 1), (-.5, .15, 0)),
         ("LeftLowerLeg1", (1, 1.1, 1), (.5, .85, 0)), ("RightLowerLeg1", (1, 1.1, 1), (-.5, .85, 0)),
         ("LeftUpperLeg1", (1, 1.2, 1), (.5, 2.0, 0)), ("RightUpperLeg1", (1, 1.2, 1), (-.5, 2.0, 0)),
         ("LowerTorso1", (2, .4, 1), (0, 2.8, 0)), ("UpperTorso1", (2, 1.6, 1), (0, 3.8, 0)),
         ("LeftUpperArm1", (1, 1.2, 1), (1.5, 4.0, 0)), ("RightUpperArm1", (1, 1.2, 1), (-1.5, 4.0, 0)),
         ("LeftLowerArm1", (1, 1.0, 1), (1.5, 2.9, 0)), ("RightLowerArm1", (1, 1.0, 1), (-1.5, 2.9, 0)),
         ("LeftHand1", (1, .3, 1), (1.5, 2.25, 0)), ("RightHand1", (1, .3, 1), (-1.5, 2.25, 0)),
         ("Head1", (1.2, 1.2, 1.2), (0, 5.2, 0)), ("Accessory (CoolCap)", (1.4, .4, 1.4), (0, 6.0, 0))]


def write_obj(path, parts=PARTS):
    lines, base = ["mtllib avatar.mtl"], 1
    for name, (sx, sy, sz), (cx, cy, cz) in parts:
        lines.append(f"o {name}")
        for dx in (-1, 1):
            for dy in (-1, 1):
                for dz in (-1, 1):
                    lines.append(f"v {cx + dx * sx / 2} {cy + dy * sy / 2} {cz + dz * sz / 2}")
        lines.append("usemtl m0")
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            lines.append("f " + " ".join(str(base + i) for i in f))
        base += 8
    path.write_text("\n".join(lines) + "\n")
    (path.parent / "avatar.mtl").write_text("newmtl m0\nKd 0.9 0.6 0.3\n")


def test_classify_r15_r6_names():
    body, extras = rbx_assets.classify_parts(["Head1", "UpperTorso", "LeftUpperArm.001", "Left Arm", "Handle", "Accessory (Hat)"])
    assert body["Head"] == "Head1" and body["UpperTorso"] == "UpperTorso" and body["LeftUpperArm"] == "LeftUpperArm.001"
    assert "Left Arm" in extras, "la pièce R15 a la priorité, l'autre nom n'est pas une 2e pièce"
    assert rbx_assets.classify_parts(["Torso", "Left Leg"])[0] == {"UpperTorso": "Torso", "LeftUpperLeg": "Left Leg"}


def test_avatar_add_checks_parts_and_records_license(tmp_path, monkeypatch):
    monkeypatch.setattr(rbx_assets, "LIB", tmp_path / "lib")
    src = tmp_path / "export"
    src.mkdir()
    write_obj(src / "kevin.obj")
    rep = rbx_assets.add(src / "kevin.obj", "Kevin RBX", "création personnelle", source="mon compte")
    assert rep["status"] == "ok" and rep["rig"] == "R15" and rep["id"] == "kevin_rbx"
    meta = read_json(tmp_path / "lib" / "kevin_rbx" / "avatar.json")
    assert meta["license"] == "création personnelle" and (tmp_path / "lib" / "kevin_rbx" / "avatar.mtl").exists()
    bad = tmp_path / "bad"
    bad.mkdir()
    write_obj(bad / "x.obj", [p for p in PARTS if not p[0].startswith("Head")])
    assert rbx_assets.add(bad / "x.obj", "bad", "x")["status"] == "rejected"


def test_contracts_know_roblox_vocabulary(episode):
    assert contracts.capability_errors() == []
    cb = read_json(episode / "cast_bible.json")
    cb["characters"][0]["design"]["roblox_avatar"] = "kevin_rbx"
    errs = contracts.schema_errors("cast_bible", cb)
    assert errs == [], errs
    ap = read_json(episode / "animation_plan.json")
    ap["shots"]["sh_001"]["actions"][0]["action"] = "dance_groove"
    assert contracts.schema_errors("animation_plan", ap) == []


needs_voice = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng absent")


@pytest.mark.blender
@pytest.mark.skipif(not has_blender(), reason="Blender indisponible")
@needs_voice
def test_imported_avatar_and_suburb_render(episode, cfg, monkeypatch):
    """Un avatar exporté (OBJ R15) est rattaché au squelette, porte le visage du moteur et joue une emote devant la maison."""
    from studio import audio, render
    from studio.compile import compile_episode
    lib = rbx_assets.LIB / "_test_avatar"
    lib.mkdir(parents=True, exist_ok=True)
    try:
        write_obj(lib / "avatar.obj")
        write_json(lib / "avatar.json", {"id": "_test_avatar", "license": "test", "face": "procedural"})
        audio.build_voice(episode, cfg)
        man = compile_episode(episode, cfg)
        s = next(x for x in man["shots"] if x["id"] == "sh_008")
        spec = read_json(episode / s["spec_path"])
        spec["set"] = dict(spec["set"], kit="suburb")
        spec["characters"][0]["design"] = dict(spec["characters"][0]["design"], roblox_avatar="_test_avatar")
        cid = spec["characters"][0]["id"]
        spec["actions"] = [{"char": cid, "action": "dance_groove", "frame": 5, "duration_frames": 40, "intensity": 1.0}]
        spec["talk"] = [{"char": cid, "words": [[5, 20], [22, 40]], "visemes": [[5, "A"], [12, "O"], [22, "E"], [40, "rest"]]}]
        write_json(episode / "shots" / "rbx.json", spec)
        rec = render.render_shot(cfg, episode, {"id": "sh_008", "spec_path": "shots/rbx.json", "spec_sha256": sha256_json(spec),
                                                "frames": spec["frames"]}, "draft", mode="stills", frames="20")
        assert rec["status"] == "rendered", (rec.get("scene_report") or {}).get("error") or rec.get("error")
        rep = rec["scene_report"]
        assert any("dance_groove" in str(e.get("what")) for e in rep["events"])
        assert not [c for c in rep["checks"] if c["id"].startswith(("char_never_visible", "prop_in_character"))], rep["checks"]
    finally:
        shutil.rmtree(lib, ignore_errors=True)
