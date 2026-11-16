"""Avatars de style Roblox R15 pour le moteur.

Même interface que characters.Character (articulations, visage, repères, tailles) : TOUT le reste du moteur
(animation, postures, visèmes, caméra, contrôles, objets tenus, écoute, figurants) fonctionne sans changement.

Deux sources :
1. PROCÉDURAL : avatar en blocs construit depuis la fiche (cast_bible.design) : tenue, motifs, inscription,
   coiffures en blocs, accessoires, chaussures. Personnages ORIGINAUX.
2. IMPORTÉ : avatar exporté depuis Roblox Studio (OBJ + textures) rangé dans assets/roblox/avatars/<id>/
   (design.roblox_avatar = "<id>") : pièces R15 (ou R6) reconnues par leur nom, squelette déduit des pièces,
   accessoires accrochés à la bonne pièce. Provenance et licence consignées dans avatar.json.

Visage : plat, façon jouet en blocs (yeux ovales, sourcils, bouches en décalcomanies) ; toutes les expressions
et les 6 visèmes du moteur.
"""
import json
import math
import random
import re
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

from . import core

D = math.radians
ROOT = Path(__file__).resolve().parents[2]
FACES = ROOT / "assets" / "roblox" / "faces"
LIBRARY = ROOT / "assets" / "roblox" / "avatars"

DEFAULT_DESIGN = {
    "body": {"height": 1.0, "girth": 1.0, "head_scale": 1.0, "leg_length": 1.0, "arm_length": 1.0, "belly": 0.0},
    "skin": "#F2B880",
    "hair": {"style": "short", "color": "#3B2416"},
    "eyes": {"size": 1.0, "spacing": 1.0, "iris": "#1A1A1A"},
    "brows": {"thickness": 1.0, "color": "#2A1B12"},
    "nose": {"shape": "round", "size": 1.0},
    "mouth": {"width": 1.0},
    "outfit": {"top": {"type": "tshirt", "color": "#3A7BD5"}, "bottom": {"type": "pants", "color": "#2D3142"}, "shoes": "#1E1E1E"},
    "accessories": [],
}
MOUTHS = ("line", "smile", "frown", "smirk", "open_o", "open_wide", "grin", "talk_a", "talk_b", "v_E", "v_U", "v_M", "v_F")
LONG_SLEEVES = ("shirt", "hoodie", "suit", "sweater", "jersey")
SLEEVED_LAYERS = ("jacket", "blazer", "leather_jacket", "lab_coat", "puffer", "cardigan")
PATTERN_KIND = {"stripes": ("hstripes", 1.0), "pinstripes": ("stripes", 9.0), "dots": ("dots", 1.0), "plaid": ("plaid", 1.0),
                "checker": ("checker", 1.0), "denim": ("denim", 1.0)}
HATS = {"beanie", "top_hat", "chef_hat", "cap", "crown"}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def plastic(name, col, rough=0.42, emission=0.10, metallic=0.0):
    """Plastique lisse façon jouet : un peu de brillance, couleurs franches."""
    return core.toon_mat(name, col, rough=rough, emission=emission, metallic=metallic)


def _block(name, size, mat, loc, parent, coll, bevel=0.06, rot=(0, 0, 0)):
    """Bloc arrondi (bevel relatif à la plus petite dimension) : la signature visuelle des avatars en blocs."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    off = bevel * min(size)
    if off > 1e-5:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=off, segments=3, affect='EDGES', profile=0.6)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    core.link(o, coll)
    if mat is not None:
        me.materials.append(mat)
    o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    return o


def _decal(name, w, h, img_path, loc, parent, coll):
    """Plan texturé transparent (décalcomanie de visage), tourné vers -Y."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x * w / 2, 0, z * h / 2)) for x, z in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for loop, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = (u, v)
    bm.to_mesh(me)
    bm.free()
    mname = "rbx_decal_" + Path(img_path).stem
    m = bpy.data.materials.get(mname)
    if m is None:
        m = bpy.data.materials.new(mname)
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(img_path), check_existing=True)
        t.interpolation = 'Cubic'
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
        b.inputs["Roughness"].default_value = 0.6
        try:
            m.surface_render_method = 'BLENDED'
        except (AttributeError, TypeError):
            pass
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    core.link(o, coll)
    o.parent = parent
    o.location = loc
    return o


def norm_part(n):
    n = re.sub(r"\.\d+$", "", n)
    n = re.sub(r"\d+$", "", n)
    return n.replace(" ", "").replace("_", "").lower()


R15 = ["Head", "UpperTorso", "LowerTorso", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm",
       "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
R6 = {"torso": "UpperTorso", "leftarm": "LeftUpperArm", "rightarm": "RightUpperArm", "leftleg": "LeftUpperLeg", "rightleg": "RightUpperLeg"}


def classify_parts(names):
    """noms d'objets importés -> ({pièce R15: nom}, [autres]) ; reconnaît « Head1 », « Left Arm », « UpperTorso.001 »."""
    body, extras = {}, []
    for n in names:
        k = norm_part(n)
        hit = next((p for p in R15 if p.lower() == k), None) or R6.get(k)
        if hit and hit not in body:
            body[hit] = n
        else:
            extras.append(n)
    return body, extras


class RobloxAvatar:
    MOUTHS = MOUTHS

    def __init__(self, cid, design, coll=None):
        self.id = cid
        self.d = d = _merge(DEFAULT_DESIGN, design)
        self.acting = {}
        self.coll = coll
        self.rng = random.Random(d.get("seed", sum(map(ord, cid))))
        self.joints, self.meshes, self.face = {}, [], {}
        self.flat_face = True
        b = d["body"]
        self.H = H = b["height"]
        self.hs, self.gs = b["head_scale"], b["girth"]
        self.ls, self.as_ = b["leg_length"], b["arm_length"]
        total = 0.3 + 2.3 * self.ls + 2.0 + 1.2 * self.hs
        self.u = u = 1.47 * H / total
        self.foot_h = 0.3 * u
        self.shin = 1.1 * u * self.ls
        self.thigh = 1.2 * u * self.ls
        self.hip_z = self.foot_h + self.shin + self.thigh
        self.torso_h = 2.0 * u
        self.torso_w = 1.0 * u * self.gs
        self.torso_d = 0.5 * u * min(self.gs, 1.3)
        self.upper, self.fore = 1.2 * u * self.as_, 1.0 * u * self.as_
        self.head_r = 0.6 * u * self.hs
        self.head_half = (0.66 * u * self.hs, 0.6 * u * self.hs, 0.6 * u * self.hs)
        self.ink = 0.0
        ref = d.get("roblox_avatar")
        if ref and (LIBRARY / ref / "avatar.obj").exists():
            self._build_imported(LIBRARY / ref)
        else:
            if ref:
                print(f"[roblox_avatar] avatar importé introuvable : {ref} -> avatar procédural")
            self._mats()
            self._build()
        self.rest = {n: (tuple(j.location), tuple(j.rotation_euler), tuple(j.scale)) for n, j in self.joints.items()}

    # ---------------------------------------------------------------- matériaux
    def _mats(self):
        d, o = self.d, self.d["outfit"]
        top, bot = o["top"], o["bottom"]

        def cloth(name, part, col_default):
            col = part.get("color", col_default)
            pat = part.get("pattern", "denim" if part.get("type") == "jeans" else "plain")
            if pat != "plain":
                kind, sc_ = PATTERN_KIND[pat]
                return core.pattern_mat(f"{self.id}_{name}_{pat}", kind, col, part.get("pattern_color", "#FFFFFF"), scale=sc_ * 0.8, emission=0.08)
            return plastic(f"{self.id}_{name}", col)
        self.m = {"skin": plastic(f"{self.id}_skin", d["skin"], rough=0.5), "top": cloth("top", top, "#3A7BD5"),
                  "bottom": cloth("bottom", bot, "#2D3142"), "accent": plastic(f"{self.id}_accent", top.get("accent", "#E63946")),
                  "hair": plastic(f"{self.id}_hair", d["hair"].get("color", "#3B2416"), rough=0.6),
                  "eye": plastic("rbx_eye", "#141214", rough=0.25, emission=0.0), "shine": core.emit_mat("rbx_shine", "#FFFFFF", 2.0),
                  "brow": plastic(f"{self.id}_brow", d["brows"].get("color", "#2A1B12"), rough=0.6, emission=0.0),
                  "blush": plastic("rbx_blush", "#FF8A98", emission=0.25), "tear": core.emit_mat("rbx_tear", "#7FD3FF", 1.0),
                  "white": plastic("rbx_white", "#F4F4F4"), "gold": plastic("rbx_gold", "#F4C430", rough=0.3, metallic=0.7),
                  "dark": plastic("rbx_dark", "#151515", rough=0.2), "print": plastic(f"{self.id}_print", top.get("print_color", "#FFFFFF"), emission=0.2)}
        sh = o.get("shoes", "#1E1E1E")
        self.shoe = sh if isinstance(sh, dict) else {"type": "sneakers", "color": sh}
        self.m["shoes"] = plastic(f"{self.id}_shoes", self.shoe.get("color", "#1E1E1E"))
        self.m["sole"] = plastic(f"{self.id}_sole", self.shoe.get("sole", "#F2F2F2"))
        lay = o.get("layer") or {}
        if lay.get("type", "none") != "none":
            self.m["layer"] = cloth("layer", lay, "#5A4636")
            self.m["layer_trim"] = plastic(f"{self.id}_layer_trim", lay.get("accent", "#2B2B2B"))

    def acc_mat(self, name, default=None):
        col = self.d.get("accessory_colors", {}).get(name) or default or self.d["outfit"]["top"].get("accent", "#E63946")
        return plastic(f"{self.id}_acc_{name}", col, rough=0.3 if name in ("watch", "gold_chain", "crown") else 0.45,
                       metallic=0.7 if name in ("gold_chain", "watch", "crown", "earrings") else 0.0)

    def _j(self, name, loc, parent):
        e = core.empty(f"{self.id}__{name}", loc, parent, self.coll)
        self.joints[name] = e
        return e

    def _b(self, name, size_half, mat, loc, parent, bevel=0.08, rot=(0, 0, 0)):
        o = _block(f"{self.id}_{name}", (size_half[0] * 2, size_half[1] * 2, size_half[2] * 2), mat, loc, parent, self.coll, bevel, rot)
        self.meshes.append(o)
        return o

    # ---------------------------------------------------------------- avatar procédural
    def _build(self):
        d, m, u = self.d, self.m, self.u
        o = d["outfit"]
        top_t, bot_t = o["top"]["type"], o["bottom"]["type"]
        lay_t = (o.get("layer") or {}).get("type", "none")
        gs, ls, as_ = self.gs, self.ls, self.as_
        root = self._j("root", (0, 0, 0), None)
        hips = self._j("hips", (0, 0, self.hip_z), root)
        legs_mat = m["bottom"] if bot_t in ("pants", "jeans") else m["skin"]
        lower_mat = m["top"] if top_t == "dress" else m["bottom"]
        self._b("lowertorso", (self.torso_w * 0.98, 0.5 * u * min(gs, 1.3), 0.2 * u), lower_mat, (0, 0, 0.2 * u), hips, bevel=0.15)
        spine = self._j("spine", (0, 0, 0.4 * u), hips)
        belly = d["body"].get("belly", 0.0)
        self._b("uppertorso", (self.torso_w, 0.5 * u * min(gs, 1.3) * (1 + 0.25 * belly), 0.8 * u), m["top"], (0, -0.06 * u * belly, 0.8 * u), spine, bevel=0.1)
        self._top_details(spine, hips, top_t, bot_t)
        neck = self._j("neck", (0, 0, 1.6 * u), spine)
        hx, hy, hz = self.head_half
        head = self._j("head", (0, 0, hz), neck)
        self._b("head", (hx, hy, hz), m["skin"], (0, 0, 0), head, bevel=0.32)
        self._face(head)
        follow = self._j("head_follow", (0, 0, 0), head)
        self._hair(follow)
        arm_w = 0.5 * u * math.sqrt(gs)
        for side, s in (("L", 1), ("R", -1)):
            sh = self._j(f"shoulder_{side}", (s * (self.torso_w + arm_w), 0, 1.4 * u), spine)
            ua = self._j(f"upper_arm_{side}", (0, 0, 0), sh)
            sleeves = o["top"].get("sleeves") or ("long" if top_t in LONG_SLEEVES else ("none" if top_t == "tank" else "short"))
            up_mat = m["skin"] if sleeves == "none" else m["top"]
            lo_mat = m["top"] if sleeves == "long" else m["skin"]
            if lay_t in SLEEVED_LAYERS:
                up_mat = lo_mat = m["layer"]
            self._b(f"upperarm_{side}", (arm_w, arm_w, self.upper / 2), up_mat, (0, 0, 0.2 * u - self.upper / 2), ua, bevel=0.12)
            el = self._j(f"forearm_{side}", (0, 0, 0.2 * u - self.upper), ua)
            self._b(f"lowerarm_{side}", (arm_w * 0.97, arm_w * 0.97, self.fore / 2), lo_mat, (0, 0, -self.fore / 2), el, bevel=0.12)
            hand = self._j(f"hand_{side}", (0, 0, -self.fore), el)
            self._b(f"hand_{side}", (arm_w * 0.95, arm_w * 0.95, 0.15 * u), m["skin"], (0, 0, -0.15 * u), hand, bevel=0.3)
            ua.rotation_euler = (0, -s * D(3), 0)
            el.rotation_euler = (D(-5), 0, 0)
        leg_w = 0.5 * u * math.sqrt(gs)
        for side, s in (("L", 1), ("R", -1)):
            th = self._j(f"thigh_{side}", (s * self.torso_w * 0.5, 0, 0), hips)
            up_mat = m["bottom"] if bot_t in ("pants", "jeans", "shorts") else m["skin"]
            if top_t == "dress":
                up_mat = m["skin"]
            self._b(f"upperleg_{side}", (leg_w, leg_w, self.thigh / 2), up_mat, (0, 0, -self.thigh / 2), th, bevel=0.12)
            kn = self._j(f"shin_{side}", (0, 0, -self.thigh), th)
            self._b(f"lowerleg_{side}", (leg_w * 0.97, leg_w * 0.97, self.shin / 2), legs_mat, (0, 0, -self.shin / 2), kn, bevel=0.12)
            ft = self._j(f"foot_{side}", (0, 0, -self.shin), kn)
            self._shoe(ft, side, leg_w)
        self._accessories(head, spine, hips, follow)

    def _top_details(self, spine, hips, top_t, bot_t):
        m, u, tw = self.m, self.u, self.torso_w
        td = 0.5 * u * min(self.gs, 1.3)
        top = self.d["outfit"]["top"]
        if top_t == "hoodie":
            self._b("hood", (tw * 0.7, 0.18 * u, 0.25 * u), m["top"], (0, td + 0.08 * u, 1.55 * u), spine, bevel=0.4)
            for s in (1, -1):
                self._b(f"string{s}", (0.03 * u, 0.02 * u, 0.22 * u), m["white"], (s * 0.25 * u, -td - 0.01 * u, 1.25 * u), spine)
        if top_t == "suit":
            self._b("shirtv", (tw * 0.3, 0.02 * u, 0.45 * u), m["white"], (0, -td - 0.005 * u, 1.15 * u), spine, bevel=0.1)
            self._b("suittie", (0.09 * u, 0.025 * u, 0.4 * u), m["accent"], (0, -td - 0.03 * u, 1.1 * u), spine, bevel=0.2)
        if top_t == "polo" or top.get("collar"):
            for s in (1, -1):
                self._b(f"collar{s}", (0.28 * u, 0.06 * u, 0.06 * u), m["accent"], (s * 0.3 * u, -td + 0.05 * u, 1.58 * u), spine, rot=(0, s * D(12), 0))
        if top_t == "dress" or bot_t == "skirt":
            mat = m["top"] if top_t == "dress" else m["bottom"]
            self._b("skirt", (tw * 1.12, td * 1.2, 0.42 * u), mat, (0, 0, -0.22 * u), hips, bevel=0.2)
        if top.get("pocket"):
            self._b("pocket", (0.2 * u, 0.02 * u, 0.18 * u), m["accent"], (-0.45 * u, -td - 0.01 * u, 1.15 * u), spine, bevel=0.2)
        txt = (top.get("print") or (str(self.rng.randint(1, 99)) if top_t == "jersey" else "")).strip()
        if txt:
            size = (0.55 if len(txt) <= 3 else 0.32) * u
            t = core.text_obj(f"{self.id}_print", txt.upper(), size, m["print"], (0, -td - 0.012 * u, 0.95 * u), parent=spine, coll=self.coll, extrude=0.004)
            self.meshes.append(t)
        self._layer(spine, td)

    def _layer(self, spine, td):
        lay = self.d["outfit"].get("layer") or {}
        lt = lay.get("type", "none")
        if lt == "none":
            return
        m, u, tw = self.m, self.u, self.torso_w
        if lt == "apron":
            self._b("apron", (tw * 0.75, 0.03 * u, 0.9 * u), m["layer"], (0, -td - 0.03 * u, 0.55 * u), spine, bevel=0.2)
            return
        long_ = lt in ("lab_coat",)
        h = 0.95 * u if not long_ else 1.25 * u
        for s in (1, -1):   # deux pans : veste ouverte sur le haut
            self._b(f"layer_front{s}", (tw * 0.42, 0.04 * u, h), m["layer"], (s * tw * 0.6, -td - 0.03 * u, 1.6 * u - h), spine, bevel=0.15)
            self._b(f"layer_lapel{s}", (0.07 * u, 0.045 * u, 0.4 * u), m["layer_trim"], (s * tw * 0.2, -td - 0.06 * u, 1.3 * u), spine, rot=(0, s * D(-14), 0))
        self._b("layer_back", (tw * 1.04, 0.04 * u, h), m["layer"], (0, td + 0.03 * u, 1.6 * u - h), spine, bevel=0.15)
        for s in (1, -1):
            self._b(f"layer_side{s}", (0.04 * u, td * 1.02, h), m["layer"], (s * (tw + 0.03 * u), 0, 1.6 * u - h), spine, bevel=0.15)
        if lt == "puffer":
            for k in range(3):
                self._b(f"puff{k}", (tw * 1.06, td * 1.12, 0.12 * u), m["layer"], (0, 0, 0.35 * u + k * 0.45 * u), spine, bevel=0.45)

    def _shoe(self, ft, side, leg_w):
        m, u = self.m, self.u
        t = self.shoe.get("type", "sneakers")
        hz = 0.15 * u
        if t == "boots":
            self._b(f"bootshaft_{side}", (leg_w * 1.03, leg_w * 1.03, 0.25 * u), m["shoes"], (0, 0, 0.2 * u), ft, bevel=0.15)
        self._b(f"foot_{side}", (leg_w * 1.0, leg_w * 1.12, hz), m["shoes"], (0, -0.06 * u, -hz), ft, bevel=0.25)
        if t in ("sneakers", "boots"):
            self._b(f"sole_{side}", (leg_w * 1.02, leg_w * 1.14, 0.035 * u), m["sole"], (0, -0.06 * u, -2 * hz + 0.035 * u), ft, bevel=0.3)

    # ---------------------------------------------------------------- visage plat
    def brow_y(self, bz, bx):
        return -self.head_half[1] - 0.012 * self.u

    def _face(self, head):
        d, m, u = self.d, self.m, self.u
        hx, hy, hz = self.head_half
        front = -hy - 0.004 * u
        es = d["eyes"].get("size", 1.0) * self.hs
        sp = d["eyes"].get("spacing", 1.0)
        for side, s in (("L", 1), ("R", -1)):
            eye = core.empty(f"{self.id}__eye_{side}", (s * 0.24 * u * sp * self.hs, front, 0.1 * u * self.hs), head, self.coll)
            self.face[f"eye_{side}"] = eye
            self.meshes.append(core.ball(f"{self.id}_eye_{side}", (0.075 * u * es, 0.012 * u, 0.115 * u * es), m["eye"], (0, 0, 0), parent=eye, coll=self.coll, detail=2, smooth=True))
            pup = core.empty(f"{self.id}__pupil_{side}", (-s * 0.02 * u * es, -0.01 * u, 0.04 * u * es), eye, self.coll)
            self.face[f"pupil_{side}"] = pup
            core.ball(f"{self.id}_shine_{side}", (0.024 * u * es, 0.006 * u, 0.03 * u * es), m["shine"], (0, 0, 0), parent=pup, coll=self.coll, detail=1)
            bt = d["brows"].get("thickness", 1.0)
            brow = core.empty(f"{self.id}__brow_{side}", (s * 0.24 * u * sp * self.hs, front - 0.008 * u, 0.3 * u * self.hs), head, self.coll)
            self.face[f"brow_{side}"] = brow
            self.meshes.append(_block(f"{self.id}_browbar_{side}", (0.2 * u * self.hs, 0.02 * u, 0.045 * u * bt), m["brow"], (0, 0, 0), brow, self.coll, bevel=0.3))
            blush = core.ball(f"{self.id}_blush_{side}", (0.09 * u, 0.008 * u, 0.05 * u), m["blush"], (s * 0.4 * u * self.hs, front, -0.12 * u * self.hs), parent=head, coll=self.coll, detail=1)
            blush.scale = (0.001,) * 3
            self.face[f"blush_{side}"] = blush
            tear = core.ball(f"{self.id}_tear_{side}", (0.03 * u, 0.01 * u, 0.06 * u), m["tear"], (s * 0.24 * u * sp * self.hs, front - 0.01 * u, -0.06 * u), parent=head, coll=self.coll, detail=1)
            tear.scale = (0.001,) * 3
            self.face[f"tear_{side}"] = tear
        mw = d["mouth"].get("width", 1.0) * self.hs
        mouth = core.empty(f"{self.id}__mouth", (0, front - 0.006 * u, -0.22 * u * self.hs), head, self.coll)
        self.face["mouth"] = mouth
        shapes = {}
        for k in MOUTHS:
            f = FACES / f"mouth_{k}.png"
            if f.exists():
                shapes[k] = _decal(f"{self.id}_m_{k}", 0.6 * u * mw, 0.3 * u * mw, f, (0, 0, 0), mouth, self.coll)
            else:
                shapes[k] = core.empty(f"{self.id}__m_{k}", (0, 0, 0), mouth, self.coll)
        for k, o in shapes.items():
            o.scale = (1, 1, 1) if k == "line" else (0.001, 0.001, 0.001)
        self.face["mouths"] = shapes

    # ---------------------------------------------------------------- coiffures et accessoires en blocs
    def _hair(self, follow):
        st = self.d["hair"]["style"]
        if st == "none":
            return
        acc = set(self.d.get("accessories", []))
        if acc & HATS and st in ("spiky", "curly", "mohawk", "bun"):
            st = "short"
        m, u = self.m, self.u
        hx, hy, hz = self.head_half
        cap_t = 0.12 * u

        def cap(extra_back=0.0):
            self._b("hair_cap", (hx + 0.06 * u, hy + 0.06 * u + extra_back / 2, cap_t + 0.08 * u), m["hair"], (0, extra_back / 2, hz + 0.01 * u), follow, bevel=0.35)
            self._b("hair_back", (hx + 0.05 * u, 0.1 * u, hz * 0.7), m["hair"], (0, hy + 0.04 * u, hz * 0.3), follow, bevel=0.35)
            for s in (1, -1):
                self._b(f"hair_side{s}", (0.06 * u, hy * 0.8, hz * 0.45), m["hair"], (s * (hx + 0.03 * u), 0.08 * u, hz * 0.5), follow, bevel=0.35)
        if st in ("short", "bun", "long", "bowl", "spiky", "curly"):
            cap()
        if st == "bowl":
            self._b("fringe", (hx + 0.05 * u, 0.07 * u, 0.13 * u), m["hair"], (0, -hy - 0.03 * u, hz * 0.62), follow, bevel=0.35)
        if st == "spiky":
            for k, (x, y, rx, ry) in enumerate(((-0.35, -0.2, -20, -15), (0.0, -0.3, -25, 0), (0.35, -0.2, -20, 15), (-0.2, 0.25, 15, -10), (0.25, 0.25, 15, 10))):
                self._b(f"spike{k}", (0.13 * u, 0.13 * u, 0.22 * u), m["hair"], (x * u, y * u, hz + 0.25 * u), follow, bevel=0.2, rot=(D(rx), D(ry), D(45)))
        if st == "mohawk":
            self._b("mohawk", (0.1 * u, hy * 0.95, 0.24 * u), m["hair"], (0, 0.05 * u, hz + 0.2 * u), follow, bevel=0.3)
        if st == "bun":
            self.meshes.append(core.ball(f"{self.id}_bun", (0.22 * u,) * 3, m["hair"], (0, 0.3 * u, hz + 0.28 * u), parent=follow, coll=self.coll, detail=2, smooth=True))
        if st == "long":
            self._b("hair_long", (hx + 0.08 * u, 0.12 * u, 0.75 * u), m["hair"], (0, hy + 0.06 * u, -0.25 * u), follow, bevel=0.3)
            for s in (1, -1):
                self._b(f"hair_long_side{s}", (0.08 * u, 0.2 * u, 0.55 * u), m["hair"], (s * (hx + 0.06 * u), -0.1 * u, -0.1 * u), follow, bevel=0.3)
        if st == "curly":
            for k in range(9):
                a = 2 * math.pi * k / 9
                self.meshes.append(core.ball(f"{self.id}_curl{k}", (0.2 * u,) * 3, m["hair"], (math.cos(a) * hx * 0.85, math.sin(a) * hy * 0.85, hz + 0.12 * u), parent=follow, coll=self.coll, detail=1, smooth=True))

    def _accessories(self, head, spine, hips, follow):
        acc = list(self.d.get("accessories", []))
        u = self.u
        hx, hy, hz = self.head_half
        td = 0.5 * u * min(self.gs, 1.3)
        front = -hy
        for a in acc:
            mt = self.acc_mat(a)
            if a == "cap":
                self._b("cap", (hx + 0.08 * u, hy + 0.08 * u, 0.2 * u), mt, (0, 0.02 * u, hz + 0.16 * u), follow, bevel=0.4)
                self._b("cap_brim", (hx * 0.85, 0.32 * u, 0.035 * u), mt, (0, -hy - 0.24 * u, hz + 0.02 * u), follow, bevel=0.3)
            elif a == "beanie":
                self._b("beanie", (hx + 0.09 * u, hy + 0.09 * u, 0.3 * u), mt, (0, 0, hz + 0.08 * u), follow, bevel=0.45)
                self._b("beanie_fold", (hx + 0.12 * u, hy + 0.12 * u, 0.09 * u), mt, (0, 0, hz - 0.18 * u), follow, bevel=0.4)
            elif a == "top_hat":
                self._b("tophat", (hx * 0.7, hy * 0.7, 0.42 * u), self.acc_mat(a, "#1B1B1B"), (0, 0, hz + 0.5 * u), follow, bevel=0.1)
                self._b("tophat_brim", (hx + 0.12 * u, hy + 0.12 * u, 0.035 * u), self.acc_mat(a, "#1B1B1B"), (0, 0, hz + 0.1 * u), follow, bevel=0.3)
            elif a == "chef_hat":
                self._b("chef_band", (hx + 0.05 * u, hy + 0.05 * u, 0.12 * u), self.m["white"], (0, 0, hz + 0.12 * u), follow, bevel=0.3)
                for k in range(4):
                    self.meshes.append(core.ball(f"{self.id}_chefpuff{k}", (0.3 * u,) * 3, self.m["white"], ((k % 2 - 0.5) * 0.35 * u, (k // 2 - 0.5) * 0.35 * u, hz + 0.45 * u), parent=follow, coll=self.coll, detail=2, smooth=True))
            elif a == "crown":
                gold = self.m["gold"]
                self._b("crown", (hx * 0.8, hy * 0.8, 0.1 * u), gold, (0, 0, hz + 0.12 * u), follow, bevel=0.2)
                for k, (x, y) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1))):
                    self._b(f"crownpt{k}", (0.07 * u, 0.07 * u, 0.12 * u), gold, (x * hx * 0.7, y * hy * 0.7, hz + 0.3 * u), follow, bevel=0.2, rot=(0, 0, D(45)))
            elif a in ("headband", "bandana"):
                self._b(a, (hx + 0.07 * u, hy + 0.07 * u, 0.07 * u), mt, (0, 0, hz * 0.62), follow, bevel=0.3)
            elif a == "headphones":
                self._b("hp_band", (hx + 0.12 * u, 0.06 * u, 0.05 * u), mt, (0, 0, hz + 0.18 * u), follow, bevel=0.3)
                for s in (1, -1):
                    self._b(f"hp_cup{s}", (0.08 * u, 0.2 * u, 0.22 * u), mt, (s * (hx + 0.1 * u), 0, 0), follow, bevel=0.4)
            elif a in ("glasses", "sunglasses"):
                lens = self.m["dark"] if a == "sunglasses" else plastic("rbx_lens", "#CFE8FF", rough=0.05, emission=0.05)
                fr = self.acc_mat(a, "#1B1B1B")
                for s in (1, -1):
                    self._b(f"{a}_lens{s}", (0.13 * u, 0.012 * u, 0.1 * u), lens, (s * 0.24 * u * self.hs, front - 0.03 * u, 0.1 * u * self.hs), head, bevel=0.3)
                    self._b(f"{a}_frame{s}", (0.15 * u, 0.01 * u, 0.12 * u), fr, (s * 0.24 * u * self.hs, front - 0.022 * u, 0.1 * u * self.hs), head, bevel=0.2)
                self._b(f"{a}_bridge", (0.06 * u, 0.012 * u, 0.02 * u), fr, (0, front - 0.03 * u, 0.13 * u * self.hs), head)
            elif a == "mustache":
                self._b("mustache", (0.2 * u, 0.025 * u, 0.05 * u), self.m["hair"], (0, front - 0.02 * u, -0.1 * u), head, bevel=0.4)
            elif a == "beard":
                self._b("beard", (hx * 0.85, 0.1 * u, 0.2 * u), self.m["hair"], (0, front + 0.05 * u, -hz * 0.75), head, bevel=0.4)
            elif a == "earrings":
                for s in (1, -1):
                    self.meshes.append(core.ball(f"{self.id}_earring{s}", (0.04 * u,) * 3, self.m["gold"], (s * (hx + 0.02 * u), 0, -0.2 * u), parent=head, coll=self.coll, detail=1))
            elif a in ("tie", "bowtie"):
                if a == "tie":
                    self._b("tie", (0.09 * u, 0.025 * u, 0.42 * u), mt, (0, -td - 0.03 * u, 1.1 * u), spine, bevel=0.2)
                else:
                    for s in (1, -1):
                        self._b(f"bowtie{s}", (0.1 * u, 0.03 * u, 0.07 * u), mt, (s * 0.09 * u, -td - 0.03 * u, 1.5 * u), spine, bevel=0.3, rot=(0, s * D(10), 0))
            elif a == "scarf":
                self._b("scarf", (self.torso_w * 0.75, td + 0.08 * u, 0.12 * u), mt, (0, 0, 1.55 * u), spine, bevel=0.45)
                self._b("scarf_tail", (0.12 * u, 0.04 * u, 0.3 * u), mt, (0.3 * u, -td - 0.08 * u, 1.25 * u), spine, bevel=0.3)
            elif a in ("necklace", "gold_chain"):
                self.meshes.append(core.torus(f"{self.id}_{a}", 0.32 * u, 0.025 * u, self.m["gold"], (0, -td * 0.5, 1.45 * u), (D(60), 0, 0), parent=spine, coll=self.coll))
            elif a == "watch":
                self._b("watch", (0.27 * u, 0.27 * u, 0.06 * u), mt, (0, 0, -0.75 * self.fore), self.joints["forearm_L"], bevel=0.3)
            elif a == "backpack":
                self._b("backpack", (self.torso_w * 0.72, 0.28 * u, 0.62 * u), mt, (0, td + 0.3 * u, 0.85 * u), spine, bevel=0.3)
                self._b("backpack_pocket", (self.torso_w * 0.5, 0.08 * u, 0.25 * u), self.m["accent"], (0, td + 0.6 * u, 0.6 * u), spine, bevel=0.3)
            elif a == "shoulder_bag":
                self._b("bag", (0.35 * u, 0.12 * u, 0.28 * u), mt, (self.torso_w + 0.15 * u, -0.1 * u, 0.15 * u), hips, bevel=0.3)
                self._b("bag_strap", (0.04 * u, td + 0.04 * u, 1.0 * u), mt, (0, 0, 0.9 * u), spine, bevel=0.2, rot=(0, D(35), 0))
            elif a == "badge":
                self._b("badge", (0.12 * u, 0.02 * u, 0.15 * u), self.m["gold"], (-0.5 * u, -td - 0.02 * u, 1.25 * u), spine, bevel=0.3)
            elif a == "flower_pin":
                self.meshes.append(core.ball(f"{self.id}_flower", (0.1 * u, 0.04 * u, 0.1 * u), plastic("rbx_flower", "#FF5C8A"), (-0.5 * u, -td - 0.03 * u, 1.3 * u), parent=spine, coll=self.coll, detail=1))

    # ---------------------------------------------------------------- avatar importé (export Roblox Studio)
    def _build_imported(self, folder):
        meta = {}
        if (folder / "avatar.json").exists():
            meta = json.loads((folder / "avatar.json").read_text(encoding="utf-8"))
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=str(folder / "avatar.obj"), forward_axis=meta.get("forward_axis", "NEGATIVE_Z"), up_axis=meta.get("up_axis", "Y"))
        objs = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
        for o in objs:
            if self.coll is not None:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                self.coll.objects.link(o)
            o.name = f"{self.id}_{o.name}"
        for mt in {s.material for o in objs for s in o.material_slots if s.material}:
            if mt.use_nodes:
                bsdf = next((n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                tex = next((n for n in mt.node_tree.nodes if n.type == 'TEX_IMAGE'), None)
                if bsdf and tex and not bsdf.inputs["Alpha"].is_linked:
                    mt.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
                if bsdf:
                    bsdf.inputs["Roughness"].default_value = 0.42
        byname = {o.name[len(self.id) + 1:]: o for o in objs}
        parts, extras = classify_parts(list(byname))
        body = {p: byname[n] for p, n in parts.items()}
        if "Head" not in body or ("UpperTorso" not in body):
            raise RuntimeError(f"avatar importé {folder.name} : pièces Head/UpperTorso introuvables ({sorted(byname)[:12]})")
        bpy.context.view_layer.update()

        def bb(o):
            pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
            return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
                    Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
        feet = min(bb(o)[0].z for o in objs)
        top = max(bb(o)[1].z for o in objs)
        ut = bb(body["UpperTorso"])
        cx, cy = (ut[0].x + ut[1].x) / 2, (ut[0].y + ut[1].y) / 2
        k = 1.47 * self.H / max(1e-6, top - feet)
        for o in objs:
            o.location = (o.location - Vector((cx, cy, feet))) * k
            o.scale = o.scale * k
        bpy.context.view_layer.update()
        self.meshes = list(objs)

        def tc(o, inset=0.0):
            a, b = bb(o)
            return Vector(((a.x + b.x) / 2, (a.y + b.y) / 2, b.z - inset))

        def mid(o):
            a, b = bb(o)
            return (a + b) / 2
        root = self._j("root", (0, 0, 0), None)
        lt = body.get("LowerTorso", body["UpperTorso"])
        ul = body.get("LeftUpperLeg")
        hip_z = tc(ul).z if ul else bb(lt)[0].z
        hips = self._j("hips", (0, 0, hip_z), root)
        waist_z = tc(lt).z if "LowerTorso" in body else hip_z
        spine = self._j("spine", (0, 0, waist_z - hip_z), hips)
        hd = body["Head"]
        neck_z = bb(hd)[0].z
        neck = self._j("neck", (0, 0, neck_z - waist_z), spine)
        hc = mid(hd)
        head = self._j("head", (0, 0, hc.z - neck_z), neck)
        follow = self._j("head_follow", (0, 0, 0), head)
        a, b = bb(hd)
        self.head_half = ((b.x - a.x) / 2, (b.y - a.y) / 2, (b.z - a.z) / 2)
        self.head_r = self.head_half[2]
        self.torso_w = (ut[1].x - ut[0].x) / 2 * k
        self.hip_z = hip_z
        self.torso_h = neck_z - hip_z
        bpy.context.view_layer.update()

        def J(name, world_pos, parent):
            e = self._j(name, (0, 0, 0), parent)
            bpy.context.view_layer.update()
            e.location = parent.matrix_world.inverted() @ world_pos
            bpy.context.view_layer.update()
            return e
        owner = {"Head": head, "UpperTorso": spine, "LowerTorso": hips}
        for side, S in (("L", "Left"), ("R", "Right")):
            ua_o, la_o, ha_o = body.get(S + "UpperArm"), body.get(S + "LowerArm"), body.get(S + "Hand")
            sh = J(f"shoulder_{side}", tc(ua_o, 0.15 * (bb(ua_o)[1].x - bb(ua_o)[0].x)), spine)
            ua = self._j(f"upper_arm_{side}", (0, 0, 0), sh)
            el = J(f"forearm_{side}", tc(la_o) if la_o else Vector((sh.matrix_world.translation.x, 0, bb(ua_o)[0].z)), ua)
            hd_ = J(f"hand_{side}", tc(ha_o) if ha_o else Vector((el.matrix_world.translation.x, 0, bb(ua_o)[0].z)), el)
            ul_o, ll_o, ft_o = body.get(S + "UpperLeg"), body.get(S + "LowerLeg"), body.get(S + "Foot")
            th = J(f"thigh_{side}", tc(ul_o), hips)
            kn = J(f"shin_{side}", tc(ll_o) if ll_o else Vector((th.matrix_world.translation.x, 0, (bb(ul_o)[0].z + bb(ul_o)[1].z) / 2)), th)
            ft = J(f"foot_{side}", tc(ft_o) if ft_o else Vector((kn.matrix_world.translation.x, 0, bb(ul_o)[0].z + 0.05)), kn)
            owner.update({S + "UpperArm": ua, S + "LowerArm": el if la_o else ua, S + "Hand": hd_ if ha_o else ua,
                          S + "UpperLeg": th, S + "LowerLeg": kn if ll_o else th, S + "Foot": ft if ft_o else th})
        if self.joints.get("thigh_L"):
            self.thigh = (self.joints["thigh_L"].matrix_world.translation - self.joints["shin_L"].matrix_world.translation).length or 0.3
            self.shin = (self.joints["shin_L"].matrix_world.translation - self.joints["foot_L"].matrix_world.translation).length or 0.3
        bpy.context.view_layer.update()

        def attach(o, j):
            mw = o.matrix_world.copy()
            o.parent = j
            o.matrix_parent_inverse = j.matrix_world.inverted()
            o.matrix_world = mw
        for p, o in body.items():
            attach(o, owner[p])
        for n in extras:
            o = byname[n]
            c = mid(o)

            def dist(part):
                pa, pb = bb(body[part])
                q = Vector((min(max(c.x, pa.x), pb.x), min(max(c.y, pa.y), pb.y), min(max(c.z, pa.z), pb.z)))
                return (q - c).length
            best = min(body, key=dist)
            attach(o, follow if best == "Head" else owner[best])
        # visage : décalcomanies du moteur par-dessus la tête (exporter l'avatar SANS visage pour un rendu propre)
        self.u = self.head_r / 0.6
        self.hs = 1.0
        if meta.get("face", "procedural") == "procedural":
            self.m = {"eye": plastic("rbx_eye", "#141214", rough=0.25, emission=0.0), "shine": core.emit_mat("rbx_shine", "#FFFFFF", 2.0),
                      "brow": plastic(f"{self.id}_brow", meta.get("brow_color", "#2A1B12"), rough=0.6, emission=0.0),
                      "blush": plastic("rbx_blush", "#FF8A98", emission=0.25), "tear": core.emit_mat("rbx_tear", "#7FD3FF", 1.0)}
            self._face(head)
        else:
            for side in ("L", "R"):
                for part in ("eye", "pupil", "brow", "blush", "tear"):
                    self.face[f"{part}_{side}"] = core.empty(f"{self.id}__{part}_{side}", (0, -self.head_half[1], 0), head, self.coll)
            self.face["mouth"] = core.empty(f"{self.id}__mouth", (0, -self.head_half[1], -0.1), head, self.coll)
            self.face["mouths"] = {k: core.empty(f"{self.id}__m_{k}", (0, 0, 0), self.face["mouth"], self.coll) for k in MOUTHS}

    # ---------------------------------------------------------------- placement / repères (identiques à Character)
    def place(self, x, y, facing_rad):
        root = self.joints["root"]
        root.location = (x, y, 0)
        root.rotation_euler = (0, 0, facing_rad)

    def landmarks_world(self):
        j = self.joints
        head = j["head"].matrix_world.translation.copy()
        root = j["root"].matrix_world.translation.copy()
        up = Vector((0, 0, 1))
        return {
            "feet": root,
            "hips": j["hips"].matrix_world.translation.copy(),
            "chest": j["neck"].matrix_world.translation.copy() - up * self.torso_h * 0.3,
            "neck": j["neck"].matrix_world.translation.copy(),
            "head": head,
            "eyes": (self.face["eye_L"].matrix_world.translation + self.face["eye_R"].matrix_world.translation) / 2,
            "head_top": Vector((head.x, head.y, max(head.z + self.head_r * 1.05, self._top_z()))),
            "hand_L": j["hand_L"].matrix_world.translation.copy(),
            "hand_R": j["hand_R"].matrix_world.translation.copy(),
        }

    def _top_z(self):
        hj = self.joints["head"]
        fol = self.joints.get("head_follow")
        zs = [(o.matrix_world @ Vector(c)).z for o in self.meshes if o.parent is not None and o.parent in (hj, fol) for c in o.bound_box]
        return max(zs) if zs else 0.0

    def facing_vector(self):
        rz = self.joints["root"].matrix_world.to_euler().z
        return Vector((math.sin(rz), -math.cos(rz), 0))
