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


def build(ptype, name, color=None, scale=1.0, label=None, coll=None, ink=0.008, parts=None, external=None):
    """external : {"path": chemin absolu, "target_height": m, "rot_offset_deg": deg} pour un modèle importé."""
    col = color or DEFAULT_COLORS.get(ptype, "#AAAAAA")
    root = core.empty(name, (0, 0, 0), None, coll)
    if ptype == "composite":
        composite(root, name, parts or [], col, coll, ink)
    elif external and external.get("path"):
        import_external(root, name, external, coll, label)
    else:
        fn = globals().get("p_" + ptype)
        if fn is None:
            raise ValueError(f"type d'accessoire inconnu : {ptype}")
        fn(root, name, col, coll, ink, label)
    root.scale = (scale, scale, scale)
    root["prop_type"] = ptype
    return root


def composite(root, n, parts, default_col, coll, ink):
    """Objet improvisé par l'agent décorateur : assemblage déterministe de formes simples."""
    for i, pt in enumerate(parts):
        sx, sy, sz = pt["size"]
        col = pt.get("color", default_col)
        mat = core.emit_mat(f"{n}_g{i}", col, 2.0) if pt.get("glow") else M(f"comp_{col}", col, emission=0.25)
        rot = tuple(D(a) for a in pt.get("rot_deg", (0, 0, 0)))
        loc = tuple(pt["pos"])
        k = ink if pt.get("ink", True) else 0.0
        sh = pt["shape"]
        nm = f"{n}_p{i}"
        if sh == "box":
            core.box(nm, (sx, sy, sz), mat, loc, rot, parent=root, coll=coll, ink=k, bevel=min(sx, sy, sz) * 0.08)
        elif sh == "ball":
            core.ball(nm, (sx / 2, sy / 2, sz / 2), mat, loc, rot, parent=root, coll=coll, ink=k, detail=2)
        elif sh in ("cyl", "cone"):
            r1 = sx / 2
            r2 = 0.0 if sh == "cone" else (sy / 2 if sy > 0 else r1)
            core.cyl(nm, r1, r2, sz, mat, loc, rot, parent=root, coll=coll, ink=k, seg=12)
        elif sh == "torus":
            core.torus(nm, sx / 2, max(0.005, sz / 2), mat, loc, rot, parent=root, coll=coll)
        elif sh == "text":
            core.text_obj(nm, pt.get("text", "?"), sx, mat, loc, (D(90) + rot[0], rot[1], rot[2]), parent=root, coll=coll, extrude=max(0.002, sx * 0.05))


def import_external(root, n, ext, coll, label=None):
    """Importe un modèle .glb/.gltf/.obj, le pose au sol, centré, à la hauteur demandée, face -Y.
    Les objets importés deviennent enfants de `root` ; un repli visible est créé si l'import échoue."""
    import os
    import bpy
    path = ext["path"]
    before = set(bpy.data.objects)
    ok = False
    try:
        if path.lower().endswith((".glb", ".gltf")):
            import addon_utils
            addon_utils.enable("io_scene_gltf2", default_set=True)
            bpy.ops.import_scene.gltf(filepath=path)
        elif path.lower().endswith(".obj"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            raise ValueError(f"format non supporté : {os.path.splitext(path)[1]}")
        ok = True
    except Exception as e:   # noqa: BLE001  — repli visible plutôt qu'un plan vide
        print("STUDIO_EXTERNAL_IMPORT_FAILED", path, repr(e))
    new = [o for o in bpy.data.objects if o not in before]
    if not ok or not new:
        p_custom(root, n, None, coll, 0.008, label)
        root["external_failed"] = True
        return
    target = coll or bpy.context.scene.collection
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        target.objects.link(o)
    tops = [o for o in new if o.parent is None or o.parent not in new]
    holder = core.empty(n + "_ext", (0, 0, 0), root, coll)
    for o in tops:
        mw = o.matrix_world.copy()
        o.parent = holder
        o.matrix_world = mw
    bpy.context.view_layer.update()
    lo, hi = core.world_bbox(holder)
    h = max(hi.z - lo.z, 1e-4)
    k = float(ext.get("target_height") or h) / h
    holder.scale = (k, k, k)
    holder.rotation_euler = (0, 0, D(ext.get("rot_offset_deg", 0.0)))
    bpy.context.view_layer.update()
    lo, hi = core.world_bbox(holder)
    holder.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
    root["external_faces"] = sum(len(o.data.polygons) for o in new if o.type == 'MESH')


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


# ====================================================================== v0.4 : restaurant, classe, plage, animaux, objets
DEFAULT_COLORS.update({
    "restaurant_table": "#FFFFFF", "wine_glass": "#CDEFFF", "plate_food": "#F8F9FA", "menu_board": "#2B2D42", "cooking_pot": "#9AA5B1",
    "school_desk": "#C68B59", "blackboard": "#2F5D50", "backpack": "#3A86FF", "globe": "#4895EF", "parasol": "#E63946",
    "beach_towel": "#F72585", "sandcastle": "#E9C46A", "palm_tree": "#2D6A4F", "beach_ball": "#FFBE0B", "surfboard": "#FB5607",
    "cooler": "#4CC9F0", "lifeguard_tower": "#E63946", "dog": "#C68B59", "chicken": "#FFFFFF", "duck": "#FFD60A", "rat": "#8D99AE",
    "fish": "#F77F00", "cow": "#FFFFFF", "guitar": "#B5651D", "pizza": "#F4A261", "burger": "#C68B59", "trophy": "#F4C430",
    "money_stack": "#52B788", "skateboard": "#8338EC", "bucket": "#E63946", "custom": "#AAAAAA",
})
SURFACE_H.update({"restaurant_table": 0.76, "school_desk": 0.72, "cooler": 0.45, "lifeguard_tower": 1.6})


def p_restaurant_table(r, n, c, coll, ink, label):
    core.cyl(n + "_cloth", 0.55, 0.62, 0.32, M(n + "_cloth", c, emission=0.2), (0, 0, 0.62), parent=r, coll=coll, ink=ink, seg=16)
    core.cyl(n + "_top", 0.56, 0.56, 0.04, M(n + "_cloth", c, emission=0.2), (0, 0, 0.76), parent=r, coll=coll, seg=16)
    core.cyl(n + "_leg", 0.05, 0.05, 0.5, M(n + "_leg", "#3D3D3D"), (0, 0, 0.25), parent=r, coll=coll, seg=8)
    core.cyl(n + "_foot", 0.25, 0.25, 0.03, M(n + "_leg", "#3D3D3D"), (0, 0, 0.015), parent=r, coll=coll, seg=12)
    core.cyl(n + "_candle", 0.02, 0.02, 0.1, M(n + "_cdl", "#FFF8E7"), (0.15, 0.1, 0.83), parent=r, coll=coll, seg=8)
    core.ball(n + "_flame", (0.015, 0.015, 0.03), core.emit_mat(n + "_fl", "#FFB703", 4), (0.15, 0.1, 0.9), parent=r, coll=coll, detail=1)


def p_wine_glass(r, n, c, coll, ink, label):
    g = M(n + "_g", c, rough=0.1, emission=0.3)
    core.cyl(n + "_base", 0.035, 0.035, 0.008, g, (0, 0, 0.004), parent=r, coll=coll, seg=10)
    core.cyl(n + "_stem", 0.006, 0.006, 0.09, g, (0, 0, 0.05), parent=r, coll=coll, seg=6)
    core.cyl(n + "_bowl", 0.025, 0.045, 0.08, g, (0, 0, 0.13), parent=r, coll=coll, seg=12, ink=0.003)
    core.cyl(n + "_wine", 0.03, 0.038, 0.035, M(n + "_wine", "#7B002C", emission=0.3), (0, 0, 0.115), parent=r, coll=coll, seg=12)


def p_plate_food(r, n, c, coll, ink, label):
    core.cyl(n + "_plate", 0.14, 0.11, 0.02, M(n + "_m", c, emission=0.2), (0, 0, 0.01), parent=r, coll=coll, seg=16, ink=0.003)
    core.ball(n + "_food", (0.08, 0.07, 0.04), M(n + "_food", "#BC6C25", emission=0.2), (0, 0, 0.04), parent=r, coll=coll, detail=1)
    for k, col in enumerate(("#52B788", "#E63946", "#FFB703")):
        core.ball(n + f"_side{k}", (0.025,) * 3, M(n + f"_s{k}", col, emission=0.2), (0.07 * math.cos(k * 2), 0.07 * math.sin(k * 2), 0.035), parent=r, coll=coll, detail=1)


def p_menu_board(r, n, c, coll, ink, label):
    wood = M(n + "_w", "#8D5A3B")
    for s in (1, -1):
        core.box(n + f"_leg{s}", (0.05, 0.05, 1.2), wood, (s * 0.28, 0.18 * s * 0 + 0.12, 0.6), (D(-12), 0, 0), parent=r, coll=coll)
    core.box(n + "_board", (0.6, 0.04, 0.8), M(n + "_m", c, emission=0.15), (0, 0, 0.75), (D(-12), 0, 0), parent=r, coll=coll, ink=ink)
    core.text_obj(n + "_txt", label or "MENU", 0.11, M(n + "_chalk", "#F8F9FA", emission=0.6), (0, -0.04, 0.98), (D(78), 0, 0), parent=r, coll=coll, extrude=0.002)
    for k in range(3):
        core.box(n + f"_line{k}", (0.4, 0.01, 0.02), M(n + "_chalk", "#F8F9FA", emission=0.6), (0, -0.03, 0.78 - k * 0.12), (D(-12), 0, 0), parent=r, coll=coll)


def p_cooking_pot(r, n, c, coll, ink, label):
    m = M(n + "_m", c, rough=0.35, metallic=0.5)
    core.cyl(n + "_body", 0.17, 0.17, 0.2, m, parent=r, coll=coll, ink=ink * 0.5, base_at_origin=True, seg=14)
    core.cyl(n + "_soup", 0.155, 0.155, 0.02, M(n + "_soup", "#E76F51", emission=0.3), (0, 0, 0.18), parent=r, coll=coll, seg=14)
    for s in (1, -1):
        core.torus(n + f"_handle{s}", 0.04, 0.01, m, (s * 0.19, 0, 0.16), (0, D(90), 0), parent=r, coll=coll)


def p_school_desk(r, n, c, coll, ink, label):
    m, mt = core.pattern_mat(n + "_top", "wood", c, None, scale=3, emission=0.15), M(n + "_metal", "#495057")
    core.box(n + "_top", (0.7, 0.5, 0.04), m, (0, 0, 0.72), parent=r, coll=coll, ink=ink)
    core.box(n + "_shelf", (0.6, 0.4, 0.02), mt, (0, 0, 0.58), parent=r, coll=coll)
    for sx in (1, -1):
        for sy in (1, -1):
            core.box(n + f"_leg{sx}{sy}", (0.035, 0.035, 0.72), mt, (sx * 0.31, sy * 0.21, 0.36), parent=r, coll=coll)
    core.box(n + "_book", (0.22, 0.16, 0.03), M(n + "_book", "#E63946", emission=0.2), (0.12, -0.05, 0.755), (0, 0, 0.3), parent=r, coll=coll)


def p_blackboard(r, n, c, coll, ink, label):
    core.box(n + "_frame", (2.6, 0.06, 1.25), M(n + "_f", "#8D5A3B"), (0, 0, 1.55), parent=r, coll=coll, ink=ink)
    core.box(n + "_board", (2.45, 0.07, 1.1), M(n + "_m", c, emission=0.12), (0, -0.005, 1.55), parent=r, coll=coll)
    core.box(n + "_tray", (2.45, 0.12, 0.04), M(n + "_f", "#8D5A3B"), (0, -0.07, 0.95), parent=r, coll=coll)
    chalk = M(n + "_chalk", "#F8F9FA", emission=0.7)
    core.text_obj(n + "_txt", label or "2 + 2 = 5", 0.2, chalk, (0, -0.045, 1.75), parent=r, coll=coll, extrude=0.003)
    for k in range(2):
        core.box(n + f"_l{k}", (1.4 - k * 0.4, 0.01, 0.025), chalk, (-0.2, -0.045, 1.4 - k * 0.16), parent=r, coll=coll)


def p_backpack(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.2)
    core.box(n + "_body", (0.32, 0.18, 0.42), m, (0, 0, 0.21), parent=r, coll=coll, ink=ink, bevel=0.06)
    core.box(n + "_pocket", (0.24, 0.06, 0.18), M(n + "_p", _darker(c, 0.75), emission=0.2), (0, -0.11, 0.14), parent=r, coll=coll, bevel=0.03)
    core.torus(n + "_strap", 0.08, 0.015, M(n + "_p", _darker(c, 0.75)), (0, 0.02, 0.43), (0, D(90), 0), parent=r, coll=coll)


def p_globe(r, n, c, coll, ink, label):
    core.cyl(n + "_base", 0.12, 0.12, 0.03, M(n + "_b", "#5C3D2E"), parent=r, coll=coll, base_at_origin=True)
    core.cyl(n + "_stem", 0.015, 0.015, 0.12, M(n + "_b", "#5C3D2E"), (0, 0, 0.09), parent=r, coll=coll)
    g = core.empty(n + "_g", (0, 0, 0.3), r, coll)
    g.rotation_euler = (D(23), 0, 0)
    core.ball(n + "_sea", (0.16,) * 3, M(n + "_m", c, emission=0.2), (0, 0, 0), parent=g, coll=coll, detail=2, ink=0.004)
    for k, (x, y, z) in enumerate(((0.08, -0.1, 0.06), (-0.1, -0.06, -0.02), (0.02, 0.1, 0.1))):
        core.ball(n + f"_land{k}", (0.07, 0.04, 0.05), M(n + "_land", "#52B788", emission=0.2), (x, y, z), parent=g, coll=coll, detail=1)


def p_parasol(r, n, c, coll, ink, label):
    core.cyl(n + "_pole", 0.025, 0.025, 2.1, M(n + "_pole", "#F8F9FA"), parent=r, coll=coll, base_at_origin=True)
    for k in range(8):
        col = c if k % 2 == 0 else "#F8F9FA"
        a = k * math.pi / 4
        core.cyl(n + f"_seg{k}", 1.0, 0.0, 0.45, M(n + f"_s{col}", col, emission=0.25), (0, 0, 2.05), (0, 0, a), parent=r, coll=coll, seg=8, ink=ink)
        break
    core.cyl(n + "_canopy", 1.05, 0.02, 0.45, core.pattern_mat(n + "_stripes", "stripes", c, "#F8F9FA", scale=3, plane='xy', emission=0.25),
             (0, 0, 2.05), parent=r, coll=coll, seg=16, ink=ink)


def p_beach_towel(r, n, c, coll, ink, label):
    core.box(n + "_m", (0.8, 1.7, 0.01), core.pattern_mat(n + "_st", "stripes", c, "#FFFFFF", scale=4, plane='xy', emission=0.2), (0, 0, 0.005), parent=r, coll=coll)


def p_sandcastle(r, n, c, coll, ink, label):
    s = core.pattern_mat(n + "_sand", "noise", c, scale=6, emission=0.15)
    core.box(n + "_base", (0.6, 0.6, 0.2), s, (0, 0, 0.1), parent=r, coll=coll, ink=ink * 0.6)
    for sx in (1, -1):
        for sy in (1, -1):
            core.cyl(n + f"_tow{sx}{sy}", 0.09, 0.08, 0.35, s, (sx * 0.27, sy * 0.27, 0.17), parent=r, coll=coll, seg=8, ink=ink * 0.5)
            core.cyl(n + f"_roof{sx}{sy}", 0.1, 0.0, 0.12, s, (sx * 0.27, sy * 0.27, 0.4), parent=r, coll=coll, seg=8)
    core.cyl(n + "_keep", 0.13, 0.12, 0.45, s, (0, 0, 0.42), parent=r, coll=coll, seg=8, ink=ink * 0.5)
    core.box(n + "_flag", (0.12, 0.01, 0.07), M(n + "_flag", "#E63946", emission=0.3), (0.06, 0, 0.78), parent=r, coll=coll)


def p_palm_tree(r, n, c, coll, ink, label):
    trunk = core.pattern_mat(n + "_trunk", "bricks", "#A47148", "#8B5E3C", scale=2.5, plane='xz', emission=0.15)
    for k in range(6):
        core.cyl(n + f"_t{k}", 0.13 - k * 0.012, 0.12 - k * 0.012, 0.6, trunk, (0.05 * k * k * 0.1, 0, 0.3 + k * 0.58), (0, D(3 * k), 0), parent=r, coll=coll, seg=7, ink=ink * 0.6)
    top = (0.12, 0, 3.6)
    for k in range(7):
        a = 2 * math.pi * k / 7
        core.ball(n + f"_leaf{k}", (0.85, 0.16, 0.05), M(n + "_m", c, emission=0.2), (top[0] + 0.7 * math.cos(a), 0.7 * math.sin(a), top[2] - 0.15), (0, D(20), a), parent=r, coll=coll, detail=1, ink=ink * 0.6)
    for k in range(3):
        core.ball(n + f"_coco{k}", (0.09,) * 3, M(n + "_coco", "#6B4226"), (top[0] + 0.1 * math.cos(k * 2), 0.1 * math.sin(k * 2), top[2] - 0.2), parent=r, coll=coll, detail=1)


def p_beach_ball(r, n, c, coll, ink, label):
    b = core.empty(n + "_b", (0, 0, 0.2), r, coll)
    for k, col in enumerate((c, "#FFFFFF", "#3A86FF", "#FFFFFF", "#E63946", "#FFFFFF")):
        o = core.uvball(n + f"_p{k}", (0.2, 0.2, 0.2), M(n + f"_{col}", col, emission=0.3), (0, 0, 0), (0, 0, k * math.pi / 3), parent=b, coll=coll, seg=12, rings=8, zmin=-1.0)
        break
    core.ball(n + "_ball", (0.2,) * 3, core.pattern_mat(n + "_st", "stripes", c, "#FFFFFF", scale=4, plane='xz', emission=0.3), (0, 0, 0), parent=b, coll=coll, detail=3, ink=0.005, smooth=True)


def p_surfboard(r, n, c, coll, ink, label):
    core.ball(n + "_board", (0.28, 0.05, 1.0), M(n + "_m", c, emission=0.25), (0, 0, 1.0), (D(-8), 0, 0), parent=r, coll=coll, detail=2, ink=ink, smooth=True)
    core.box(n + "_stripe", (0.06, 0.06, 1.6), M(n + "_s", "#FFFFFF", emission=0.3), (0, -0.01, 1.0), (D(-8), 0, 0), parent=r, coll=coll)


def p_cooler(r, n, c, coll, ink, label):
    core.box(n + "_body", (0.55, 0.38, 0.38), M(n + "_m", c, emission=0.2), (0, 0, 0.19), parent=r, coll=coll, ink=ink, bevel=0.03)
    core.box(n + "_lid", (0.57, 0.4, 0.07), M(n + "_lid", "#FFFFFF", emission=0.2), (0, 0, 0.415), parent=r, coll=coll, ink=ink * 0.6, bevel=0.02)


def p_lifeguard_tower(r, n, c, coll, ink, label):
    wood = core.pattern_mat(n + "_w", "wood", "#F2E8CF", "#D8C3A5", scale=2, emission=0.15)
    for sx in (1, -1):
        for sy in (1, -1):
            core.box(n + f"_leg{sx}{sy}", (0.08, 0.08, 1.6), wood, (sx * 0.5, sy * 0.5, 0.8), parent=r, coll=coll, ink=ink * 0.6)
    core.box(n + "_floor", (1.2, 1.2, 0.08), wood, (0, 0, 1.6), parent=r, coll=coll, ink=ink)
    core.box(n + "_cabin", (1.1, 1.1, 0.9), M(n + "_m", c, emission=0.25), (0, 0.1, 2.1), parent=r, coll=coll, ink=ink)
    core.box(n + "_roof", (1.4, 1.4, 0.08), M(n + "_roof", "#F8F9FA"), (0, 0.1, 2.6), parent=r, coll=coll, ink=ink)
    core.box(n + "_win", (0.8, 0.02, 0.4), core.gradient_emit_mat(n + "_gl", "#8ECAE6", "#CDEFFF", 0.4, 0.8), (0, -0.46, 2.2), parent=r, coll=coll)
    core.text_obj(n + "_txt", label or "SURVEILLANCE", 0.09, M(n + "_t", "#FFFFFF", emission=0.6), (0, -0.46, 1.8), parent=r, coll=coll, extrude=0.003)


def _animal_eyes(r, n, x, y, z, sz, coll):
    for s in (1, -1):
        core.ball(n + f"_eye{s}", (sz,) * 3, M("animal_eye_w", "#FFFFFF", emission=0.3), (x + s * sz * 1.4, y, z), parent=r, coll=coll, detail=1)
        core.ball(n + f"_pup{s}", (sz * 0.55,) * 3, M("animal_pupil", "#111111"), (x + s * sz * 1.4, y - sz * 0.6, z), parent=r, coll=coll, detail=1)


def p_dog(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.25)
    core.ball(n + "_body", (0.16, 0.3, 0.15), m, (0, 0.05, 0.3), parent=r, coll=coll, ink=0.006, detail=2)
    core.ball(n + "_head", (0.14, 0.14, 0.13), m, (0, -0.28, 0.48), parent=r, coll=coll, ink=0.006, detail=2)
    core.ball(n + "_snout", (0.07, 0.08, 0.06), M(n + "_sn", _darker(c, 1.15), emission=0.25), (0, -0.4, 0.44), parent=r, coll=coll, detail=1)
    core.ball(n + "_nose", (0.03,) * 3, M(n + "_nose", "#111111"), (0, -0.47, 0.47), parent=r, coll=coll, detail=1)
    for s in (1, -1):
        core.ball(n + f"_ear{s}", (0.04, 0.03, 0.1), M(n + "_ear", _darker(c, 0.7), emission=0.2), (s * 0.12, -0.26, 0.5), (0, s * D(-20), 0), parent=r, coll=coll, detail=1)
        for sy in (1, -1):
            core.cyl(n + f"_leg{s}{sy}", 0.045, 0.04, 0.22, m, (s * 0.09, 0.05 + sy * 0.18, 0.11), parent=r, coll=coll, seg=6, ink=0.004)
    core.cyl(n + "_tail", 0.03, 0.015, 0.22, m, (0, 0.38, 0.42), (D(-40), 0, 0), parent=r, coll=coll, seg=6)
    core.box(n + "_collar", (0.17, 0.17, 0.03), M(n + "_collar", "#E63946", emission=0.3), (0, -0.2, 0.42), parent=r, coll=coll)
    _animal_eyes(r, n, 0, -0.39, 0.53, 0.025, coll)


def p_chicken(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.3)
    core.ball(n + "_body", (0.13, 0.17, 0.13), m, (0, 0.02, 0.2), parent=r, coll=coll, ink=0.005, detail=2)
    core.ball(n + "_head", (0.07,) * 3, m, (0, -0.1, 0.36), parent=r, coll=coll, ink=0.004, detail=1)
    core.cyl(n + "_beak", 0.025, 0.0, 0.06, M(n + "_beak", "#FFB703"), (0, -0.18, 0.36), (D(90), 0, 0), parent=r, coll=coll, seg=4)
    core.box(n + "_comb", (0.02, 0.07, 0.05), M(n + "_comb", "#E63946", emission=0.3), (0, -0.1, 0.44), parent=r, coll=coll)
    core.ball(n + "_wattle", (0.02, 0.02, 0.03), M(n + "_comb", "#E63946", emission=0.3), (0, -0.15, 0.31), parent=r, coll=coll, detail=1)
    for s in (1, -1):
        core.cyl(n + f"_leg{s}", 0.01, 0.01, 0.1, M(n + "_beak", "#FFB703"), (s * 0.04, 0.02, 0.05), parent=r, coll=coll, seg=4)
    core.ball(n + "_tail", (0.06, 0.05, 0.09), m, (0, 0.17, 0.27), (D(-30), 0, 0), parent=r, coll=coll, detail=1)
    _animal_eyes(r, n, 0, -0.15, 0.39, 0.015, coll)


def p_duck(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.3)
    core.ball(n + "_body", (0.13, 0.18, 0.1), m, (0, 0.02, 0.12), parent=r, coll=coll, ink=0.005, detail=2)
    core.ball(n + "_head", (0.07,) * 3, m, (0, -0.12, 0.27), parent=r, coll=coll, ink=0.004, detail=1)
    core.ball(n + "_beak", (0.045, 0.06, 0.018), M(n + "_beak", "#FB8500", emission=0.3), (0, -0.2, 0.25), parent=r, coll=coll, detail=1)
    _animal_eyes(r, n, 0, -0.17, 0.3, 0.014, coll)


def p_rat(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.2)
    core.ball(n + "_body", (0.06, 0.11, 0.055), m, (0, 0, 0.055), parent=r, coll=coll, ink=0.004, detail=2)
    core.ball(n + "_head", (0.04, 0.06, 0.04), m, (0, -0.12, 0.07), parent=r, coll=coll, detail=1)
    core.ball(n + "_nose", (0.012,) * 3, M(n + "_nose", "#FF8FA3"), (0, -0.18, 0.07), parent=r, coll=coll, detail=1)
    for s in (1, -1):
        core.ball(n + f"_ear{s}", (0.025, 0.008, 0.025), M(n + "_nose", "#FF8FA3"), (s * 0.035, -0.1, 0.11), parent=r, coll=coll, detail=1)
    core.cyl(n + "_tail", 0.006, 0.003, 0.2, M(n + "_nose", "#FF8FA3"), (0, 0.18, 0.04), (D(-80), 0, 0), parent=r, coll=coll, seg=4)
    _animal_eyes(r, n, 0, -0.16, 0.09, 0.009, coll)


def p_fish(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.3)
    core.ball(n + "_body", (0.05, 0.16, 0.08), m, (0, 0, 0.08), parent=r, coll=coll, ink=0.004, detail=2)
    core.cyl(n + "_tail", 0.07, 0.0, 0.09, m, (0, 0.19, 0.08), (D(-90), 0, 0), parent=r, coll=coll, seg=4)
    _animal_eyes(r, n, 0, -0.12, 0.1, 0.012, coll)


def p_cow(r, n, c, coll, ink, label):
    m = M(n + "_m", c, emission=0.25)
    spot = M(n + "_spot", "#1A1A1A")
    core.ball(n + "_body", (0.38, 0.7, 0.38), m, (0, 0.05, 0.95), parent=r, coll=coll, ink=0.01, detail=2)
    for k, (x, y, z) in enumerate(((0.3, 0.2, 1.05), (-0.32, -0.15, 0.95), (0.1, 0.45, 1.2))):
        core.ball(n + f"_spot{k}", (0.12, 0.18, 0.14), spot, (x, y, z), parent=r, coll=coll, detail=1)
    core.ball(n + "_head", (0.24, 0.3, 0.24), m, (0, -0.7, 1.15), parent=r, coll=coll, ink=0.008, detail=2)
    core.ball(n + "_muzzle", (0.2, 0.12, 0.13), M(n + "_muz", "#FFB5C2", emission=0.25), (0, -0.95, 1.05), parent=r, coll=coll, detail=1)
    for s in (1, -1):
        core.cyl(n + f"_horn{s}", 0.04, 0.0, 0.18, M(n + "_horn", "#F2E8CF"), (s * 0.18, -0.7, 1.42), (0, s * D(-30), 0), parent=r, coll=coll, seg=5)
        for sy in (1, -1):
            core.cyl(n + f"_leg{s}{sy}", 0.09, 0.08, 0.65, m, (s * 0.22, 0.05 + sy * 0.45, 0.33), parent=r, coll=coll, seg=6, ink=0.006)
    _animal_eyes(r, n, 0, -0.95, 1.25, 0.035, coll)


def p_guitar(r, n, c, coll, ink, label):
    m = core.pattern_mat(n + "_w", "wood", c, None, scale=5, emission=0.2)
    core.ball(n + "_body1", (0.2, 0.06, 0.18), m, (0, 0, 0.2), parent=r, coll=coll, ink=0.004, detail=2)
    core.ball(n + "_body2", (0.15, 0.06, 0.13), m, (0, 0, 0.42), parent=r, coll=coll, ink=0.004, detail=2)
    core.cyl(n + "_hole", 0.05, 0.05, 0.01, M(n + "_hole", "#1A1A1A"), (0, -0.06, 0.3), (D(90), 0, 0), parent=r, coll=coll, seg=12)
    core.box(n + "_neck", (0.05, 0.03, 0.5), M(n + "_neck", "#3D2B1F"), (0, 0, 0.78), parent=r, coll=coll)
    core.box(n + "_head", (0.08, 0.035, 0.12), M(n + "_neck", "#3D2B1F"), (0, 0, 1.08), parent=r, coll=coll)


def p_pizza(r, n, c, coll, ink, label):
    core.cyl(n + "_crust", 0.18, 0.18, 0.025, M(n + "_m", c, emission=0.25), parent=r, coll=coll, base_at_origin=True, seg=16, ink=0.003)
    core.cyl(n + "_sauce", 0.155, 0.155, 0.01, M(n + "_sauce", "#D62828", emission=0.25), (0, 0, 0.028), parent=r, coll=coll, seg=16)
    core.cyl(n + "_cheese", 0.14, 0.14, 0.008, M(n + "_cheese", "#FFD166", emission=0.3), (0, 0, 0.034), parent=r, coll=coll, seg=16)
    for k in range(6):
        a = k * math.pi / 3
        core.cyl(n + f"_pep{k}", 0.025, 0.025, 0.008, M(n + "_pep", "#9D0208", emission=0.2), (0.09 * math.cos(a), 0.09 * math.sin(a), 0.04), parent=r, coll=coll, seg=8)


def p_burger(r, n, c, coll, ink, label):
    bun = M(n + "_bun", "#E09F3E", emission=0.25)
    core.cyl(n + "_bottom", 0.1, 0.1, 0.035, bun, parent=r, coll=coll, base_at_origin=True, seg=14, ink=0.003)
    core.cyl(n + "_patty", 0.105, 0.105, 0.035, M(n + "_m", "#6F4518", emission=0.15), (0, 0, 0.052), parent=r, coll=coll, seg=14)
    core.cyl(n + "_cheese", 0.11, 0.11, 0.008, M(n + "_ch", "#FFD166", emission=0.3), (0, 0, 0.073), parent=r, coll=coll, seg=4)
    core.cyl(n + "_salad", 0.11, 0.11, 0.01, M(n + "_sal", "#80B918", emission=0.3), (0, 0, 0.082), parent=r, coll=coll, seg=10)
    core.uvball(n + "_top", (0.1, 0.1, 0.07), bun, (0, 0, 0.087), parent=r, coll=coll, seg=14, rings=8, zmin=0.0, ink=0.003)


def p_trophy(r, n, c, coll, ink, label):
    g = M(n + "_m", c, rough=0.25, metallic=0.7, emission=0.15)
    core.box(n + "_base", (0.16, 0.16, 0.06), M(n + "_base", "#3D2B1F"), (0, 0, 0.03), parent=r, coll=coll, ink=0.003)
    core.cyl(n + "_stem", 0.02, 0.03, 0.1, g, (0, 0, 0.11), parent=r, coll=coll, seg=8)
    core.cyl(n + "_cup", 0.1, 0.05, 0.15, g, (0, 0, 0.24), parent=r, coll=coll, seg=14, ink=0.004)
    for s in (1, -1):
        core.torus(n + f"_h{s}", 0.04, 0.008, g, (s * 0.11, 0, 0.26), (D(90), 0, 0), parent=r, coll=coll)


def p_money_stack(r, n, c, coll, ink, label):
    for k in range(5):
        core.box(n + f"_bill{k}", (0.16, 0.07, 0.025), M(n + "_m", c, emission=0.3), (0.0, 0.0, 0.013 + k * 0.026), (0, 0, k * 0.08), parent=r, coll=coll, ink=0.002)
    core.box(n + "_band", (0.03, 0.075, 0.13), M(n + "_band", "#F8F9FA", emission=0.3), (0, 0, 0.065), parent=r, coll=coll)


def p_skateboard(r, n, c, coll, ink, label):
    core.ball(n + "_deck", (0.11, 0.42, 0.012), M(n + "_m", c, emission=0.25), (0, 0, 0.09), parent=r, coll=coll, detail=2, ink=0.004)
    for sy in (1, -1):
        for sx in (1, -1):
            core.cyl(n + f"_wheel{sx}{sy}", 0.03, 0.03, 0.03, M(n + "_wh", "#FFD60A"), (sx * 0.08, sy * 0.28, 0.035), (0, D(90), 0), parent=r, coll=coll, seg=8)


def p_bucket(r, n, c, coll, ink, label):
    core.cyl(n + "_body", 0.14, 0.11, 0.25, M(n + "_m", c, emission=0.25), parent=r, coll=coll, base_at_origin=True, seg=12, ink=0.004)
    core.torus(n + "_handle", 0.13, 0.008, M(n + "_h", "#6C757D"), (0, 0, 0.26), (0, D(90), 0), parent=r, coll=coll)


def p_custom(r, n, c, coll, ink, label):
    # Repli visible si le modèle externe est absent : une caisse étiquetée (jamais un plan vide en silence)
    p_box(r, n, "#FF006E", coll, ink, label or "MODELE ?")
