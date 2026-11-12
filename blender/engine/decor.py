"""Habillage d'ambiance des décors : objets muraux, petits objets posés, arrière-plans extérieurs.

Ces éléments ne sont PAS des accessoires de l'histoire (pas d'id, pas de schéma) : ils rendent un lieu crédible
et dense, comme un décor de dessin animé. Tout est procédural, seedé et reproductible. Règle de mise en scène :
rien n'est placé côté caméra (y < 0) au centre du décor, pour ne jamais boucher le premier plan.
"""
import math
import random
from mathutils import Vector
from . import core

D = math.radians
M = core.toon_mat

POSTER_COLORS = ["#E63946", "#F4A261", "#2A9D8F", "#8338EC", "#FFBE0B", "#3A86FF", "#FB5607", "#06D6A0"]
OBJ_COLORS = ["#E63946", "#F1FAEE", "#A8DADC", "#457B9D", "#FFB703", "#FB8500", "#8ECAE6", "#06D6A0", "#EF476F"]


# ------------------------------------------------------------------ objets muraux (face -Y, collés au mur y = wy)
def poster(n, x, z, wy, w, h, rng, coll):
    root = core.empty(n, (x, wy - 0.03, z), None, coll)
    c1, c2 = rng.sample(POSTER_COLORS, 2)
    core.box(n + "_frame", (w + 0.06, 0.03, h + 0.06), M("dec_frame_dark", "#2B2D42"), (0, 0, 0), parent=root, coll=coll, ink=0.006)
    core.box(n + "_bg", (w, 0.035, h), M(f"dec_poster_{c1}", c1, emission=0.25), (0, -0.003, 0), parent=root, coll=coll)
    shape = rng.choice(("circle", "star", "bars"))
    mat2 = M(f"dec_poster_{c2}", c2, emission=0.3)
    if shape == "circle":
        core.ball(n + "_c", (w * 0.28, 0.01, w * 0.28), mat2, (0, -0.025, h * 0.1), parent=root, coll=coll, detail=2)
    elif shape == "star":
        core.star(n + "_s", w * 0.3, w * 0.13, 5, 0.008, mat2, (0, -0.025, h * 0.08), parent=root, coll=coll)
    else:
        for i in range(3):
            core.box(n + f"_b{i}", (w * 0.7, 0.01, h * 0.08), mat2, (0, -0.025, h * (0.25 - i * 0.2)), parent=root, coll=coll)
    return root


def clock(n, x, z, wy, coll):
    root = core.empty(n, (x, wy - 0.04, z), None, coll)
    core.cyl(n + "_body", 0.22, 0.22, 0.05, M("dec_clock", "#F8F9FA", emission=0.2), (0, 0, 0), (D(90), 0, 0), parent=root, coll=coll, ink=0.01, seg=20)
    core.torus(n + "_rim", 0.22, 0.02, M("dec_clock_rim", "#E63946"), (0, -0.02, 0), (D(90), 0, 0), parent=root, coll=coll)
    hand = M("dec_hand", "#1A1A1A")
    core.box(n + "_h1", (0.02, 0.01, 0.13), hand, (0.0, -0.035, 0.05), parent=root, coll=coll)
    core.box(n + "_h2", (0.09, 0.01, 0.02), hand, (0.04, -0.035, 0.0), parent=root, coll=coll)
    return root


def wall_shelf(n, x, z, wy, width, rng, coll):
    root = core.empty(n, (x, wy - 0.13, z), None, coll)
    core.box(n + "_board", (width, 0.24, 0.035), M("dec_shelf", "#8D5A3B"), (0, 0, 0), parent=root, coll=coll, ink=0.006)
    xx = -width / 2 + 0.06
    i = 0
    while xx < width / 2 - 0.08:
        kind = rng.random()
        if kind < 0.6:   # livre
            h = rng.uniform(0.16, 0.26)
            t = rng.uniform(0.035, 0.06)
            col = rng.choice(OBJ_COLORS)
            core.box(n + f"_book{i}", (t, 0.17, h), M(f"dec_book_{col}", col, emission=0.15), (xx + t / 2, 0, h / 2 + 0.02), (0, rng.uniform(-0.05, 0.05), 0), parent=root, coll=coll)
            xx += t + 0.005
        elif kind < 0.8:   # bocal
            col = rng.choice(OBJ_COLORS)
            core.cyl(n + f"_jar{i}", 0.045, 0.045, 0.14, M(f"dec_jar_{col}", col, emission=0.15), (xx + 0.05, 0, 0.09), parent=root, coll=coll, seg=10, ink=0.004)
            xx += 0.11
        else:   # petite plante
            core.cyl(n + f"_pot{i}", 0.05, 0.04, 0.09, M("dec_pot", "#C46A3C"), (xx + 0.05, 0, 0.065), parent=root, coll=coll, seg=8)
            core.ball(n + f"_leaf{i}", (0.07, 0.06, 0.07), M("dec_leaf", "#3FA34D", emission=0.15), (xx + 0.05, 0, 0.15), parent=root, coll=coll, detail=1, ink=0.004)
            xx += 0.12
        i += 1
    return root


def pendant_lamp(n, x, y, top, coll, col="#FFD166"):
    root = core.empty(n, (x, y, top), None, coll)
    core.cyl(n + "_cord", 0.008, 0.008, 0.9, M("dec_cord", "#222222"), (0, 0, -0.45), parent=root, coll=coll)
    core.cyl(n + "_shade", 0.06, 0.24, 0.2, M(f"dec_shade_{col}", col, emission=0.3), (0, 0, -0.98), parent=root, coll=coll, ink=0.008, seg=14)
    core.ball(n + "_bulb", (0.06,) * 3, core.emit_mat("dec_bulb", "#FFF3C4", 6.0), (0, 0, -1.08), parent=root, coll=coll, detail=1)
    return root


def curtains(n, x, z, wy, width, col, coll):
    root = core.empty(n, (x, wy - 0.12, z), None, coll)
    core.cyl(n + "_rod", 0.015, 0.015, width + 0.4, M("dec_rod", "#5C3D2E"), (0, 0, 0.62), (0, D(90), 0), parent=root, coll=coll)
    for s in (1, -1):
        for k in range(3):
            core.cyl(n + f"_fold{s}{k}", 0.06, 0.07, 1.3, M(f"dec_curtain_{col}", col, emission=0.15), (s * (width / 2 + 0.05 + k * 0.08), 0, 0.0), parent=root, coll=coll, seg=8, ink=0.006)
    return root


def wainscot(n, w, wy, top_hex, low_hex, coll, side_x=None, depth=None):
    """Soubassement : panneau bas plus foncé + cimaise ; donne de la profondeur aux murs."""
    low = core.pattern_mat(n + "_m", "noise", low_hex, scale=0.8, emission=0.15)
    core.box(n + "_panel", (w, 0.03, 0.9), low, (0, wy - 0.015, 0.45), coll=coll)
    core.box(n + "_rail", (w, 0.06, 0.05), M(n + "_rail", top_hex), (0, wy - 0.03, 0.92), coll=coll, ink=0.005)
    core.box(n + "_crown", (w, 0.08, 0.08), M(n + "_rail", top_hex), (0, wy - 0.04, 3.12), coll=coll, ink=0.005)


# ------------------------------------------------------------------ petits objets posés sur une surface
def small_item(n, kind, x, y, z, rng, coll):
    col = rng.choice(OBJ_COLORS)
    m = M(f"dec_item_{col}", col, emission=0.18)
    if kind == "jar":
        core.cyl(n, 0.05, 0.05, 0.16, m, (x, y, z + 0.08), coll=coll, seg=10, ink=0.004)
        core.cyl(n + "_lid", 0.055, 0.055, 0.025, M("dec_lid", "#6C757D"), (x, y, z + 0.17), coll=coll, seg=10)
    elif kind == "bottle":
        core.cyl(n, 0.035, 0.035, 0.2, m, (x, y, z + 0.1), coll=coll, seg=8, ink=0.004)
        core.cyl(n + "_neck", 0.015, 0.015, 0.07, m, (x, y, z + 0.235), coll=coll, seg=6)
    elif kind == "plates":
        for k in range(rng.randint(2, 5)):
            core.cyl(n + f"_{k}", 0.11, 0.09, 0.018, M("dec_plate", "#F8F9FA", emission=0.2), (x, y, z + 0.012 + k * 0.02), coll=coll, seg=14)
    elif kind == "bowl":
        core.uvball(n, (0.13, 0.13, 0.07), M("dec_bowl", "#F4F1DE", emission=0.15), (x, y, z + 0.07), (D(180), 0, 0), coll=coll, seg=12, rings=6, zmin=0.0, ink=0.004)
        for k in range(3):
            fc = ["#E63946", "#FFB703", "#06D6A0"][k]
            core.ball(n + f"_fruit{k}", (0.045,) * 3, M(f"dec_fruit_{fc}", fc, emission=0.2), (x + (k - 1) * 0.05, y, z + 0.09), coll=coll, detail=1)
    elif kind == "board":
        core.box(n, (0.32, 0.2, 0.02), core.pattern_mat("dec_board", "wood", "#C68B59", "#A0693A", scale=4), (x, y, z + 0.01), (0, 0, rng.uniform(-0.3, 0.3)), coll=coll, ink=0.003)
    elif kind == "books":
        for k in range(rng.randint(2, 4)):
            c2 = rng.choice(OBJ_COLORS)
            core.box(n + f"_{k}", (0.22, 0.16, 0.035), M(f"dec_book_{c2}", c2, emission=0.15), (x, y, z + 0.018 + k * 0.037), (0, 0, rng.uniform(-0.3, 0.3)), coll=coll)
    elif kind == "mug":
        core.cyl(n, 0.045, 0.045, 0.1, m, (x, y, z + 0.05), coll=coll, seg=10, ink=0.003)


# ------------------------------------------------------------------ extérieurs
def cloud(n, pos, s, coll, rng):
    root = core.empty(n, pos, None, coll)
    mat = M("dec_cloud", "#FFFFFF", emission=0.7)
    for k in range(5):
        r = s * rng.uniform(0.5, 0.9)
        core.ball(n + f"_{k}", (r * 1.3, r * 0.7, r), mat, ((k - 2) * s * 0.55, 0, rng.uniform(-0.1, 0.25) * s), parent=root, coll=coll, detail=2, ink=s * 0.03)
    return root


def far_tree(n, x, y, h, coll, rng, col="#2D6A4F"):
    shade = rng.uniform(0.85, 1.1)
    c = '#' + ''.join(f"{min(255, int(int(col[i:i + 2], 16) * shade)):02x}" for i in (1, 3, 5))
    core.cyl(n + "_t", 0.08 * h, 0.06 * h, 0.3 * h, M("dec_trunk", "#6B4226"), (x, y, 0.15 * h), coll=coll, seg=5)
    core.cyl(n + "_c", 0.32 * h, 0.0, 0.85 * h, M(f"dec_pine_{c}", c, emission=0.2), (x, y, 0.3 * h + 0.42 * h), coll=coll, seg=7, ink=0.01 * h)


def hill(n, x, y, rx, h, col, coll):
    core.uvball(n, (rx, rx * 0.5, h), core.pattern_mat(f"dec_hill_{col}", "grass", col, scale=0.2, emission=0.2), (x, y, 0), coll=coll, seg=16, rings=8, zmin=0.0, smooth=True)


def skyline(n, y, rng, coll, col="#9DB4C0"):
    x = -30.0
    i = 0
    while x < 30:
        w = rng.uniform(2.5, 5.0)
        h = rng.uniform(6, 16)
        core.box(n + f"_{i}", (w, 2.0, h), M(f"dec_sky_{col}", col, emission=0.35), (x + w / 2, y + rng.uniform(-1, 1), h / 2), coll=coll)
        for k in range(int(h // 2.2)):
            if rng.random() < 0.7:
                core.box(n + f"_{i}_w{k}", (w * 0.6, 0.05, 0.3), core.emit_mat("dec_skywin", "#FFE8A3", 0.6), (x + w / 2, y - 1.03, 1.2 + k * 2.2), coll=coll)
        x += w + rng.uniform(0.0, 0.6)
        i += 1


def facade(n, x, y, w, h, col, rng, coll, shop=None):
    """Immeuble cartoon : briques ou enduit, fenêtres encadrées, auvent, porte ; face -Y."""
    kind = rng.choice(("bricks", "noise"))
    core.box(n + "_body", (w, 3.0, h), core.pattern_mat(f"dec_facade_{kind}_{col}", kind, col, scale=1.0, plane='xz', emission=0.2), (x, y, h / 2), coll=coll, ink=0.02)
    core.box(n + "_roof", (w + 0.3, 3.3, 0.3), M("dec_roof", "#5C4033"), (x, y, h + 0.15), coll=coll, ink=0.01)
    frame = M("dec_winframe", "#F8F9FA", emission=0.2)
    glass = core.gradient_emit_mat("dec_winglass", "#8ECAE6", "#CDEFFF", 1.0, 0.9)
    floors = int((h - 3.2) // 2.4)
    cols = max(1, int(w // 1.6))
    for f in range(floors):
        for c in range(cols):
            wx = x - w / 2 + (c + 0.5) * w / cols
            wz = 3.6 + f * 2.4
            core.box(n + f"_wf{f}{c}", (0.95, 0.06, 1.25), frame, (wx, y - 1.52, wz), coll=coll)
            core.box(n + f"_wg{f}{c}", (0.8, 0.06, 1.1), glass, (wx, y - 1.54, wz), coll=coll)
    awn = rng.choice(POSTER_COLORS)
    core.box(n + "_awning", (w * 0.8, 0.9, 0.12), core.pattern_mat(f"dec_awning_{awn}", "stripes", awn, "#F8F9FA", scale=1.2, plane='xy', emission=0.25),
             (x, y - 1.9, 2.75), (D(-18), 0, 0), coll=coll, ink=0.008)
    core.box(n + "_door", (1.1, 0.06, 2.2), M("dec_door", "#5C3D2E"), (x - w * 0.2, y - 1.52, 1.1), coll=coll, ink=0.006)
    core.box(n + "_shopwin", (w * 0.35, 0.06, 1.4), glass, (x + w * 0.15, y - 1.53, 1.3), coll=coll)
    if shop:
        core.box(n + "_sign", (w * 0.7, 0.08, 0.45), M(f"dec_sign_{awn}", "#2B2D42", emission=0.2), (x, y - 1.6, 3.3), coll=coll, ink=0.006)
        core.text_obj(n + "_signtxt", shop, 0.32, core.emit_mat("dec_signtxt", "#FFD166", 1.5), (x, y - 1.66, 3.3), coll=coll, extrude=0.01)


def flower_patch(n, x, y, rng, coll):
    for k in range(6):
        c = rng.choice(["#FF4D6D", "#FFD166", "#FFFFFF", "#C77DFF"])
        p = Vector((x + rng.uniform(-0.4, 0.4), y + rng.uniform(-0.3, 0.3), 0.0))
        core.cyl(n + f"_st{k}", 0.008, 0.008, 0.18, M("dec_stem", "#2D6A4F"), (p.x, p.y, 0.09), coll=coll, seg=4)
        core.ball(n + f"_fl{k}", (0.045,) * 3, M(f"dec_flower_{c}", c, emission=0.3), (p.x, p.y, 0.2), coll=coll, detail=1)


def fence(n, x0, x1, y, coll):
    m = core.pattern_mat("dec_fence", "wood", "#E9D8A6", "#CDB380", scale=3)
    x = x0
    i = 0
    while x <= x1:
        core.box(n + f"_p{i}", (0.1, 0.06, 0.9), m, (x, y, 0.45), coll=coll, ink=0.004)
        x += 0.35
        i += 1
    for z in (0.3, 0.7):
        core.box(n + f"_r{z}", (x1 - x0, 0.04, 0.08), m, ((x0 + x1) / 2, y + 0.04, z), coll=coll)


def scatter_avoiding(rng, n, xr, yr, avoid, min_d=0.5):
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 30:
        tries += 1
        p = (rng.uniform(*xr), rng.uniform(*yr))
        if any((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2 < (a[2] if len(a) > 2 else min_d) ** 2 for a in avoid):
            continue
        pts.append(p)
    return pts
