"""Bibliothèque d'accessoires low-poly procéduraux. Chaque constructeur renvoie un empty racine posé au sol
(origine = point de contact au sol, avant = -Y). Dimensions réalistes en mètres, exagérées pour le cartoon.
"""
import math
from . import core

D = math.radians

# Hauteur de la surface utile (pour poser un accessoire dessus).
SURFACE_H = {"table": 0.76, "counter": 0.92, "desk": 0.76, "bed": 0.55, "sofa": 0.45, "chair": 0.47, "bench": 0.46,
             "stove": 0.92, "shelf": 1.2, "toilet": 0.42, "box": 0.4, "trash_can": 0.8, "car": 1.25}

DEFAULT_COLORS = {
    "sofa": "#C0504D", "table": "#A47148", "chair": "#8B5E3C", "tv": "#222222", "fridge": "#E8EEF2", "stove": "#D9D9D9",
    "counter": "#F0E6D2", "toaster": "#C9CED6", "plant": "#3FA34D", "lamp": "#F2C14E", "door": "#8D5A3B", "window": "#9FD3F5",
    "car": "#E63946", "tree": "#2E8B57", "bush": "#3C9A4A", "bench": "#9C6B3E", "desk": "#B07D4F", "computer": "#2F3640",
    "phone": "#1B1B1F", "mug": "#F4F1DE", "bed": "#6C8EBF", "toilet": "#FAFAFA", "box": "#C69C6D", "trash_can": "#5E6B73",
    "cake": "#F7B2BD", "sign": "#F9C80E", "pigeon": "#8A94A6", "cat": "#F28C28", "frying_pan": "#2B2B2B",
    "fire_extinguisher": "#D62828", "shopping_cart": "#B8C0C8", "shelf": "#9A7B5B", "rug": "#7B2D26",
    "streetlight": "#3D405B", "building": "#E9C46A", "painting": "#F4A261",
}


def build(ptype, name, color=None, scale=1.0, label=None, coll=None, ink=0.008):
    fn = globals().get("p_" + ptype)
    if fn is None:
        raise ValueError(f"type d'accessoire inconnu : {ptype}")
    col = color or DEFAULT_COLORS.get(ptype, "#AAAAAA")
    root = core.empty(name, (0, 0, 0), None, coll)
    fn(root, name, col, coll, ink, label)
    root.scale = (scale, scale, scale)
    root["prop_type"] = ptype
    return root


def M(name, hexcol, **kw):
    return core.toon_mat(name, hexcol, **kw)


def _darker(h, k=0.7):
    h = h.lstrip('#')
    return '#' + ''.join(f"{int(int(h[i:i + 2], 16) * k):02x}" for i in (0, 2, 4))


def p_sofa(r, n, c, coll, ink, label):
    m, m2 = M(n + "_m", c), M(n + "_m2", _darker(c, 0.8))
    core.box(n + "_base", (2.0, 0.9, 0.42), m, (0, 0, 0.21), parent=r, coll=coll, ink=ink, bevel=0.05)
    core.box(n + "_back", (2.0, 0.25, 0.55), m2, (0, 0.33, 0.66), parent=r, coll=coll, ink=ink, bevel=0.06)
    for s in (1, -1):
        core.box(n + f"_arm{s}", (0.22, 0.9, 0.62), m2, (s * 0.95, 0, 0.31), parent=r, coll=coll, ink=ink, bevel=0.06)
    for s in (1, -1):
        core.box(n + f"_cush{s}", (0.82, 0.6, 0.14), m, (s * 0.43, -0.08, 0.47), parent=r, coll=coll, ink=ink * 0.6, bevel=0.05)


def p_table(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.box(n + "_top", (1.4, 0.85, 0.07), m, (0, 0, 0.73), parent=r, coll=coll, ink=ink, bevel=0.02)
    for sx in (1, -1):
        for sy in (1, -1):
            core.box(n + f"_leg{sx}{sy}", (0.07, 0.07, 0.7), m, (sx * 0.62, sy * 0.36, 0.35), parent=r, coll=coll, ink=ink * 0.6)


def p_desk(r, n, c, coll, ink, label):
    m, m2 = M(n + "_m", c), M(n + "_m2", _darker(c, 0.75))
    core.box(n + "_top", (1.5, 0.75, 0.06), m, (0, 0, 0.73), parent=r, coll=coll, ink=ink)
    core.box(n + "_drawer", (0.45, 0.7, 0.68), m2, (0.5, 0, 0.35), parent=r, coll=coll, ink=ink)
    core.box(n + "_leg", (0.06, 0.7, 0.7), m2, (-0.7, 0, 0.35), parent=r, coll=coll, ink=ink)


def p_chair(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.box(n + "_seat", (0.48, 0.48, 0.06), m, (0, 0, 0.45), parent=r, coll=coll, ink=ink)
    core.box(n + "_back", (0.48, 0.06, 0.5), m, (0, 0.22, 0.73), parent=r, coll=coll, ink=ink)
    for sx in (1, -1):
        for sy in (1, -1):
            core.box(n + f"_leg{sx}{sy}", (0.05, 0.05, 0.45), m, (sx * 0.2, sy * 0.2, 0.22), parent=r, coll=coll)


def p_bench(r, n, c, coll, ink, label):
    m, mi = M(n + "_m", c), M(n + "_iron", "#2F2F2F")
    for i in range(3):
        core.box(n + f"_slat{i}", (1.6, 0.12, 0.04), m, (0, -0.15 + i * 0.15, 0.45), parent=r, coll=coll, ink=ink * 0.6)
    for i in range(2):
        core.box(n + f"_bslat{i}", (1.6, 0.04, 0.12), m, (0, 0.22, 0.62 + i * 0.16), parent=r, coll=coll, ink=ink * 0.6)
    for s in (1, -1):
        core.box(n + f"_leg{s}", (0.06, 0.5, 0.45), mi, (s * 0.7, 0, 0.22), parent=r, coll=coll, ink=ink * 0.6)


def p_tv(r, n, c, coll, ink, label):
    m, scr = M(n + "_m", c), core.emit_mat(n + "_screen", "#3D7DD8", 1.3)
    core.box(n + "_cab", (1.6, 0.45, 0.5), M(n + "_cab", "#6B4F3A"), (0, 0, 0.25), parent=r, coll=coll, ink=ink)
    core.box(n + "_frame", (1.3, 0.08, 0.78), m, (0, 0.05, 0.92), parent=r, coll=coll, ink=ink)
    core.box(n + "_scr", (1.18, 0.01, 0.66), scr, (0, 0.005, 0.92), parent=r, coll=coll)


def p_fridge(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.05)
    core.box(n + "_body", (0.75, 0.7, 1.8), m, (0, 0, 0.9), parent=r, coll=coll, ink=ink, bevel=0.04)
    core.box(n + "_split", (0.76, 0.01, 0.02), M(n + "_g", "#999999"), (0, -0.351, 1.2), parent=r, coll=coll)
    for z in (1.5, 0.75):
        core.box(n + f"_h{z}", (0.04, 0.05, 0.3), M(n + "_g", "#999999"), (0.28, -0.37, z), parent=r, coll=coll)


def p_stove(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.box(n + "_body", (0.75, 0.65, 0.9), m, (0, 0, 0.45), parent=r, coll=coll, ink=ink)
    core.box(n + "_oven", (0.6, 0.01, 0.45), M(n + "_glass", "#222222"), (0, -0.33, 0.4), parent=r, coll=coll)
    for sx in (1, -1):
        for sy in (1, -1):
            core.cyl(n + f"_burn{sx}{sy}", 0.11, 0.11, 0.02, M(n + "_b", "#1A1A1A"), (sx * 0.18, sy * 0.15, 0.91), parent=r, coll=coll)


def p_counter(r, n, c, coll, ink, label):
    core.box(n + "_body", (2.2, 0.65, 0.86), M(n + "_m", _darker(c, 0.85)), (0, 0, 0.43), parent=r, coll=coll, ink=ink)
    core.box(n + "_top", (2.25, 0.7, 0.06), M(n + "_top", c), (0, 0, 0.89), parent=r, coll=coll, ink=ink)
    for i in range(3):
        core.box(n + f"_door{i}", (0.6, 0.01, 0.6), M(n + "_d", _darker(c, 0.7)), (-0.72 + i * 0.72, -0.33, 0.42), parent=r, coll=coll)


def p_toaster(r, n, c, coll, ink, label):
    m = M(n + "_m", c, rough=0.3, metallic=0.5)
    core.box(n + "_body", (0.32, 0.2, 0.22), m, (0, 0, 0.11), parent=r, coll=coll, ink=ink, bevel=0.035)
    for s in (1, -1):
        core.box(n + f"_slot{s}", (0.2, 0.035, 0.01), M(n + "_slot", "#111111"), (0, s * 0.045, 0.222), parent=r, coll=coll)
    core.box(n + "_lever", (0.03, 0.06, 0.03), M(n + "_lev", "#222222"), (0.17, 0, 0.12), parent=r, coll=coll)
    core.ball(n + "_knob", (0.025,) * 3, M(n + "_lev", "#222222"), (0.165, -0.06, 0.06), parent=r, coll=coll, detail=1)


def p_plant(r, n, c, coll, ink, label):
    core.cyl(n + "_pot", 0.17, 0.13, 0.32, M(n + "_pot", "#C46A3C"), parent=r, coll=coll, ink=ink, base_at_origin=True)
    for i in range(6):
        a = 2 * math.pi * i / 6
        core.ball(n + f"_leaf{i}", (0.1, 0.05, 0.28), M(n + "_m", c), (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.55), (math.sin(a) * 0.5, -math.cos(a) * 0.5, 0), parent=r, coll=coll, ink=ink * 0.5, detail=1)


def p_lamp(r, n, c, coll, ink, label):
    core.cyl(n + "_base", 0.16, 0.16, 0.04, M(n + "_b", "#333333"), parent=r, coll=coll, base_at_origin=True)
    core.cyl(n + "_pole", 0.02, 0.02, 1.4, M(n + "_b", "#333333"), parent=r, coll=coll, base_at_origin=True)
    core.cyl(n + "_shade", 0.25, 0.15, 0.3, core.emit_mat(n + "_shade", c, 0.8), (0, 0, 1.5), parent=r, coll=coll, ink=ink)


def p_door(r, n, c, coll, ink, label):
    core.box(n + "_frame", (1.05, 0.12, 2.15), M(n + "_f", "#EDE6DA"), (0, 0, 1.075), parent=r, coll=coll, ink=ink)
    core.box(n + "_leaf", (0.9, 0.06, 2.05), M(n + "_m", c), (0, -0.04, 1.03), parent=r, coll=coll, ink=ink)
    core.ball(n + "_knob", (0.04,) * 3, M(n + "_k", "#F4C430", metallic=0.6), (0.35, -0.1, 1.0), parent=r, coll=coll, detail=1)


def p_window(r, n, c, coll, ink, label):
    """Fenêtre avec une vraie « vue » : ciel en dégradé, collines, petit immeuble lointain."""
    core.box(n + "_frame", (1.3, 0.1, 1.1), M(n + "_f", "#F5F5F5", emission=0.2), (0, 0, 1.55), parent=r, coll=coll, ink=ink)
    core.box(n + "_glass", (1.15, 0.02, 0.95), core.gradient_emit_mat(n + "_sky", "#E8F6FF", c, 0.95, 1.0), (0, -0.04, 1.55), parent=r, coll=coll)
    core.uvball(n + "_hill1", (0.45, 0.01, 0.22), core.emit_mat(n + "_hillA", "#74C69D", 0.9), (-0.3, -0.052, 1.08), parent=r, coll=coll, seg=12, rings=6, zmin=0.0)
    core.uvball(n + "_hill2", (0.55, 0.01, 0.16), core.emit_mat(n + "_hillB", "#95D5B2", 0.9), (0.3, -0.051, 1.08), parent=r, coll=coll, seg=12, rings=6, zmin=0.0)
    core.box(n + "_bld", (0.14, 0.01, 0.38), core.emit_mat(n + "_bldc", "#B8C0FF", 0.8), (0.32, -0.05, 1.27), parent=r, coll=coll)
    core.ball(n + "_cloud", (0.13, 0.01, 0.05), core.emit_mat(n + "_cl", "#FFFFFF", 1.2), (-0.25, -0.053, 1.85), parent=r, coll=coll, detail=1)
    core.box(n + "_bar", (0.05, 0.03, 0.95), M(n + "_f", "#F5F5F5", emission=0.2), (0, -0.06, 1.55), parent=r, coll=coll)
    core.box(n + "_hbar", (1.15, 0.03, 0.05), M(n + "_f", "#F5F5F5", emission=0.2), (0, -0.06, 1.55), parent=r, coll=coll)
    core.box(n + "_sill", (1.4, 0.18, 0.05), M(n + "_f", "#F5F5F5", emission=0.2), (0, -0.08, 1.05), parent=r, coll=coll, ink=ink * 0.5)


def p_car(r, n, c, coll, ink, label):
    m = M(n + "_m", c, rough=0.4)
    core.box(n + "_body", (1.8, 3.9, 0.7), m, (0, 0, 0.6), parent=r, coll=coll, ink=ink, bevel=0.12)
    core.box(n + "_cabin", (1.6, 2.0, 0.6), m, (0, 0.2, 1.2), parent=r, coll=coll, ink=ink, bevel=0.12)
    core.box(n + "_wind", (1.5, 0.05, 0.45), M(n + "_glass", "#9FD3F5", emission=0.2), (0, -0.82, 1.2), (D(-25), 0, 0), parent=r, coll=coll)
    for sx in (1, -1):
        for sy in (1, -1):
            core.cyl(n + f"_wheel{sx}{sy}", 0.36, 0.36, 0.25, M(n + "_tire", "#1A1A1A"), (sx * 0.85, sy * 1.25, 0.36), (0, D(90), 0), parent=r, coll=coll, ink=ink, seg=10)
    for s in (1, -1):
        core.ball(n + f"_light{s}", (0.14, 0.05, 0.1), core.emit_mat(n + "_hl", "#FFF3B0", 2), (s * 0.6, -1.95, 0.7), parent=r, coll=coll, detail=1)


def p_tree(r, n, c, coll, ink, label):
    core.cyl(n + "_trunk", 0.18, 0.12, 2.0, M(n + "_trunk", "#7A4E2D"), parent=r, coll=coll, ink=ink, base_at_origin=True, seg=6)
    for i, (x, y, z, s) in enumerate(((0, 0, 2.5, 1.0), (0.5, 0.2, 2.1, 0.7), (-0.5, -0.1, 2.2, 0.75), (0.1, -0.4, 2.9, 0.6))):
        core.ball(n + f"_crown{i}", (0.9 * s, 0.9 * s, 0.8 * s), M(n + "_m", c), (x, y, z), parent=r, coll=coll, ink=ink, detail=1)


def p_bush(r, n, c, coll, ink, label):
    for i, (x, z, s) in enumerate(((0, 0.35, 0.5), (0.4, 0.3, 0.38), (-0.4, 0.28, 0.4))):
        core.ball(n + f"_b{i}", (s, s * 0.9, s * 0.8), M(n + "_m", c), (x, 0, z), parent=r, coll=coll, ink=ink, detail=1)


def p_computer(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.box(n + "_screen", (0.55, 0.04, 0.36), m, (0, 0, 0.3), parent=r, coll=coll, ink=ink)
    core.box(n + "_disp", (0.5, 0.01, 0.31), core.emit_mat(n + "_disp", "#7FDBFF", 1.2), (0, -0.025, 0.3), parent=r, coll=coll)
    core.box(n + "_stand", (0.06, 0.06, 0.12), m, (0, 0.02, 0.06), parent=r, coll=coll)
    core.box(n + "_kb", (0.45, 0.15, 0.02), m, (0, -0.25, 0.01), parent=r, coll=coll, ink=ink * 0.5)


def p_phone(r, n, c, coll, ink, label):
    core.box(n + "_body", (0.08, 0.012, 0.16), M(n + "_m", c), (0, 0, 0.08), parent=r, coll=coll, ink=0.003, bevel=0.008)
    core.box(n + "_scr", (0.07, 0.002, 0.14), core.emit_mat(n + "_scr", "#5AC8FA", 1.5), (0, -0.007, 0.08), parent=r, coll=coll)


def p_mug(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.cyl(n + "_body", 0.045, 0.045, 0.1, m, parent=r, coll=coll, ink=0.003, base_at_origin=True, seg=10)
    core.torus(n + "_handle", 0.03, 0.008, m, (0.055, 0, 0.05), (D(90), 0, 0), parent=r, coll=coll)


def p_bed(r, n, c, coll, ink, label):
    core.box(n + "_frame", (1.5, 2.1, 0.35), M(n + "_f", "#8B5E3C"), (0, 0, 0.18), parent=r, coll=coll, ink=ink)
    core.box(n + "_mat", (1.4, 2.0, 0.18), M(n + "_m", c), (0, 0, 0.45), parent=r, coll=coll, ink=ink, bevel=0.04)
    core.box(n + "_pillow", (0.6, 0.35, 0.14), M(n + "_p", "#FFFFFF", emission=0.1), (0, 0.75, 0.6), parent=r, coll=coll, ink=ink, bevel=0.05)
    core.box(n + "_head", (1.5, 0.08, 0.9), M(n + "_f", "#8B5E3C"), (0, 1.05, 0.45), parent=r, coll=coll, ink=ink)


def p_toilet(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.08)
    core.cyl(n + "_base", 0.18, 0.22, 0.4, m, parent=r, coll=coll, ink=ink, base_at_origin=True, seg=10)
    core.torus(n + "_seat", 0.2, 0.04, m, (0, -0.05, 0.42), parent=r, coll=coll)
    core.box(n + "_tank", (0.45, 0.2, 0.4), m, (0, 0.25, 0.6), parent=r, coll=coll, ink=ink, bevel=0.03)


def p_box(r, n, c, coll, ink, label):
    core.box(n + "_body", (0.5, 0.5, 0.4), M(n + "_m", c), (0, 0, 0.2), parent=r, coll=coll, ink=ink)
    core.box(n + "_tape", (0.08, 0.51, 0.005), M(n + "_t", "#E0C097"), (0, 0, 0.401), parent=r, coll=coll)
    if label:
        core.text_obj(n + "_label", label, 0.09, M(n + "_lt", "#1A1A1A"), (0, -0.252, 0.2), parent=r, coll=coll, extrude=0.002)


def p_trash_can(r, n, c, coll, ink, label):
    core.cyl(n + "_body", 0.25, 0.22, 0.8, M(n + "_m", c), parent=r, coll=coll, ink=ink, base_at_origin=True, seg=10)
    core.cyl(n + "_lid", 0.27, 0.27, 0.05, M(n + "_l", _darker(c)), (0, 0, 0.82), parent=r, coll=coll, ink=ink, seg=10)


def p_cake(r, n, c, coll, ink, label):
    core.cyl(n + "_plate", 0.2, 0.2, 0.015, M(n + "_p", "#FFFFFF"), parent=r, coll=coll, base_at_origin=True, seg=16)
    core.cyl(n + "_body", 0.15, 0.15, 0.12, M(n + "_m", c), parent=r, coll=coll, ink=0.004, base_at_origin=True, seg=14)
    core.ball(n + "_cherry", (0.025,) * 3, M(n + "_ch", "#C1121F"), (0, 0, 0.15), parent=r, coll=coll, detail=1)
    core.cyl(n + "_candle", 0.008, 0.008, 0.08, M(n + "_c", "#FFFFFF"), (0.05, 0, 0.16), parent=r, coll=coll)
    core.ball(n + "_flame", (0.012, 0.012, 0.022), core.emit_mat(n + "_fl", "#FFB703", 4), (0.05, 0, 0.215), parent=r, coll=coll, detail=1)


def p_sign(r, n, c, coll, ink, label):
    core.cyl(n + "_pole", 0.03, 0.03, 1.6, M(n + "_pole", "#555555"), parent=r, coll=coll, base_at_origin=True)
    core.box(n + "_board", (0.9, 0.04, 0.5), M(n + "_m", c, emission=0.1), (0, 0, 1.65), parent=r, coll=coll, ink=ink)
    if label:
        core.text_obj(n + "_label", label, 0.14, M(n + "_lt", "#111111"), (0, -0.03, 1.65), parent=r, coll=coll, extrude=0.004)


def p_painting(r, n, c, coll, ink, label):
    core.box(n + "_frame", (0.8, 0.04, 0.6), M(n + "_f", "#6B4226"), (0, 0, 1.5), parent=r, coll=coll, ink=ink)
    core.box(n + "_canvas", (0.68, 0.01, 0.48), M(n + "_m", c, emission=0.1), (0, -0.022, 1.5), parent=r, coll=coll)
    core.ball(n + "_sun", (0.08, 0.01, 0.08), M(n + "_s", "#FFD166"), (0.15, -0.03, 1.6), parent=r, coll=coll, detail=1)


def p_pigeon(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.ball(n + "_body", (0.09, 0.14, 0.09), m, (0, 0, 0.12), parent=r, coll=coll, ink=0.004, detail=1)
    core.ball(n + "_chest", (0.07, 0.05, 0.07), M(n + "_chest", "#7FB7A4"), (0, -0.08, 0.15), parent=r, coll=coll, detail=1)
    core.ball(n + "_head", (0.055,) * 3, m, (0, -0.11, 0.23), parent=r, coll=coll, ink=0.004, detail=1)
    core.cyl(n + "_beak", 0.015, 0.0, 0.05, M(n + "_beak", "#F4A261"), (0, -0.17, 0.23), (D(90), 0, 0), parent=r, coll=coll, seg=4)
    for s in (1, -1):
        core.ball(n + f"_eye{s}", (0.018,) * 3, M(n + "_eye", "#FF7F11", emission=0.3), (s * 0.035, -0.145, 0.25), parent=r, coll=coll, detail=1)
        core.ball(n + f"_pupil{s}", (0.009,) * 3, M(n + "_pup", "#000000"), (s * 0.04, -0.158, 0.252), parent=r, coll=coll, detail=1)
        core.ball(n + f"_wing{s}", (0.03, 0.12, 0.06), M(n + "_w", _darker(c, 0.8)), (s * 0.085, 0.02, 0.13), parent=r, coll=coll, detail=1)
        core.cyl(n + f"_leg{s}", 0.008, 0.008, 0.07, M(n + "_beak", "#F4A261"), (s * 0.03, 0, 0.035), parent=r, coll=coll, seg=4)
    core.box(n + "_tail", (0.08, 0.1, 0.02), M(n + "_w", _darker(c, 0.8)), (0, 0.16, 0.1), (D(-20), 0, 0), parent=r, coll=coll)


def p_cat(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    core.ball(n + "_body", (0.13, 0.25, 0.13), m, (0, 0, 0.2), parent=r, coll=coll, ink=0.005, detail=1)
    core.ball(n + "_head", (0.11,) * 3, m, (0, -0.25, 0.32), parent=r, coll=coll, ink=0.005, detail=1)
    for s in (1, -1):
        core.cyl(n + f"_ear{s}", 0.04, 0.0, 0.08, m, (s * 0.06, -0.25, 0.44), parent=r, coll=coll, seg=4)
        core.ball(n + f"_eye{s}", (0.025, 0.01, 0.03), M(n + "_eye", "#B5E61D", emission=0.4), (s * 0.045, -0.35, 0.34), parent=r, coll=coll, detail=1)
        for sy in (1, -1):
            core.cyl(n + f"_leg{s}{sy}", 0.03, 0.03, 0.12, m, (s * 0.07, sy * 0.15, 0.06), parent=r, coll=coll, seg=6)
    core.cyl(n + "_tail", 0.025, 0.015, 0.35, m, (0, 0.33, 0.35), (D(-30), 0, 0), parent=r, coll=coll, seg=6)


def p_frying_pan(r, n, c, coll, ink, label):
    m = M(n + "_m", c, rough=0.4, metallic=0.4)
    core.cyl(n + "_pan", 0.14, 0.12, 0.04, m, parent=r, coll=coll, ink=0.004, base_at_origin=True, seg=14)
    core.box(n + "_handle", (0.03, 0.22, 0.02), M(n + "_h", "#1A1A1A"), (0, 0.24, 0.03), parent=r, coll=coll)


def p_fire_extinguisher(r, n, c, coll, ink, label):
    core.cyl(n + "_body", 0.08, 0.08, 0.5, M(n + "_m", c), parent=r, coll=coll, ink=ink * 0.5, base_at_origin=True, seg=10)
    core.ball(n + "_top", (0.08, 0.08, 0.05), M(n + "_m", c), (0, 0, 0.5), parent=r, coll=coll, detail=1)
    core.box(n + "_nozzle", (0.03, 0.15, 0.03), M(n + "_n", "#1A1A1A"), (0, -0.07, 0.56), parent=r, coll=coll)


def p_shopping_cart(r, n, c, coll, ink, label):
    m = M(n + "_m", c, metallic=0.6, rough=0.3)
    core.box(n + "_basket", (0.55, 0.85, 0.45), m, (0, 0, 0.75), parent=r, coll=coll, ink=ink)
    core.box(n + "_handle", (0.6, 0.04, 0.04), M(n + "_h", "#D62828"), (0, 0.48, 1.05), parent=r, coll=coll)
    for sx in (1, -1):
        for sy in (1, -1):
            core.cyl(n + f"_wheel{sx}{sy}", 0.05, 0.05, 0.04, M(n + "_w", "#1A1A1A"), (sx * 0.22, sy * 0.35, 0.05), (0, D(90), 0), parent=r, coll=coll, seg=8)


def p_shelf(r, n, c, coll, ink, label):
    m = M(n + "_m", c)
    for s in (1, -1):
        core.box(n + f"_side{s}", (0.04, 0.4, 1.8), m, (s * 0.6, 0, 0.9), parent=r, coll=coll, ink=ink)
    for i in range(5):
        core.box(n + f"_board{i}", (1.2, 0.4, 0.03), m, (0, 0, 0.05 + i * 0.42), parent=r, coll=coll, ink=ink * 0.5)
        for j in range(4):
            col = ["#E63946", "#F1FAEE", "#A8DADC", "#457B9D", "#FFB703"][(i + j) % 5]
            core.box(n + f"_item{i}{j}", (0.18, 0.2, 0.25), M(n + f"_it{col}", col), (-0.42 + j * 0.28, -0.05, 0.19 + i * 0.42), parent=r, coll=coll)


def p_rug(r, n, c, coll, ink, label):
    core.box(n + "_m", (2.2, 1.5, 0.01), M(n + "_m", c), (0, 0, 0.005), parent=r, coll=coll)
    core.box(n + "_b", (1.8, 1.1, 0.012), M(n + "_b", _darker(c, 0.75)), (0, 0, 0.006), parent=r, coll=coll)


def p_streetlight(r, n, c, coll, ink, label):
    core.cyl(n + "_pole", 0.06, 0.05, 4.0, M(n + "_m", c), parent=r, coll=coll, ink=ink, base_at_origin=True)
    core.box(n + "_arm", (0.08, 0.8, 0.08), M(n + "_m", c), (0, -0.4, 4.0), parent=r, coll=coll)
    core.ball(n + "_bulb", (0.18, 0.18, 0.1), core.emit_mat(n + "_bulb", "#FFF1C1", 3), (0, -0.8, 3.92), parent=r, coll=coll, detail=1)


def p_building(r, n, c, coll, ink, label):
    core.box(n + "_body", (6.0, 5.0, 9.0), M(n + "_m", c), (0, 0, 4.5), parent=r, coll=coll, ink=ink * 2)
    core.box(n + "_roof", (6.3, 5.3, 0.3), M(n + "_r", _darker(c, 0.6)), (0, 0, 9.1), parent=r, coll=coll)
    win = core.emit_mat(n + "_win", "#FFE8A3", 0.9)
    for fl in range(4):
        for i in range(4):
            core.box(n + f"_w{fl}{i}", (0.8, 0.05, 1.0), win, (-2.1 + i * 1.4, -2.52, 1.6 + fl * 2.0), parent=r, coll=coll)
    core.box(n + "_door", (1.2, 0.05, 2.2), M(n + "_d", "#5C3D2E"), (0, -2.52, 1.1), parent=r, coll=coll)
