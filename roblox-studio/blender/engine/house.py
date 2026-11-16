"""Décor « suburb » : maison de banlieue façon jeu en blocs (extérieur), quartier vivant autour.

Pelouse à plots, trottoir, allée, maison à étage avec toit à deux pans, porche, fenêtres à volets, garage et
allée de garage, boîte aux lettres, clôture, haies, massifs, arbres, maisons voisines, collines et nuages.
Repères : center, left, right, back, porch, door, mailbox, driveway, lawn_left, lawn_right, sidewalk.
"""
import math

import bmesh
import bpy

from . import core, decor

D = math.radians


def _m(name, col, rough=0.45, emission=0.12, metallic=0.0):
    return core.toon_mat(name, col, rough=rough, emission=emission, metallic=metallic)


def _b(name, size, mat, loc, col, rot=(0, 0, 0), bevel=0.02):
    o = core.box(name, size, mat, loc, rot, coll=col)
    if bevel:
        mod = o.modifiers.new("bevel", 'BEVEL')
        mod.width, mod.segments, mod.limit_method = bevel, 2, 'ANGLE'
    return o


def gable_roof(name, w, d, h, overhang, mat, loc, col):
    """Toit à deux pans : prisme triangulaire (faîtage selon X), débord sur les 4 côtés."""
    bm = bmesh.new()
    W, Dd = w / 2 + overhang, d / 2 + overhang
    v = [bm.verts.new(p) for p in ((-W, -Dd, 0), (W, -Dd, 0), (W, Dd, 0), (-W, Dd, 0), (-W, 0, h), (W, 0, h))]
    for f in ((0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)):
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    core.link(o, col)
    me.materials.append(mat)
    o.location = loc
    return o


def window(n, x, z, wy, w, h, col, shutter_col, frame, glass, coll, shutters=True):
    _b(n + "_frame", (w + 0.16, 0.12, h + 0.16), frame, (x, wy - 0.04, z), coll)
    _b(n + "_glass", (w, 0.06, h), glass, (x, wy - 0.08, z), coll, bevel=0)
    _b(n + "_cross_v", (0.06, 0.08, h), frame, (x, wy - 0.11, z), coll, bevel=0)
    _b(n + "_cross_h", (w, 0.08, 0.06), frame, (x, wy - 0.11, z), coll, bevel=0)
    _b(n + "_sill", (w + 0.3, 0.22, 0.07), frame, (x, wy - 0.12, z - h / 2 - 0.08), coll)
    if shutters:
        sm = _m(n + "_sh", shutter_col)
        for s in (1, -1):
            _b(n + f"_shutter{s}", (w * 0.42, 0.06, h + 0.1), sm, (x + s * (w / 2 + w * 0.26), wy - 0.05, z), coll)


def build(sid, pal, col, rng):
    wall = pal.get("wall", "#F6E7C1")
    accent = pal.get("accent", "#C0392B")
    trim = _m(sid + "_trim", "#FAFAFA", rough=0.4)
    glass = core.toon_mat(sid + "_glass", "#9FD3F5", rough=0.08, emission=0.35, metallic=0.0)
    # sol : pelouse à plots + trottoir + allée
    core.box(sid + "_lawn", (80, 80, 0.1), core.pattern_mat(sid + "_lawn", "studs", pal.get("floor", "#5DBB4A"), scale=1.0, emission=0.1), (0, 22, -0.05), coll=col)
    sw = core.pattern_mat(sid + "_sidewalk", "tiles", "#C9C7C2", "#B9B6B0", scale=1.0, emission=0.1)
    core.box(sid + "_sidewalk", (80, 2.4, 0.12), sw, (0, -2.6, 0.0), coll=col)
    core.box(sid + "_road", (80, 7.0, 0.08), core.pattern_mat(sid + "_road", "noise", "#4A4E57", scale=3, emission=0.05), (0, -7.4, -0.02), coll=col)
    core.box(sid + "_path", (1.5, 6.4, 0.06), core.pattern_mat(sid + "_pathm", "tiles", "#D8C3A5", "#C9B08F", scale=1.2, emission=0.1), (0, 1.0, 0.02), coll=col)
    core.box(sid + "_drive", (3.2, 8.6, 0.06), core.pattern_mat(sid + "_drivem", "noise", "#9A9A9A", scale=2, emission=0.05), (6.2, 0.1, 0.02), coll=col)
    # maison à étage
    wall_m = core.pattern_mat(sid + "_siding", "hstripes", wall, core_shade(wall, 0.9), scale=2.4, plane='xz', emission=0.1)
    hw, hd, hh = 9.0, 6.0, 5.4
    hy = 4.2 + hd / 2
    _b(sid + "_house", (hw, hd, hh), wall_m, (0, hy, hh / 2), col, bevel=0.03)
    _b(sid + "_floorband", (hw + 0.1, hd + 0.1, 0.18), trim, (0, hy, 2.75), col)
    _b(sid + "_base", (hw + 0.15, hd + 0.15, 0.35), _m(sid + "_basem", "#8D8D8D", rough=0.6), (0, hy, 0.17), col)
    roof_m = core.pattern_mat(sid + "_roof", "tiles", accent, core_shade(accent, 0.82), scale=2.0, plane='xz', emission=0.08)
    gable_roof(sid + "_roof", hw, hd, 2.4, 0.45, roof_m, (0, hy, hh), col)
    _b(sid + "_chimney", (0.7, 0.7, 2.0), core.pattern_mat(sid + "_brick", "bricks", "#B5523B", scale=2, plane='xz', emission=0.06), (2.6, hy + 1.2, hh + 1.6), col)
    front = 4.2
    # porte + porche
    door_m = _m(sid + "_door", pal.get("door", "#7A4E2D"), rough=0.5)
    _b(sid + "_doorframe", (1.35, 0.14, 2.35), trim, (0, front - 0.05, 1.18), col)
    _b(sid + "_door", (1.05, 0.1, 2.1), door_m, (0, front - 0.1, 1.08), col)
    core.box(sid + "_knob", (0.08, 0.08, 0.08), _m(sid + "_gold", "#F4C430", rough=0.25, metallic=0.7), (0.38, front - 0.18, 1.05), coll=col)
    _b(sid + "_step", (2.4, 1.0, 0.22), _m(sid + "_stepm", "#BDBDBD", rough=0.6), (0, front - 0.5, 0.11), col)
    _b(sid + "_awning", (2.8, 1.4, 0.14), roof_m, (0, front - 0.7, 2.75), col, rot=(D(-12), 0, 0))
    for s in (1, -1):
        _b(sid + f"_post{s}", (0.16, 0.16, 2.6), trim, (s * 1.25, front - 1.3, 1.3), col)
    lamp = core.emit_mat(sid + "_porchlamp", "#FFE3A3", 4.0)
    core.box(sid + "_porchlight", (0.18, 0.18, 0.26), lamp, (0.9, front - 0.12, 2.2), coll=col)
    # fenêtres
    sh_col = pal.get("shutter", "#2E5E8C")
    for i, x in enumerate((-3.0, -1.6, 1.6, 3.0)):
        window(f"{sid}_win{i}", x, 1.6, front, 0.9, 1.2, col, sh_col, trim, glass, col, shutters=abs(x) > 2)
    for i, x in enumerate((-2.8, 0.0, 2.8)):
        window(f"{sid}_upwin{i}", x, 4.0, front, 1.1, 1.1, col, sh_col, trim, glass, col)
    # garage
    gw = 3.6
    _b(sid + "_garage", (gw, 5.0, 3.0), wall_m, (hw / 2 + gw / 2 + 0.05, hy + 0.3, 1.5), col)
    gable_roof(sid + "_groof", gw, 5.0, 1.0, 0.3, roof_m, (hw / 2 + gw / 2 + 0.05, hy + 0.3, 3.0), col)
    _b(sid + "_gdoor", (3.0, 0.1, 2.3), core.pattern_mat(sid + "_gdoorm", "hstripes", "#F2F2F2", "#D6D6D6", scale=3.5, plane='xz', emission=0.1),
       (hw / 2 + gw / 2 + 0.05, hy + 0.3 - 2.53, 1.15), col)
    # jardin : haies, massifs, boîte aux lettres, clôture, arbres
    hedge = core.pattern_mat(sid + "_hedge", "grass", "#2F7D32", "#1E5E22", scale=2.0, emission=0.06)
    for s in (1, -1):
        _b(sid + f"_hedge{s}", (2.6, 0.7, 0.75), hedge, (s * 2.7, front - 0.55, 0.37), col, bevel=0.15)
        for k in range(4):
            decor.flower_patch(f"{sid}_flw{s}{k}", s * (1.6 + k * 0.55), front - 1.2, rng, col)
    post = _m(sid + "_mpost", "#5A3A22")
    _b(sid + "_mailpost", (0.12, 0.12, 1.1), post, (2.0, -1.0, 0.55), col)
    _b(sid + "_mailbox", (0.32, 0.55, 0.32), _m(sid + "_mailb", "#2B6CB0", rough=0.35), (2.0, -1.0, 1.2), col, bevel=0.06)
    _b(sid + "_flag", (0.04, 0.2, 0.12), _m(sid + "_flagm", "#E53935"), (2.18, -0.9, 1.35), col, bevel=0)
    picket = _m(sid + "_picket", "#FFFFFF", rough=0.45)
    for side, x0, x1 in ((-1, -12.0, -1.0), (1, 1.0, 4.4)):
        _b(f"{sid}_rail{side}", (x1 - x0, 0.06, 0.08), picket, ((x0 + x1) / 2, -1.25, 0.55), col, bevel=0)
        n = int((x1 - x0) / 0.32)
        for k in range(n + 1):
            _b(f"{sid}_pk{side}_{k}", (0.1, 0.05, 0.8), picket, (x0 + k * (x1 - x0) / max(1, n), -1.25, 0.4), col, bevel=0.01)
    # voisinage : maisons voisines simplifiées, arbres, collines, nuages
    for k, (x, c, r) in enumerate(((-15.0, "#A8DADC", "#355070"), (15.5, "#F4ACB7", "#6D597A"), (-26.0, "#FFE5B4", "#9C6644"), (27.0, "#CDEAC0", "#BC4749"))):
        _b(f"{sid}_nb{k}", (8.0, 6.0, 4.0), _m(f"{sid}_nbm{k}", c), (x, hy + 1.5, 2.0), col)
        gable_roof(f"{sid}_nbroof{k}", 8.0, 6.0, 2.0, 0.4, _m(f"{sid}_nbr{k}", r), (x, hy + 1.5, 4.0), col)
        for wx in (-2.0, 2.0):
            _b(f"{sid}_nbw{k}{wx}", (1.0, 0.08, 1.0), glass, (x + wx, hy + 1.5 - 3.02, 2.0), col, bevel=0)
    for k in range(4):
        decor.hill(f"{sid}_hill{k}", -30 + k * 20 + rng.uniform(-3, 3), 40 + rng.uniform(0, 8), rng.uniform(12, 18), rng.uniform(5, 9),
                   ["#95D5B2", "#74C69D", "#B7E4C7", "#52B788"][k % 4], col)
    for k in range(18):
        decor.far_tree(f"{sid}_ft{k}", -26 + k * 3.1 + rng.uniform(-0.6, 0.6), 20 + rng.uniform(0, 5), rng.uniform(4.0, 6.5), col, rng)
    for k in range(6):
        decor.cloud(f"{sid}_cloud{k}", (rng.uniform(-18, 18), 45 + rng.uniform(0, 10), rng.uniform(13, 22)), rng.uniform(2.2, 3.8), col, rng)


def core_shade(h, k):
    h = h.lstrip("#")
    return "#" + "".join(f"{max(0, min(255, int(int(h[i:i + 2], 16) * k))):02X}" for i in (0, 2, 4))
