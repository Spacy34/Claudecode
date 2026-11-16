"""Bibliothèque d'avatars exportés depuis Roblox Studio (sans bpy) : contrôle des pièces R15/R6, licence, rangement.

Rangement : assets/roblox/avatars/<id>/avatar.obj (+ .mtl + textures) et avatar.json (provenance, licence, pièces).
Utilisation : cast_bible.characters[].design.roblox_avatar = "<id>".
"""
import re
import shutil
from pathlib import Path

from .util import ROOT, now, sha256_file, write_json

LIB = ROOT / "assets" / "roblox" / "avatars"
TEX_EXT = (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".webp")
R15 = ["Head", "UpperTorso", "LowerTorso", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm",
       "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
R6 = {"torso": "UpperTorso", "leftarm": "LeftUpperArm", "rightarm": "RightUpperArm", "leftleg": "LeftUpperLeg", "rightleg": "RightUpperLeg"}


def norm_part(n):
    n = re.sub(r"\.\d+$", "", n)
    n = re.sub(r"\d+$", "", n)
    return n.replace(" ", "").replace("_", "").lower()


def classify_parts(names):
    """Même règle que le moteur (blender/engine/roblox_avatar.py) : {pièce: nom d'origine}, [autres]."""
    body, extras = {}, []
    for n in names:
        k = norm_part(n)
        hit = next((p for p in R15 if p.lower() == k), None) or R6.get(k)
        if hit and hit not in body:
            body[hit] = n
        else:
            extras.append(n)
    return body, extras


def obj_objects(path):
    """Noms des objets/groupes d'un OBJ (lignes « o » sinon « g »)."""
    os_, gs = [], []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("o "):
            os_.append(line[2:].strip())
        elif line.startswith("g "):
            gs.append(line[2:].strip())
    return os_ or gs


def mtl_files(obj_path):
    out = []
    for line in Path(obj_path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("mtllib "):
            out.append(line[7:].strip())
    return out


def inspect(obj_path):
    names = obj_objects(obj_path)
    body, extras = classify_parts(names)
    kind = "R15" if {"LowerTorso", "LeftLowerArm"} <= set(body) else ("R6" if body else "inconnu")
    problems = []
    for need in ("Head", "UpperTorso"):
        if need not in body:
            problems.append(f"pièce {need} introuvable (noms trouvés : {names[:12]})")
    for side in ("Left", "Right"):
        if side + "UpperArm" not in body:
            problems.append(f"bras {side} introuvable")
        if side + "UpperLeg" not in body:
            problems.append(f"jambe {side} introuvable")
    if any(norm_part(n) in ("face", "decal") for n in extras):
        problems.append("un visage d'origine est exporté : le moteur dessine son propre visage (expressions, bouche) "
                        "par-dessus ; exporter de préférence SANS visage (face: procedural)")
    return {"rig": kind, "parts": sorted(body), "accessories": [n for n in extras], "problems": problems}


def add(src, aid, license_txt, source="", face="procedural", force=False):
    """Copie un export (fichier .obj ou dossier) dans la bibliothèque et écrit avatar.json. -> rapport."""
    src = Path(src).resolve()
    obj = src if src.suffix.lower() == ".obj" else next(iter(sorted(src.glob("*.obj"))), None)
    if obj is None or not obj.exists():
        raise FileNotFoundError(f"aucun fichier .obj dans {src}")
    aid = re.sub(r"[^a-z0-9_-]", "_", aid.strip().lower())
    rep = inspect(obj)
    blocking = [p for p in rep["problems"] if "introuvable" in p]
    if blocking and not force:
        return {"status": "rejected", "id": aid, **rep}
    dst = LIB / aid
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(obj, dst / "avatar.obj")
    for m in mtl_files(obj):
        if (obj.parent / m).exists():
            shutil.copy2(obj.parent / m, dst / Path(m).name)
    for f in obj.parent.iterdir():
        if f.suffix.lower() in TEX_EXT:
            shutil.copy2(f, dst / f.name)
    meta = {"id": aid, "added_at": now(), "source": source, "license": license_txt, "face": face, "rig": rep["rig"],
            "parts": rep["parts"], "accessories": rep["accessories"], "sha256": sha256_file(dst / "avatar.obj"),
            "forward_axis": "NEGATIVE_Z", "up_axis": "Y", "problems": rep["problems"]}
    write_json(dst / "avatar.json", meta)
    return {"status": "ok", "id": aid, "folder": str(dst), **rep,
            "cast_bible": {"design": {"roblox_avatar": aid}}}


def listing():
    out = []
    for d in sorted(LIB.glob("*/avatar.json")):
        import json
        m = json.loads(d.read_text(encoding="utf-8"))
        out.append({k: m.get(k) for k in ("id", "rig", "license", "source", "face")})
    return out
