"""Décors procéduraux par « kit ». Convention : sol z=0, caméra côté -Y (face ouverte, pas de 4e mur),
mur du fond à y = +profondeur/2. Chaque décor expose des repères nommés (`marks`) en (x, y)."""
import math
import random
import bpy
from . import core, props

D = math.radians

from .kitdata import PALETTES, BASE_MARKS, KIT_DRESSING, KIT_MARKS, INTERIOR  # noqa: E402


def build_set(spec, coll=None):
    kit = spec["kit"]
    pal = dict(PALETTES[kit])
    pal.update(spec.get("palette", {}))
    w, d = spec.get("size", [8.0, 6.0])
    rng = random.Random(spec.get("seed", 7))
    col = bpy.data.collections.new(spec["id"])
    (coll or bpy.context.scene.collection).children.link(col)
    solids = []
    floor_m = core.toon_mat(spec["id"] + "_floor", pal["floor"], rough=0.85)
    wall_m = core.toon_mat(spec["id"] + "_wall", pal["wall"], rough=0.9)
    if kit in INTERIOR:
        core.box(spec["id"] + "_floor", (w, d + 6, 0.1), floor_m, (0, 0, -0.05), coll=col)
        # lattes / carrelage : bandes pour donner de la texture au sol sans textures externes
        stripe = core.toon_mat(spec["id"] + "_floor2", _shade(pal["floor"], 0.9), rough=0.85)
        step = 0.6 if kit in ("kitchen", "bathroom", "supermarket") else 0.35
        x = -w / 2 + step
        i = 0
        while x < w / 2:
            if i % 2 == 0:
                core.box(spec["id"] + f"_fl{i}", (step * 0.96, d + 6, 0.004), stripe, (x - step / 2, 0, 0.002), coll=col)
            x += step
            i += 1
        core.box(spec["id"] + "_backwall", (w, 0.2, 3.2), wall_m, (0, d / 2 + 0.1, 1.6), coll=col, ink=0.015)
        for s in (1, -1):
            core.box(spec["id"] + f"_side{s}", (0.2, d, 3.2), wall_m, (s * (w / 2 + 0.1), 0, 1.6), coll=col, ink=0.015)
        base_m = core.toon_mat(spec["id"] + "_base", _shade(pal["wall"], 0.75))
        core.box(spec["id"] + "_baseboard", (w, 0.04, 0.12), base_m, (0, d / 2 - 0.01, 0.06), coll=col)
    elif kit == "street":
        core.box(spec["id"] + "_sidewalk", (40, 4.5, 0.15), core.toon_mat(spec["id"] + "_sw", "#C9C9C9"), (0, -0.75, 0.0), coll=col, ink=0.01)
        core.box(spec["id"] + "_road", (40, 6.0, 0.1), core.toon_mat(spec["id"] + "_road", "#4A4E69"), (0, 4.5, -0.03), coll=col)
        dash = core.toon_mat(spec["id"] + "_dash", "#F1FAEE", emission=0.1)
        for i in range(-8, 9):
            core.box(spec["id"] + f"_dash{i}", (1.2, 0.15, 0.01), dash, (i * 2.4, 4.5, 0.03), coll=col)
        core.box(spec["id"] + "_far", (60, 30, 0.1), core.toon_mat(spec["id"] + "_far", "#ADB5BD"), (0, 20, -0.06), coll=col)
    else:   # park, studio_void
        core.box(spec["id"] + "_ground", (60, 60, 0.1), floor_m, (0, 20, -0.05), coll=col)
        if kit == "park":
            core.box(spec["id"] + "_path", (2.2, 30, 0.02), core.toon_mat(spec["id"] + "_path", "#E9D8A6"), (0, 10, 0.01), coll=col)
            gm = core.toon_mat(spec["id"] + "_grass2", _shade(pal["floor"], 0.85))
            for i in range(40):
                x, y = rng.uniform(-8, 8), rng.uniform(-2, 12)
                if abs(x) < 1.4:
                    continue
                core.cyl(spec["id"] + f"_tuft{i}", 0.08, 0.0, 0.18, gm, (x, y, 0.09), parent=None, coll=col, seg=4)
        if kit == "studio_void":
            core.box(spec["id"] + "_cyc", (30, 0.3, 12), wall_m, (0, 8, 6), coll=col)
    # habillage
    dressing = []
    if spec.get("use_kit_dressing", True):
        for t in KIT_DRESSING[kit]:
            dressing.append({"type": t[0], "pos": [t[1], t[2]], "rot_deg": t[3], "scale": t[4] if len(t) > 4 else 1.0, "z": t[5] if len(t) > 5 else 0.0})
    dressing += spec.get("dressing", [])
    for i, item in enumerate(dressing):
        o = props.build(item["type"], f"{spec['id']}_{item['type']}_{i}", item.get("color"), item.get("scale", 1.0), item.get("label"), col)
        o.location = (item["pos"][0], item["pos"][1], item.get("z", 0.0))
        o.rotation_euler = (0, 0, D(item.get("rot_deg", 0)))
        if item["type"] not in ("rug", "window", "painting", "building", "streetlight"):
            solids.append(o)
    marks = dict(BASE_MARKS)
    marks.update(KIT_MARKS[kit])
    marks.update({k: tuple(v) for k, v in spec.get("marks", {}).items()})
    bounds = (-w / 2 + 0.3, w / 2 - 0.3, -d / 2 - 3, d / 2 - 0.3) if kit in INTERIOR else (-20, 20, -4, 8)
    return {"collection": col, "marks": marks, "solids": solids, "bounds": bounds, "palette": pal, "kit": kit, "interior": kit in INTERIOR}


def _shade(h, k):
    h = h.lstrip('#')
    return '#' + ''.join(f"{min(255, int(int(h[i:i + 2], 16) * k)):02x}" for i in (0, 2, 4))
