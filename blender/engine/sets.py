"""Décors procéduraux par « kit ». Convention : sol z=0, caméra côté -Y (face ouverte, pas de 4e mur),
mur du fond à y = +profondeur/2. Chaque décor expose des repères nommés (`marks`) en (x, y).

v2 : surfaces texturées procédurales (parquet, carrelage, briques, herbe, papier peint), soubassements et
moulures, objets muraux d'ambiance, petits objets posés, extérieurs en couches (rue avec façades, skyline,
collines, rangées d'arbres, nuages) et ciel en dégradé. Rien n'est ajouté côté caméra au centre du décor.
"""
import math
import random
import bpy
from . import core, props, decor
from .kitdata import PALETTES, BASE_MARKS, KIT_DRESSING, KIT_MARKS, INTERIOR, SURFACES, WALL_DECOR, CLUTTER  # noqa: F401

D = math.radians


def _shade(h, k):
    h = h.lstrip('#')
    return '#' + ''.join(f"{min(255, int(int(h[i:i + 2], 16) * k)):02x}" for i in (0, 2, 4))


def _interior_shell(sid, kit, pal, w, d, col, surf=None):
    floor_kind, wall_kind, floor_alt, wains = SURFACES.get(kit, ("planks", "noise", None, False))
    if surf:   # lieu générique ou surcharge par l'agent décorateur
        floor_kind, wall_kind = surf.get("floor", floor_kind), surf.get("wall", wall_kind)
        wains = surf.get("wainscot", wains)
    fl_alt = floor_alt or _shade(pal["floor"], 0.82)
    fscale = {"planks": 1.0, "tiles": 1.6, "noise": 1.0, "grass": 0.6, "bricks": 1.0, "wood": 0.5, "stripes": 1.0}.get(floor_kind, 1.0)
    floor_m = core.pattern_mat(sid + "_floor", floor_kind, pal["floor"], fl_alt, scale=fscale, emission=0.18)
    core.box(sid + "_floor", (w, d + 6, 0.1), floor_m, (0, 0, -0.05), coll=col)
    wall_alt = _shade(pal["wall"], 0.9)
    wall_m = core.pattern_mat(sid + "_wall", wall_kind, pal["wall"], wall_alt, scale=1.0, plane='xz', emission=0.18)
    core.box(sid + "_backwall", (w, 0.2, 3.2), wall_m, (0, d / 2 + 0.1, 1.6), coll=col, ink=0.015)
    side_m = core.pattern_mat(sid + "_wallside", "noise", _shade(pal["wall"], 0.92), scale=1.0, emission=0.15)
    for s in (1, -1):
        core.box(sid + f"_side{s}", (0.2, d, 3.2), side_m, (s * (w / 2 + 0.1), 0, 1.6), coll=col, ink=0.015)
    base_m = core.toon_mat(sid + "_base", _shade(pal["wall"], 0.7))
    core.box(sid + "_baseboard", (w, 0.05, 0.13), base_m, (0, d / 2 - 0.02, 0.065), coll=col)
    if wains:
        decor.wainscot(sid + "_wains", w, d / 2, _shade(pal["wall"], 0.7), _shade(pal.get("accent", pal["wall"]), 0.75), col)
    # plafond suggéré : bandeau sombre en haut du mur du fond (cadre l'image verticale)
    core.box(sid + "_ceilband", (w, 0.3, 0.25), core.toon_mat(sid + "_ceil", _shade(pal["wall"], 0.6)), (0, d / 2 - 0.1, 3.3), coll=col)


def _wall_decor(sid, kit, pal, d, col, rng):
    wy = d / 2
    for i, (kind, x, z, prm) in enumerate(WALL_DECOR.get(kit, [])):
        n = f"{sid}_dec_{kind}{i}"
        if kind == "poster":
            decor.poster(n, x, z, wy, prm, prm * 1.35, rng, col)
        elif kind == "clock":
            decor.clock(n, x, z, wy, col)
        elif kind == "shelf":
            decor.wall_shelf(n, x, z, wy, prm, rng, col)
        elif kind == "curtains":
            decor.curtains(n, x, z, wy, prm, pal.get("accent", "#E76F51"), col)
        elif kind == "pendant":
            decor.pendant_lamp(n, x, z if z < 2.9 else 1.0, 3.35, col, _shade(pal.get("accent", "#FFD166"), 1.1))
        elif kind == "cabinet":
            wood = core.pattern_mat(f"{sid}_cab", "wood", _shade(pal.get("accent", "#C68B59"), 1.0), _shade(pal.get("accent", "#C68B59"), 0.8), scale=2.5, plane='xz', emission=0.15)
            core.box(n, (prm, 0.36, 0.7), wood, (x, wy - 0.18, z), coll=col, ink=0.008)
            ndoor = max(1, int(round(prm / 0.5)))
            for k in range(ndoor):
                dx = x - prm / 2 + (k + 0.5) * prm / ndoor
                core.box(n + f"_door{k}", (prm / ndoor - 0.05, 0.02, 0.6), core.toon_mat(f"{sid}_cabdoor", _shade(pal.get("accent", "#C68B59"), 1.15), emission=0.15),
                         (dx, wy - 0.37, z), coll=col)
                core.ball(n + f"_knob{k}", (0.025,) * 3, core.toon_mat("dec_knob", "#F4C430", metallic=0.5), (dx + (0.12 if k % 2 == 0 else -0.12), wy - 0.39, z - 0.18), coll=col, detail=1)


def _clutter(sid, kit, col, rng, avoid):
    for zi, (x0, x1, y, h, nmax, kinds) in enumerate(CLUTTER.get(kit, [])):
        pts = decor.scatter_avoiding(rng, nmax, (x0, x1), (y - 0.08, y + 0.08), avoid + [], 0.3)
        # espacement minimal entre objets
        kept = []
        for p in sorted(pts):
            if all(abs(p[0] - q[0]) > 0.22 for q in kept):
                kept.append(p)
        for k, p in enumerate(kept):
            decor.small_item(f"{sid}_cl{zi}_{k}", kinds[k % len(kinds)], p[0], p[1], h, rng, col)


def _street(sid, pal, col, rng):
    sw = core.pattern_mat(sid + "_sw", "tiles", "#B9B4AC", "#A9A39A", scale=1.4, emission=0.18)
    core.box(sid + "_sidewalk", (40, 4.5, 0.15), sw, (0, -0.75, 0.0), coll=col, ink=0.01)
    core.box(sid + "_curb", (40, 0.25, 0.2), core.toon_mat(sid + "_curb", "#9A9A9A"), (0, 1.5, 0.02), coll=col, ink=0.006)
    core.box(sid + "_road", (40, 6.0, 0.1), core.pattern_mat(sid + "_road", "noise", "#4A4E69", scale=3, emission=0.12), (0, 4.6, -0.03), coll=col)
    dash = core.toon_mat(sid + "_dash", "#F1FAEE", emission=0.25)
    for i in range(-8, 9):
        core.box(sid + f"_dash{i}", (1.2, 0.15, 0.01), dash, (i * 2.4, 4.6, 0.03), coll=col)
    core.box(sid + "_sw2", (40, 3.0, 0.15), sw, (0, 9.0, 0.0), coll=col)
    shops = ["BOULANGERIE", "PHARMACIE", "TABAC", "PIZZA", "LAVERIE", "KEBAB", "COIFFURE"]
    x = -16.0
    i = 0
    while x < 16:
        bw = rng.uniform(4.5, 6.5)
        bh = rng.uniform(8.0, 13.0)
        decor.facade(f"{sid}_fac{i}", x + bw / 2, 12.0, bw, bh, rng.choice(["#E9C46A", "#F4A261", "#E5989B", "#A8DADC", "#CDB4DB", "#F2CC8F"]),
                     rng, col, shop=shops[i % len(shops)] if rng.random() < 0.7 else None)
        x += bw + 0.1
        i += 1
    decor.skyline(sid + "_skyline", 26.0, rng, col)
    for k in range(5):
        decor.cloud(f"{sid}_cloud{k}", (rng.uniform(-14, 14), 40 + rng.uniform(0, 10), rng.uniform(14, 22)), rng.uniform(2.0, 3.5), col, rng)


def _park(sid, pal, col, rng):
    g = core.pattern_mat(sid + "_grass", "grass", pal["floor"], _shade(pal["floor"], 0.78), scale=0.6, emission=0.18)
    core.box(sid + "_ground", (80, 80, 0.1), g, (0, 25, -0.05), coll=col)
    core.box(sid + "_path", (2.2, 40, 0.03), core.pattern_mat(sid + "_path", "noise", "#D4B483", scale=3, emission=0.2), (0, 15, 0.01), coll=col)
    for k in range(4):
        decor.hill(f"{sid}_hill{k}", -24 + k * 16 + rng.uniform(-3, 3), 34 + rng.uniform(0, 8), rng.uniform(10, 16), rng.uniform(4, 8),
                   ["#95D5B2", "#74C69D", "#B7E4C7", "#52B788"][k % 4], col)
    for k in range(26):
        x = -18 + k * 1.45 + rng.uniform(-0.4, 0.4)
        decor.far_tree(f"{sid}_ft{k}", x, 16 + rng.uniform(0, 4), rng.uniform(3.5, 5.5), col, rng)
    for k, (fx, fy) in enumerate(decor.scatter_avoiding(rng, 8, (-6, 6), (0.8, 6), [(0, y, 1.6) for y in range(0, 12)])):
        decor.flower_patch(f"{sid}_fl{k}", fx, fy, rng, col)
    decor.fence(sid + "_fence", -7.0, 7.0, 8.5, col)
    for k in range(5):
        decor.cloud(f"{sid}_cloud{k}", (rng.uniform(-16, 16), 45 + rng.uniform(0, 10), rng.uniform(12, 20)), rng.uniform(2.0, 3.8), col, rng)


def build_set(spec, coll=None, avoid=None):
    """avoid : [(x, y, rayon)] positions d'accessoires/personnages du plan à ne pas encombrer."""
    kit = spec["kit"]
    pal = dict(PALETTES[kit])
    pal.update(spec.get("palette", {}))
    w, d = spec.get("size", [8.0, 6.0])
    rng = random.Random(spec.get("seed", 7))
    sid = spec["id"]
    col = bpy.data.collections.new(sid)
    (coll or bpy.context.scene.collection).children.link(col)
    solids = []
    avoid = list(avoid or [])
    rich = spec.get("use_kit_dressing", True)
    if kit in INTERIOR:
        _interior_shell(sid, kit, pal, w, d, col, spec.get("surfaces"))
        if rich:
            _wall_decor(sid, kit, pal, d, col, rng)
            _clutter(sid, kit, col, rng, avoid)
    elif kit == "street":
        _street(sid, pal, col, rng)
    elif kit == "park":
        _park(sid, pal, col, rng)
    elif kit == "beach":
        _beach(sid, pal, col, rng)
    elif kit == "car_interior":
        _car_interior(sid, pal, col, rng, solids)
    elif kit == "generic_exterior":
        _generic_exterior(sid, pal, col, rng, spec.get("surfaces", {}), spec.get("backdrop", ["hills", "clouds"]))
    else:   # studio_void
        floor_m = core.toon_mat(sid + "_floor", pal["floor"], rough=0.85, emission=0.2)
        core.box(sid + "_ground", (60, 60, 0.1), floor_m, (0, 20, -0.05), coll=col)
        core.box(sid + "_cyc", (30, 0.3, 12), core.toon_mat(sid + "_wall", pal["wall"], emission=0.2), (0, 8, 6), coll=col)
    # habillage (accessoires de bibliothèque)
    dressing = []
    if rich:
        for t in KIT_DRESSING[kit]:
            dressing.append({"type": t[0], "pos": [t[1], t[2]], "rot_deg": t[3], "scale": t[4] if len(t) > 4 else 1.0, "z": t[5] if len(t) > 5 else 0.0})
    dressing += spec.get("dressing", [])
    for i, item in enumerate(dressing):
        o = props.build(item["type"], f"{sid}_{item['type']}_{i}", item.get("color"), item.get("scale", 1.0), item.get("label"), col, parts=item.get("parts"))
        o.location = (item["pos"][0], item["pos"][1], item.get("z", 0.0))
        o.rotation_euler = (0, 0, D(item.get("rot_deg", 0)))
        if item["type"] not in ("rug", "window", "painting", "building", "streetlight"):
            solids.append(o)
    marks = dict(BASE_MARKS)
    marks.update(KIT_MARKS[kit])
    marks.update({k: tuple(v) for k, v in spec.get("marks", {}).items()})
    bounds = (-w / 2 + 0.3, w / 2 - 0.3, -d / 2 - 3, d / 2 - 0.3) if kit in INTERIOR else ((-1.0, 1.0, -0.3, 1.6) if kit == "car_interior" else (-20, 20, -4, 8))
    sky = None if kit in INTERIOR or kit == "studio_void" else (_shade(pal.get("sky", "#8ECAE6"), 1.25), pal.get("sky", "#8ECAE6"))
    return {"collection": col, "marks": marks, "solids": solids, "bounds": bounds, "palette": pal, "kit": kit, "interior": kit in INTERIOR, "sky": sky}


def _sea(sid, col, y0=6.0):
    """Mer cartoon : bandes d'écume + dégradé lumineux jusqu'à l'horizon."""
    sea = core.pattern_mat(sid + "_sea", "noise", "#0096C7", "#48CAE4", scale=0.4, emission=0.35)
    core.box(sid + "_sea", (120, 80, 0.1), sea, (0, y0 + 40, -0.02), coll=col)
    foam = core.toon_mat(sid + "_foam", "#FFFFFF", emission=0.6)
    for k in range(3):
        core.box(sid + f"_foam{k}", (120, 0.12 + k * 0.05, 0.02), foam, (0, y0 + 0.2 + k * 1.6, 0.04), coll=col)


def _beach(sid, pal, col, rng):
    sand = core.pattern_mat(sid + "_sand", "noise", pal["floor"], _shade(pal["floor"], 0.85), scale=1.5, emission=0.15)
    core.box(sid + "_sand", (80, 14, 0.1), sand, (0, 0, -0.05), coll=col)
    _sea(sid, col, 6.5)
    for k in range(6):
        decor.cloud(f"{sid}_cloud{k}", (rng.uniform(-18, 18), 45 + rng.uniform(0, 12), rng.uniform(10, 18)), rng.uniform(2.0, 3.6), col, rng)
    for k in range(3):   # îlot lointain
        decor.hill(f"{sid}_isle{k}", -20 + k * 18 + rng.uniform(-3, 3), 70, rng.uniform(6, 10), rng.uniform(2, 4), "#52B788", col)
    for k, (fx, fy) in enumerate(decor.scatter_avoiding(rng, 10, (-6, 6), (-0.5, 4.5), [(0, 0.5, 1.4)])):
        core.ball(f"{sid}_shell{k}", (0.05, 0.04, 0.02), core.toon_mat("dec_shell", rng.choice(["#FFCAD4", "#FFF1E6", "#F4ACB7"]), emission=0.3), (fx, fy, 0.01), coll=col, detail=1)


def _car_interior(sid, pal, col, rng, solids):
    """Habitacle vu depuis le pare-brise (caméra côté -Y) : deux rangées de sièges, volant, toit, vitres avec vue."""
    shell = core.toon_mat(sid + "_shell", pal["wall"], emission=0.2)
    seat = core.pattern_mat(sid + "_seat", "stripes", pal.get("accent", "#E07A5F"), _shade(pal.get("accent", "#E07A5F"), 0.8), scale=6, plane='xz', emission=0.2)
    core.box(sid + "_floor", (2.0, 3.0, 0.1), core.toon_mat(sid + "_floorm", pal["floor"], emission=0.1), (0, 0.7, 0.0), coll=col)
    for row, y in ((0, 0.45), (1, 1.35)):
        for s in ((-0.42, 0.42) if row == 0 else (-0.42, 0.42)):
            core.box(f"{sid}_seat{row}{s}", (0.55, 0.5, 0.18), seat, (s, y - 0.05, 0.36), coll=col, ink=0.008, bevel=0.05)
            core.box(f"{sid}_back{row}{s}", (0.55, 0.16, 0.7), seat, (s, y + 0.25, 0.75), (D(-8), 0, 0), coll=col, ink=0.008, bevel=0.05)
            core.box(f"{sid}_head{row}{s}", (0.3, 0.12, 0.2), seat, (s, y + 0.3, 1.2), coll=col, ink=0.006, bevel=0.04)
    core.box(sid + "_roof", (2.0, 2.6, 0.08), shell, (0, 0.8, 1.72), coll=col)
    view = core.gradient_emit_mat(sid + "_view", "#A7C957", pal.get("sky", "#8ECAE6"), 0.9, 1.0)
    for s in (1, -1):
        core.box(f"{sid}_door{s}", (0.08, 2.6, 0.7), shell, (s * 0.95, 0.8, 0.45), coll=col, ink=0.008)
        core.box(f"{sid}_win{s}", (0.04, 2.2, 0.75), view, (s * 0.97, 0.8, 1.2), coll=col)
        core.box(f"{sid}_pillar{s}", (0.08, 0.1, 0.8), shell, (s * 0.95, -0.3, 1.25), (0, s * D(-12), 0), coll=col)
    core.box(sid + "_rearwin", (1.8, 0.04, 0.6), view, (0, 2.05, 1.25), coll=col)
    # tableau de bord bas et fin : il ne doit jamais masquer le buste des passagers
    core.box(sid + "_dash", (2.0, 0.35, 0.1), core.toon_mat(sid + "_dashm", _shade(pal["wall"], 0.8), emission=0.15), (0, -0.62, 0.55), coll=col, ink=0.006)
    wheel = core.toon_mat(sid + "_wheel", "#1A1A1A")
    core.torus(sid + "_steer", 0.19, 0.022, wheel, (-0.42, -0.15, 0.95), (D(65), 0, 0), coll=col)
    core.cyl(sid + "_column", 0.03, 0.03, 0.35, wheel, (-0.42, -0.3, 0.85), (D(65), 0, 0), coll=col)
    core.box(sid + "_mirror", (0.25, 0.04, 0.07), core.toon_mat(sid + "_mir", "#CED4DA", emission=0.3), (0, -0.2, 1.6), coll=col, ink=0.004)
    core.ball(sid + "_dice", (0.04,) * 3, core.toon_mat(sid + "_dicem", "#FFFFFF", emission=0.3), (0.05, -0.2, 1.45), coll=col, detail=1)


def _generic_exterior(sid, pal, col, rng, surf, backdrop):
    gk = surf.get("floor", "grass")
    g = core.pattern_mat(sid + "_ground", gk, pal["floor"], _shade(pal["floor"], 0.8), scale=0.6 if gk == "grass" else 1.0, emission=0.18)
    core.box(sid + "_ground", (80, 80, 0.1), g, (0, 25, -0.05), coll=col)
    if "sea" in backdrop:
        _sea(sid, col, 12.0)
    if "hills" in backdrop:
        for k in range(4):
            decor.hill(f"{sid}_hill{k}", -24 + k * 16 + rng.uniform(-3, 3), 34 + rng.uniform(0, 8), rng.uniform(10, 16), rng.uniform(4, 8),
                       ["#95D5B2", "#74C69D", "#B7E4C7", "#52B788"][k % 4], col)
    if "trees" in backdrop:
        for k in range(26):
            decor.far_tree(f"{sid}_ft{k}", -18 + k * 1.45 + rng.uniform(-0.4, 0.4), 16 + rng.uniform(0, 4), rng.uniform(3.5, 5.5), col, rng)
    if "skyline" in backdrop:
        decor.skyline(sid + "_skyline", 26.0, rng, col)
    if "clouds" in backdrop:
        for k in range(5):
            decor.cloud(f"{sid}_cloud{k}", (rng.uniform(-16, 16), 45 + rng.uniform(0, 10), rng.uniform(12, 20)), rng.uniform(2.0, 3.8), col, rng)
