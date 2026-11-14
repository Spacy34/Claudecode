"""Personnages low-poly 'goofy' procéduraux, entièrement déterminés par leur fiche cast_bible.

Rig = hiérarchie d'empties (pas d'armature) : robuste en headless, aucune opération en mode édition,
pièces rigides parentées aux articulations (style low-poly segmenté). Le personnage regarde -Y.
Côté gauche du personnage = +X.
"""
import math
import random
from mathutils import Vector
from . import core

D = math.radians

DEFAULT_DESIGN = {
    "body": {"height": 1.0, "girth": 1.0, "head_scale": 1.0, "leg_length": 1.0, "arm_length": 1.0, "belly": 0.2},
    "skin": "#F2C29B",
    "hair": {"style": "short", "color": "#3B2416"},
    "eyes": {"size": 1.0, "spacing": 1.0, "iris": "#2B2B2B"},
    "brows": {"thickness": 1.0, "color": "#2A1B12"},
    "nose": {"shape": "round", "size": 1.0},
    "mouth": {"width": 1.0},
    "outfit": {"top": {"type": "tshirt", "color": "#3A7BD5"}, "bottom": {"type": "pants", "color": "#2D3142"}, "shoes": "#1E1E1E"},
    "accessories": [],
}


# motif -> (type de texture procédurale de core.pattern_mat, échelle) : tailles adaptées à un vêtement (≈ 6 cm)
PATTERN_KIND = {"stripes": ("hstripes", 1.0), "pinstripes": ("stripes", 9.0), "dots": ("dots", 1.0), "plaid": ("plaid", 1.0),
                "checker": ("checker", 1.0), "denim": ("denim", 1.0)}
SLEEVED_LAYERS = ("jacket", "blazer", "leather_jacket", "lab_coat", "puffer", "cardigan")
LONG_SLEEVE_TOPS = ("shirt", "hoodie", "suit", "sweater")


def _shade_hex(h, k):
    h = h.lstrip("#")
    return "#" + "".join(f"{max(0, min(255, int(int(h[i:i + 2], 16) * k))):02X}" for i in (0, 2, 4))


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


class Character:
    MOUTHS = ("line", "smile", "frown", "smirk", "open_o", "open_wide", "grin", "talk_a", "talk_b")

    def __init__(self, cid, design, coll=None):
        self.id = cid
        self.d = d = _merge(DEFAULT_DESIGN, design)
        self.coll = coll
        self.rng = random.Random(d.get("seed", sum(map(ord, cid))))
        b = d["body"]
        H = b["height"]
        self.H = H
        self.head_r = 0.27 * b["head_scale"] * H
        self.thigh = 0.22 * b["leg_length"] * H
        self.shin = 0.21 * b["leg_length"] * H
        self.foot_h = 0.06 * H
        self.hip_z = self.thigh + self.shin + self.foot_h
        self.torso_h = 0.40 * H
        self.torso_w = 0.19 * b["girth"] * H
        self.torso_d = 0.14 * b["girth"] * H
        self.upper = 0.19 * b["arm_length"] * H
        self.fore = 0.18 * b["arm_length"] * H
        self.neck_len = 0.05 * H
        self.head_cz = self.hip_z + self.torso_h + self.neck_len + self.head_r * 0.92
        self.height = self.head_cz + self.head_r * 1.05
        self.ink = 0.020 * H   # contours épais : lisibilité à taille téléphone
        self.joints = {}
        self.meshes = []
        self.face = {}
        self._mats()
        self._build()

    # ---------------------------------------------------------------- matériaux
    def _mats(self):
        d = self.d
        o = d["outfit"]
        top_col = o["top"]["color"]
        flat = 0.35   # part d'auto-illumination : aplats de couleur franche, peu dépendants de l'éclairage
        self.m = {
            "skin": core.toon_mat(f"{self.id}_skin", d["skin"], rough=0.8, emission=flat),
            "top": core.toon_mat(f"{self.id}_top", top_col, emission=flat),
            "accent": core.toon_mat(f"{self.id}_accent", o["top"].get("accent", "#E63946"), emission=flat),
            "bottom": core.toon_mat(f"{self.id}_bottom", o["bottom"]["color"], emission=flat * 0.8),

            "hair": core.toon_mat(f"{self.id}_hair", d["hair"].get("color", "#3B2416"), rough=0.9, emission=flat * 0.6),
            "brow": core.toon_mat(f"{self.id}_brow", d["brows"].get("color", "#2A1B12")),
            "white": core.toon_mat("eye_white", "#FFFFFF", rough=0.4, emission=0.25),
            "iris": core.toon_mat(f"{self.id}_iris", d["eyes"].get("iris", "#2B2B2B"), rough=0.3),
            "shine": core.emit_mat("eye_shine", "#FFFFFF", 3.0),
            "mouth": core.toon_mat("mouth_dark", "#3A0E12", rough=0.9),
            "tongue": core.toon_mat("tongue", "#E86A7A"),
            "teeth": core.toon_mat("teeth", "#FFFFFF", emission=0.2),
            "blush": core.toon_mat("blush", "#FF7A8A", emission=0.2),
            "tear": core.emit_mat("tear", "#7FD3FF", 1.2),
            "gold": core.toon_mat("gold", "#F4C430", rough=0.3, metallic=0.6),
            "dark": core.toon_mat("lens_dark", "#111111", rough=0.2),
            "chef": core.toon_mat("chef_white", "#F7F7F7", emission=0.3),
        }
        # motifs et couche supérieure (garde-robe v2)
        top = o["top"]
        if top.get("pattern", "plain") != "plain":
            kind, sc_ = PATTERN_KIND[top["pattern"]]
            self.m["top"] = core.pattern_mat(f"{self.id}_top_{top['pattern']}", kind, top_col, top.get("pattern_color", "#FFFFFF"), scale=sc_, emission=flat)
        bot = o["bottom"]
        bpat = bot.get("pattern", "denim" if bot.get("type") == "jeans" else "plain")
        if bpat != "plain":
            kind, sc_ = PATTERN_KIND[bpat]
            self.m["bottom"] = core.pattern_mat(f"{self.id}_bottom_{bpat}", kind, bot["color"], bot.get("pattern_color", "#FFFFFF"), scale=sc_, emission=flat * 0.8)
        lay = o.get("layer") or {}
        if lay.get("type", "none") != "none":
            lc = lay.get("color", "#5A4636")
            if lay.get("pattern", "plain") != "plain":
                kind, sc_ = PATTERN_KIND[lay["pattern"]]
                self.m["layer"] = core.pattern_mat(f"{self.id}_layer_{lay['pattern']}", kind, lc, lay.get("pattern_color", "#FFFFFF"), scale=sc_, emission=flat)
            else:
                rough = 0.35 if lay["type"] == "leather_jacket" else 0.8
                self.m["layer"] = core.toon_mat(f"{self.id}_layer", lc, rough=rough, emission=flat * (0.6 if lay["type"] == "leather_jacket" else 1.0))
            self.m["layer_trim"] = core.toon_mat(f"{self.id}_layer_trim", lay.get("accent", "#2B2B2B"), emission=flat * 0.7)
        sh = o.get("shoes", "#1E1E1E")
        self.shoe = sh if isinstance(sh, dict) else {"type": "sneakers", "color": sh}
        self.m["shoes"] = core.toon_mat(f"{self.id}_shoes", self.shoe.get("color", "#1E1E1E"), rough=0.25 if self.shoe.get("type") == "dress_shoes" else 0.5, emission=flat * 0.6)
        self.m["sole"] = core.toon_mat(f"{self.id}_sole", self.shoe.get("sole", "#F2F2F2"), emission=flat * 0.6)
        self.m["print"] = core.toon_mat(f"{self.id}_print", top.get("print_color", "#FFFFFF"), emission=0.3)

    def acc_mat(self, name, default=None):
        """Couleur d'un accessoire : design.accessory_colors[nom], sinon la couleur d'accent du haut."""
        col = self.d.get("accessory_colors", {}).get(name) or default or self.d["outfit"]["top"].get("accent", "#E63946")
        return core.toon_mat(f"{self.id}_acc_{name}", col, emission=0.3, rough=0.4 if name in ("watch", "gold_chain") else 0.75,
                             metallic=0.6 if name in ("gold_chain", "watch") else 0.0)

    def _j(self, name, loc, parent):
        e = core.empty(f"{self.id}__{name}", loc, parent, self.coll)
        self.joints[name] = e
        return e

    def _mesh(self, o):
        self.meshes.append(o)
        return o

    # ---------------------------------------------------------------- construction
    def _build(self):
        d, m, r = self.d, self.m, self.head_r
        top_t, bot_t = d["outfit"]["top"]["type"], d["outfit"]["bottom"]["type"]
        root = self._j("root", (0, 0, 0), None)
        hips = self._j("hips", (0, 0, self.hip_z), root)
        spine = self._j("spine", (0, 0, 0), hips)
        # bassin
        pelvis_mat = m["top"] if top_t == "dress" else m["bottom"]
        self._mesh(core.ball(f"{self.id}_pelvis", (self.torso_w * 0.95, self.torso_d * 0.95, 0.11 * self.H), pelvis_mat, (0, 0, 0.02), parent=hips, coll=self.coll, ink=self.ink))
        # torse (œuf + ventre)
        tz = self.torso_h * 0.5
        self._mesh(core.ball(f"{self.id}_torso", (self.torso_w, self.torso_d, self.torso_h * 0.58), m["top"], (0, 0, tz), parent=spine, coll=self.coll, ink=self.ink))
        belly = d["body"].get("belly", 0.2)
        if belly > 0.05:
            self._mesh(core.ball(f"{self.id}_belly", (self.torso_w * 0.85, self.torso_d * (0.8 + belly * 0.6), self.torso_h * 0.38), m["top"], (0, -self.torso_d * belly * 0.35, tz * 0.75), parent=spine, coll=self.coll))
        if top_t == "suit":
            self._mesh(core.box(f"{self.id}_shirtv", (self.torso_w * 0.45, 0.01, self.torso_h * 0.45), core.toon_mat("shirt_white", "#F5F5F5", emission=0.1), (0, -self.torso_d * 0.98, self.torso_h * 0.72), parent=spine, coll=self.coll))
        if top_t == "hoodie":
            self._mesh(core.torus(f"{self.id}_hood", self.torso_w * 0.55, 0.05 * self.H, m["top"], (0, self.torso_d * 0.35, self.torso_h * 0.98), (D(70), 0, 0), parent=spine, coll=self.coll, ink=self.ink))
        if top_t == "dress":
            self._mesh(core.cyl(f"{self.id}_dress", self.torso_w * 1.55, self.torso_w * 0.9, 0.30 * self.H, m["top"], (0, 0, -0.12 * self.H), parent=hips, coll=self.coll, ink=self.ink, seg=10))
        if bot_t == "skirt" and top_t != "dress":
            self._mesh(core.cyl(f"{self.id}_skirt", self.torso_w * 1.45, self.torso_w * 0.95, 0.22 * self.H, m["bottom"], (0, 0, -0.07 * self.H), parent=hips, coll=self.coll, ink=self.ink, seg=10))
        self._top_details(spine, hips, top_t)
        self._layer(spine, hips)
        self._belt(hips)
        # cou + tête
        neck = self._j("neck", (0, 0, self.torso_h), spine)
        self._mesh(core.cyl(f"{self.id}_neck", 0.045 * self.H, 0.05 * self.H, self.neck_len * 2, m["skin"], (0, 0, self.neck_len * 0.5), parent=neck, coll=self.coll))
        head = self._j("head", (0, 0, self.neck_len + r * 0.92), neck)
        self._mesh(core.ball(f"{self.id}_head", (r, r * 0.95, r * 0.98), m["skin"], (0, 0, 0), parent=head, coll=self.coll, ink=self.ink * 1.2, detail=2))
        for s in (1, -1):
            self._mesh(core.ball(f"{self.id}_ear{'L' if s > 0 else 'R'}", (r * 0.16, r * 0.09, r * 0.22), m["skin"], (s * r * 0.97, 0, 0), parent=head, coll=self.coll, ink=self.ink * 0.6, detail=1))
        self._face(head)
        follow = self._j("head_follow", (0, 0, 0), head)   # cheveux/chapeaux : retard animé (follow-through)
        self._hair(follow)
        self._accessories(head, spine, neck, hat_parent=follow)
        # bras
        for side, s in (("L", 1), ("R", -1)):
            sh = self._j(f"shoulder_{side}", (s * self.torso_w * 0.92, 0, self.torso_h * 0.82), spine)
            ua = self._j(f"upper_arm_{side}", (0, 0, 0), sh)
            sleeves = d["outfit"]["top"].get("sleeves") or ("long" if top_t in LONG_SLEEVE_TOPS else ("none" if top_t == "tank" else "short"))
            sleeve_upper = m["skin"] if sleeves == "none" else m["top"]
            sleeve_fore = m["top"] if sleeves == "long" else m["skin"]
            lay_t = (d["outfit"].get("layer") or {}).get("type", "none")
            if lay_t in SLEEVED_LAYERS:
                sleeve_upper = sleeve_fore = m["layer"]
            self._mesh(core.ball(f"{self.id}_shoulderball_{side}", (0.062 * self.H,) * 3, sleeve_upper, (0, 0, 0), parent=ua, coll=self.coll, detail=1))
            self._mesh(core.limb(f"{self.id}_upperarm_{side}", 0.055 * self.H, 0.047 * self.H, self.upper, sleeve_upper, parent=ua, coll=self.coll, ink=self.ink))
            el = self._j(f"forearm_{side}", (0, 0, -self.upper), ua)
            self._mesh(core.ball(f"{self.id}_elbow_{side}", (0.048 * self.H,) * 3, sleeve_fore, (0, 0, 0), parent=el, coll=self.coll, detail=1))
            self._mesh(core.limb(f"{self.id}_forearm_{side}", 0.047 * self.H, 0.042 * self.H, self.fore, sleeve_fore, parent=el, coll=self.coll, ink=self.ink))
            hand = self._j(f"hand_{side}", (0, 0, -self.fore), el)
            self._mesh(core.ball(f"{self.id}_hand_{side}", (0.06 * self.H, 0.05 * self.H, 0.065 * self.H), m["skin"], (0, 0, -0.04 * self.H), parent=hand, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.ball(f"{self.id}_thumb_{side}", (0.022 * self.H, 0.022 * self.H, 0.035 * self.H), m["skin"], (-s * 0.0, -0.045 * self.H, -0.02 * self.H), parent=hand, coll=self.coll, detail=1))
        # jambes
        for side, s in (("L", 1), ("R", -1)):
            th = self._j(f"thigh_{side}", (s * self.torso_w * 0.45, 0, 0), hips)
            thigh_mat = m["bottom"] if bot_t in ("pants", "jeans", "shorts") else m["skin"]
            shin_mat = m["bottom"] if bot_t in ("pants", "jeans") else m["skin"]
            self._mesh(core.limb(f"{self.id}_thigh_{side}", 0.075 * self.H, 0.06 * self.H, self.thigh, thigh_mat, parent=th, coll=self.coll, ink=self.ink))
            kn = self._j(f"shin_{side}", (0, 0, -self.thigh), th)
            self._mesh(core.ball(f"{self.id}_knee_{side}", (0.062 * self.H,) * 3, shin_mat, (0, 0, 0), parent=kn, coll=self.coll, detail=1))
            self._mesh(core.limb(f"{self.id}_shin_{side}", 0.06 * self.H, 0.05 * self.H, self.shin, shin_mat, parent=kn, coll=self.coll, ink=self.ink))
            ft = self._j(f"foot_{side}", (0, 0, -self.shin), kn)
            self._shoe(ft, side, shin_mat)
        self._late_accessories(spine, hips)
        # pose de repos
        for side, s in (("L", 1), ("R", -1)):
            self.joints[f"upper_arm_{side}"].rotation_euler = (0, -s * D(8), 0)
            self.joints[f"forearm_{side}"].rotation_euler = (D(-10), 0, 0)
        self.rest = {n: (tuple(j.location), tuple(j.rotation_euler), tuple(j.scale)) for n, j in self.joints.items()}

    def _face(self, head):
        d, m, r = self.d, self.m, self.head_r
        es = d["eyes"].get("size", 1.0)
        sp = d["eyes"].get("spacing", 1.0)
        er = r * 0.23 * es
        for side, s in (("L", 1), ("R", -1)):
            eye = core.empty(f"{self.id}__eye_{side}", (s * r * 0.36 * sp, -r * 0.83, r * 0.16), head, self.coll)
            self.face[f"eye_{side}"] = eye
            self._mesh(core.ball(f"{self.id}_sclera_{side}", (er, er * 0.7, er * 1.12), m["white"], (0, 0, 0), parent=eye, coll=self.coll, ink=r * 0.025, detail=2, smooth=True))
            pup = core.empty(f"{self.id}__pupil_{side}", (0, -er * 0.62, 0), eye, self.coll)
            self.face[f"pupil_{side}"] = pup
            self._mesh(core.ball(f"{self.id}_iris_{side}", (er * 0.5, er * 0.3, er * 0.55), m["iris"], (0, 0, 0), parent=pup, coll=self.coll, detail=2, smooth=True))
            self._mesh(core.ball(f"{self.id}_shine_{side}", (er * 0.14,) * 3, m["shine"], (er * 0.18, -er * 0.24, er * 0.22), parent=pup, coll=self.coll, detail=1))
            bt = d["brows"].get("thickness", 1.0)
            brow = core.empty(f"{self.id}__brow_{side}", (s * r * 0.36 * sp, -r * 0.93, r * 0.50), head, self.coll)
            self.face[f"brow_{side}"] = brow
            self._mesh(core.box(f"{self.id}_browbar_{side}", (r * 0.42, r * 0.07, r * 0.075 * bt), m["brow"], (0, 0, 0), parent=brow, coll=self.coll, bevel=r * 0.01))
            blush = core.ball(f"{self.id}_blush_{side}", (r * 0.17, r * 0.03, r * 0.09), m["blush"], (s * r * 0.55, -r * 0.82, -r * 0.18), parent=head, coll=self.coll, detail=1)
            blush.scale = (0.001,) * 3
            self.face[f"blush_{side}"] = blush
            tear = core.ball(f"{self.id}_tear_{side}", (r * 0.06, r * 0.04, r * 0.12), m["tear"], (s * r * 0.36 * sp, -r * 0.98, -r * 0.12), parent=head, coll=self.coll, detail=1)
            tear.scale = (0.001,) * 3
            self.face[f"tear_{side}"] = tear
        # nez
        n = d["nose"]
        ns = n.get("size", 1.0) * r
        shape = n.get("shape", "round")
        nloc = (0, -r * 0.97, -r * 0.06)
        if shape == "round":
            self._mesh(core.ball(f"{self.id}_nose", (ns * 0.17, ns * 0.15, ns * 0.15), m["skin"], nloc, parent=head, coll=self.coll, ink=r * 0.02, detail=1))
        elif shape == "potato":
            self._mesh(core.ball(f"{self.id}_nose", (ns * 0.24, ns * 0.2, ns * 0.2), m["skin"], (0, -r * 0.98, -r * 0.1), parent=head, coll=self.coll, ink=r * 0.02, detail=1))
        elif shape == "long":
            self._mesh(core.cyl(f"{self.id}_nose", ns * 0.11, ns * 0.07, ns * 0.5, m["skin"], (0, -r * 1.12, -r * 0.08), (D(95), 0, 0), parent=head, coll=self.coll, ink=r * 0.02, seg=6))
        else:
            self._mesh(core.cyl(f"{self.id}_nose", ns * 0.12, 0.0, ns * 0.35, m["skin"], (0, -r * 1.08, -r * 0.05), (D(100), 0, 0), parent=head, coll=self.coll, ink=r * 0.02, seg=5))
        # bouches (une seule visible à la fois : échelle 1 / 0.001 en interpolation constante)
        mw = d["mouth"].get("width", 1.0) * r
        mouth = core.empty(f"{self.id}__mouth", (0, -r * 0.90, -r * 0.40), head, self.coll)
        self.face["mouth"] = mouth
        shapes = {}
        shapes["line"] = core.arc_strip(f"{self.id}_m_line", mw * 0.32, 60, r * 0.022, r * 0.02, m["mouth"], parent=mouth, coll=self.coll, bend=0.0)
        shapes["smile"] = core.arc_strip(f"{self.id}_m_smile", mw * 0.34, 100, r * 0.026, r * 0.02, m["mouth"], parent=mouth, coll=self.coll, bend=1.0)
        shapes["frown"] = core.arc_strip(f"{self.id}_m_frown", mw * 0.30, 90, r * 0.026, r * 0.02, m["mouth"], (0, 0, r * 0.06), parent=mouth, coll=self.coll, bend=-1.0)
        shapes["smirk"] = core.arc_strip(f"{self.id}_m_smirk", mw * 0.3, 70, r * 0.024, r * 0.02, m["mouth"], (mw * 0.05, 0, 0), (0, D(-14), 0), parent=mouth, coll=self.coll, bend=0.7)
        o_ = core.empty(f"{self.id}__m_open_o", (0, 0, 0), mouth, self.coll)
        core.ball(f"{self.id}_m_o", (mw * 0.12, r * 0.05, mw * 0.15), m["mouth"], (0, 0, 0), parent=o_, coll=self.coll, detail=2, smooth=True)
        shapes["open_o"] = o_
        w_ = core.empty(f"{self.id}__m_open_wide", (0, 0, 0), mouth, self.coll)
        core.ball(f"{self.id}_m_wide", (mw * 0.30, r * 0.05, mw * 0.2), m["mouth"], (0, 0, -r * 0.02), parent=w_, coll=self.coll, detail=2, smooth=True)
        core.ball(f"{self.id}_m_tongue", (mw * 0.16, r * 0.04, mw * 0.07), m["tongue"], (0, -r * 0.02, -r * 0.1), parent=w_, coll=self.coll, detail=1)
        shapes["open_wide"] = w_
        g_ = core.empty(f"{self.id}__m_grin", (0, 0, 0), mouth, self.coll)
        core.uvball(f"{self.id}_m_grinbowl", (mw * 0.36, r * 0.05, mw * 0.2), m["mouth"], (0, 0, r * 0.03), (D(180), 0, 0), parent=g_, coll=self.coll, seg=12, rings=8, zmin=0.0)
        core.box(f"{self.id}_m_teeth", (mw * 0.6, r * 0.03, r * 0.05), m["teeth"], (0, -r * 0.035, r * 0.0), parent=g_, coll=self.coll)
        shapes["grin"] = g_
        a_ = core.empty(f"{self.id}__m_talk_a", (0, 0, 0), mouth, self.coll)
        core.ball(f"{self.id}_m_ta", (mw * 0.22, r * 0.05, mw * 0.14), m["mouth"], (0, 0, -r * 0.01), parent=a_, coll=self.coll, detail=2, smooth=True)
        core.ball(f"{self.id}_m_tat", (mw * 0.12, r * 0.04, mw * 0.05), m["tongue"], (0, -r * 0.02, -r * 0.07), parent=a_, coll=self.coll, detail=1)
        shapes["talk_a"] = a_
        b_ = core.empty(f"{self.id}__m_talk_b", (0, 0, 0), mouth, self.coll)
        core.ball(f"{self.id}_m_tb", (mw * 0.17, r * 0.05, mw * 0.07), m["mouth"], (0, 0, 0), parent=b_, coll=self.coll, detail=2, smooth=True)
        shapes["talk_b"] = b_
        for k, o in shapes.items():
            o.scale = (1, 1, 1) if k == "line" else (0.001, 0.001, 0.001)
        self.face["mouths"] = shapes

    def _hair(self, head):
        d, m, r = self.d, self.m, self.head_r
        st = d["hair"]["style"]
        if st == "none":
            return
        if {"beanie", "top_hat", "chef_hat"} & set(d.get("accessories", [])) and st in ("spiky", "curly", "mohawk", "bun"):
            st = "short"   # chapeau couvrant : les mèches traverseraient le tissu

        def cap(name, zmin=0.18, sc=1.07, back=0.08):
            return self._mesh(core.uvball(f"{self.id}_{name}", (r * sc, r * sc * 0.97, r * sc), m["hair"], (0, r * back, r * 0.02), parent=head, coll=self.coll, ink=self.ink, seg=12, rings=8, zmin=zmin, smooth=False))
        if st in ("short", "bun", "long"):
            cap("hair_cap")
        if st == "bowl":
            cap("hair_bowl", zmin=0.05, sc=1.12, back=0.05)
        if st == "spiky":
            cap("hair_cap", zmin=0.3)
            for i in range(9):
                a = 2 * math.pi * i / 9
                tilt = D(35)
                self._mesh(core.cyl(f"{self.id}_spike{i}", r * 0.2, 0.0, r * 0.65, m["hair"], (math.cos(a) * r * 0.45, math.sin(a) * r * 0.45 + r * 0.05, r * 0.85),
                                    (-math.sin(a) * tilt, math.cos(a) * tilt, 0), parent=head, coll=self.coll, seg=5, ink=self.ink * 0.6))
        if st == "mohawk":
            for i in range(6):
                y = -r * 0.55 + i * r * 0.25
                z = math.sqrt(max(r * r - y * y, 0)) * 0.98
                self._mesh(core.cyl(f"{self.id}_mohawk{i}", r * 0.15, 0.0, r * 0.6, m["hair"], (0, y, z + r * 0.15), (D(-15 + i * 8), 0, 0), parent=head, coll=self.coll, seg=4, ink=self.ink * 0.6))
        if st == "bun":
            self._mesh(core.ball(f"{self.id}_bun", (r * 0.32,) * 3, m["hair"], (0, r * 0.45, r * 0.9), parent=head, coll=self.coll, ink=self.ink, detail=1))
        if st == "long":
            self._mesh(core.box(f"{self.id}_hair_back", (r * 1.9, r * 0.35, r * 1.7), m["hair"], (0, r * 0.62, -r * 0.55), parent=head, coll=self.coll, ink=self.ink, bevel=r * 0.08))
        if st == "curly":
            for i in range(16):
                a = 2 * math.pi * i / 16
                h = 0.35 + 0.45 * (i % 3) / 2
                rr = math.sqrt(max(1 - h * h, 0)) * r
                self._mesh(core.ball(f"{self.id}_curl{i}", (r * 0.3,) * 3, m["hair"], (math.cos(a) * rr, math.sin(a) * rr + r * 0.1, h * r + r * 0.1), parent=head, coll=self.coll, detail=1, ink=self.ink * 0.5))

    def _accessories(self, head, spine, neck, hat_parent=None):
        d, m, r = self.d, self.m, self.head_r
        hat = hat_parent or head
        acc = set(d.get("accessories", []))
        if "cap" in acc:
            self._mesh(core.uvball(f"{self.id}_cap", (r * 1.1, r * 1.08, r * 1.0), m["accent"], (0, r * 0.06, r * 0.2), parent=hat, coll=self.coll, ink=self.ink, seg=12, rings=8, zmin=0.38, smooth=False))
            self._mesh(core.box(f"{self.id}_visor", (r * 1.0, r * 0.65, r * 0.05), m["accent"], (0, -r * 0.9, r * 0.66), (D(-12), 0, 0), parent=hat, coll=self.coll, ink=self.ink * 0.6))
        if "glasses" in acc:
            for s in (1, -1):
                self._mesh(core.torus(f"{self.id}_glass{s}", r * 0.24, r * 0.025, m["dark"], (s * r * 0.36, -r * 1.07, r * 0.16), (D(90), 0, 0), parent=head, coll=self.coll))
            self._mesh(core.box(f"{self.id}_bridge", (r * 0.25, r * 0.03, r * 0.03), m["dark"], (0, -r * 1.08, r * 0.2), parent=head, coll=self.coll))
        if "sunglasses" in acc:
            for s in (1, -1):
                self._mesh(core.box(f"{self.id}_shade{s}", (r * 0.42, r * 0.05, r * 0.26), m["dark"], (s * r * 0.36, -r * 1.08, r * 0.16), parent=head, coll=self.coll, bevel=r * 0.03))
            self._mesh(core.box(f"{self.id}_sbridge", (r * 0.3, r * 0.04, r * 0.05), m["dark"], (0, -r * 1.08, r * 0.24), parent=head, coll=self.coll))
        if "mustache" in acc:
            for s in (1, -1):
                self._mesh(core.ball(f"{self.id}_stache{s}", (r * 0.22, r * 0.08, r * 0.08), m["hair"], (s * r * 0.17, -r * 0.97, -r * 0.24), (0, s * D(-15), 0), parent=head, coll=self.coll, detail=1))
        if "beard" in acc:
            self._mesh(core.uvball(f"{self.id}_beard", (r * 0.75, r * 0.6, r * 0.55), m["hair"], (0, -r * 0.35, -r * 0.55), (D(180), 0, 0), parent=head, coll=self.coll, seg=10, rings=6, zmin=0.0, smooth=False, ink=self.ink))
        if "chef_hat" in acc:
            self._mesh(core.cyl(f"{self.id}_chefband", r * 0.8, r * 0.85, r * 0.5, m["chef"], (0, 0, r * 0.95), parent=hat, coll=self.coll, ink=self.ink, seg=12))
            self._mesh(core.ball(f"{self.id}_chefpuff", (r * 1.0, r * 1.0, r * 0.6), m["chef"], (0, 0, r * 1.4), parent=hat, coll=self.coll, ink=self.ink, detail=2))
        if "beanie" in acc:
            bm = self.acc_mat("beanie")
            self._mesh(core.uvball(f"{self.id}_beanie", (r * 1.12, r * 1.1, r * 1.08), bm, (0, r * 0.04, r * 0.12), parent=hat, coll=self.coll, ink=self.ink, seg=12, rings=8, zmin=0.25, smooth=False))
            self._mesh(core.torus(f"{self.id}_beanie_fold", r * 1.06, r * 0.1, bm, (0, r * 0.04, r * 0.36), parent=hat, coll=self.coll))
            self._mesh(core.ball(f"{self.id}_pompom", (r * 0.2,) * 3, m["white"], (0, r * 0.05, r * 1.22), parent=hat, coll=self.coll, detail=1))
        if "top_hat" in acc:
            hm = self.acc_mat("top_hat", "#1A1A1A")
            self._mesh(core.cyl(f"{self.id}_hat_brim", r * 1.3, r * 1.3, r * 0.06, hm, (0, 0, r * 0.8), parent=hat, coll=self.coll, ink=self.ink * 0.6, seg=14))
            self._mesh(core.cyl(f"{self.id}_hat_crown", r * 0.78, r * 0.82, r * 1.05, hm, (0, 0, r * 1.33), parent=hat, coll=self.coll, ink=self.ink, seg=14))
            self._mesh(core.cyl(f"{self.id}_hat_band", r * 0.83, r * 0.83, r * 0.16, m["accent"], (0, 0, r * 0.94), parent=hat, coll=self.coll, seg=14))
        if "headphones" in acc:
            hp = self.acc_mat("headphones", "#2B2B2B")
            for i in range(9):   # arceau (demi-cercle au-dessus de la tête)
                a = math.pi * i / 8
                self._mesh(core.ball(f"{self.id}_hp_arc{i}", (r * 0.07,) * 3, hp, (math.cos(a) * r * 1.1, 0, math.sin(a) * r * 1.1 + r * 0.1), parent=hat, coll=self.coll, detail=1))
            for s in (1, -1):
                self._mesh(core.cyl(f"{self.id}_hp_cup{s}", r * 0.3, r * 0.3, r * 0.18, hp, (s * r * 1.08, 0, 0.0), (0, D(90), 0), parent=hat, coll=self.coll, ink=self.ink * 0.5, seg=12))
        if "bandana" in acc:
            bd = self.acc_mat("bandana")
            self._mesh(core.torus(f"{self.id}_bandana", r * 1.01, r * 0.08, bd, (0, 0, r * 0.42), (D(-6), 0, 0), parent=hat, coll=self.coll))
            self._mesh(core.ball(f"{self.id}_bandana_knot", (r * 0.13,) * 3, bd, (0, r * 1.02, r * 0.4), parent=hat, coll=self.coll, detail=1))
        if "headband" in acc:
            self._mesh(core.torus(f"{self.id}_headband", r * 1.0, r * 0.06, m["accent"], (0, 0, r * 0.45), parent=hat, coll=self.coll))
        if "earrings" in acc:
            for s in (1, -1):
                self._mesh(core.ball(f"{self.id}_earring{s}", (r * 0.06,) * 3, m["gold"], (s * r * 1.0, -r * 0.02, -r * 0.25), parent=head, coll=self.coll, detail=1))
        if "crown" in acc:
            self._mesh(core.cyl(f"{self.id}_crownband", r * 0.62, r * 0.66, r * 0.2, m["gold"], (0, 0, r * 0.98), parent=hat, coll=self.coll, ink=self.ink, seg=10))
            for i in range(5):
                a = 2 * math.pi * i / 5
                self._mesh(core.cyl(f"{self.id}_crownspike{i}", r * 0.1, 0.0, r * 0.3, m["gold"], (math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, r * 1.2), parent=hat, coll=self.coll, seg=4))
        if "tie" in acc or d["outfit"]["top"]["type"] == "suit":
            self._mesh(core.box(f"{self.id}_tie", (self.torso_w * 0.22, 0.012, self.torso_h * 0.55), self.acc_mat("tie"), (0, self.front_y(0.004), self.torso_h * 0.62), (D(6), 0, 0), parent=spine, coll=self.coll, ink=self.ink * 0.5))
        if "bowtie" in acc:
            for s in (1, -1):
                self._mesh(core.cyl(f"{self.id}_bow{s}", r * 0.12, 0.0, r * 0.22, m["accent"], (s * r * 0.1, -0.05 * self.H, 0.0), (0, D(90) * s, 0), parent=neck, coll=self.coll, seg=4))

    # ---------------------------------------------------------------- garde-robe v2
    def front_y(self, extra=0.0):
        """Devant du buste (y négatif), en tenant compte du ventre et d'une veste/tablier par-dessus."""
        lay = (self.d["outfit"].get("layer") or {}).get("type", "none")
        k = {"none": 1.0, "apron": 1.0, "puffer": 1.16, "leather_jacket": 1.08}.get(lay, 1.07)
        belly = self.d["body"].get("belly", 0.2)
        body = max(1.0, 0.8 + 0.95 * belly) if belly > 0.05 else 1.0
        return -(self.torso_d * max(k, body * (1.04 if lay not in ("none",) else 1.0)) + 0.006 + extra)

    def _top_details(self, spine, hips, top_t):
        d, m = self.d, self.m
        top = d["outfit"]["top"]
        H, tw, td, th = self.H, self.torso_w, self.torso_d, self.torso_h
        trim = core.toon_mat(f"{self.id}_trim", top.get("accent", "#F5F5F5"), emission=0.3)
        rib = core.toon_mat(f"{self.id}_rib", _shade_hex(top["color"], 0.78), emission=0.3)
        if top.get("collar", top_t in ("polo", "shirt")):
            c = self._mesh(core.torus(f"{self.id}_collar", 0.062 * H, 0.02 * H, trim if top_t == "shirt" else m["top"], (0, -td * 0.1, th * 0.97), (D(12), 0, 0), parent=spine, coll=self.coll, ink=self.ink * 0.5))
            c.scale = (1.0, 0.9, 0.6)
        if top_t == "sweater":
            hem = self._mesh(core.torus(f"{self.id}_hem", tw * 0.92, 0.022 * H, rib, (0, 0, th * 0.06), parent=spine, coll=self.coll))
            hem.scale.y = td / tw
            self._mesh(core.torus(f"{self.id}_neckrib", 0.058 * H, 0.016 * H, rib, (0, 0, th * 0.98), parent=spine, coll=self.coll))
        if top_t == "jersey":
            for s_ in (1, -1):   # bandes sur les épaules
                self._mesh(core.box(f"{self.id}_jstripe{s_}", (0.03 * H, td * 1.6, 0.02 * H), trim, (s_ * tw * 0.6, 0, th * 0.93), parent=spine, coll=self.coll))
        if top.get("pocket"):
            self._mesh(core.box(f"{self.id}_pocket", (tw * 0.32, 0.01, th * 0.16), trim, (tw * 0.42, self.front_y(-0.004), th * 0.66), parent=spine, coll=self.coll, ink=self.ink * 0.3))
        txt = top.get("print") or ("10" if top_t == "jersey" else "")
        txt = "".join(ch for ch in str(txt) if ord(ch) < 0x2600)[:12]
        if txt:
            size = min(th * 0.24, tw * 1.7 / max(2, len(txt)) * 1.25)
            try:
                core.text_obj(f"{self.id}_print", txt, size, m["print"], (0, self.front_y(0.012), th * 0.6), (D(90), 0, 0), parent=spine, coll=self.coll, extrude=0.004)
            except Exception:
                pass

    def _layer(self, spine, hips):
        lay = self.d["outfit"].get("layer") or {}
        t = lay.get("type", "none")
        if t == "none":
            return
        m, H = self.m, self.H
        tw, td, th = self.torso_w, self.torso_d, self.torso_h
        L, trim = m["layer"], m["layer_trim"]
        tz = th * 0.5
        if t == "apron":
            fy = self.front_y(0.004)
            self._mesh(core.box(f"{self.id}_apron_bib", (tw * 1.15, 0.012, th * 0.62), L, (0, fy, th * 0.52), parent=spine, coll=self.coll, ink=self.ink * 0.4))
            self._mesh(core.box(f"{self.id}_apron_skirt", (tw * 1.7, 0.012, 0.26 * H), L, (0, min(fy * 0.92, -td * 1.0), -0.1 * H), parent=hips, coll=self.coll, ink=self.ink * 0.4))
            strap = self._mesh(core.torus(f"{self.id}_apron_strap", 0.07 * H, 0.008 * H, L, (0, -td * 0.3, th * 0.9), (D(30), 0, 0), parent=spine, coll=self.coll))
            band = self._mesh(core.torus(f"{self.id}_apron_band", tw * 0.98, 0.01 * H, L, (0, 0, th * 0.12), parent=spine, coll=self.coll))
            band.scale.y = td / tw
            return
        k = {"puffer": 1.16, "leather_jacket": 1.08}.get(t, 1.07)
        self._mesh(core.ball(f"{self.id}_layer_shell", (tw * k, td * k, th * 0.6 * k), L, (0, 0, tz), parent=spine, coll=self.coll, ink=self.ink))
        belly = self.d["body"].get("belly", 0.2)
        if belly > 0.05:   # le ventre ne traverse pas la veste
            self._mesh(core.ball(f"{self.id}_layer_belly", (tw * 0.85 * k, td * (0.8 + belly * 0.6) * k, th * 0.38 * k), L,
                                 (0, -td * belly * 0.35, tz * 0.75), parent=spine, coll=self.coll))
        open_front = t in ("jacket", "blazer", "lab_coat", "vest", "cardigan")
        if open_front:   # veste ouverte : on voit le haut entre les deux pans
            self._mesh(core.box(f"{self.id}_layer_open", (tw * 0.46, 0.01, th * 0.86), m["top"], (0, -td * k - 0.002, tz + th * 0.06), parent=spine, coll=self.coll))
        if t in ("blazer", "lab_coat", "jacket", "leather_jacket"):
            for s_ in (1, -1):   # revers / col
                lap = self._mesh(core.box(f"{self.id}_lapel{s_}", (tw * 0.18, 0.014, th * 0.42), trim if t == "blazer" else L, (s_ * tw * 0.3, -td * k - 0.006, th * 0.72), (0, s_ * D(18), 0), parent=spine, coll=self.coll, ink=self.ink * 0.4))
        if t == "leather_jacket":
            self._mesh(core.box(f"{self.id}_zip", (0.012 * H, 0.01, th * 0.8), core.toon_mat("zip_metal", "#C9C9C9", rough=0.3, metallic=0.6), (tw * 0.1, -td * k - 0.004, tz), parent=spine, coll=self.coll))
        if t == "cardigan":
            for i in range(3):
                self._mesh(core.ball(f"{self.id}_button{i}", (0.012 * H,) * 3, trim, (tw * 0.26, -td * k - 0.006, th * (0.35 + 0.18 * i)), parent=spine, coll=self.coll, detail=1))
        if t == "puffer":
            for i in range(3):
                b = self._mesh(core.torus(f"{self.id}_puff{i}", tw * k * 0.98, 0.012 * H, trim, (0, 0, th * (0.25 + 0.22 * i)), parent=spine, coll=self.coll))
                b.scale.y = td / tw
        if t == "lab_coat":
            self._mesh(core.cyl(f"{self.id}_coat_tails", tw * 1.12, tw * 1.28, 0.26 * H, L, (0, 0, -0.12 * H), parent=hips, coll=self.coll, ink=self.ink, seg=12))
            self._mesh(core.box(f"{self.id}_coat_pocket", (tw * 0.3, 0.01, th * 0.14), trim, (-tw * 0.45, -td * k - 0.004, th * 0.62), parent=spine, coll=self.coll))

    def _belt(self, hips):
        b = self.d["outfit"]["bottom"].get("belt")
        if not b:
            return
        H, tw, td = self.H, self.torso_w, self.torso_d
        belt = self._mesh(core.torus(f"{self.id}_belt", tw * 0.97, 0.016 * H, core.toon_mat(f"{self.id}_beltm", b, emission=0.2), (0, 0, 0.08 * H), parent=hips, coll=self.coll))
        belt.scale.y = td / tw
        self._mesh(core.box(f"{self.id}_buckle", (0.045 * H, 0.012, 0.035 * H), self.m["gold"], (0, -td * 0.98, 0.08 * H), parent=hips, coll=self.coll))

    def _shoe(self, ft, side, leg_mat):
        H, fh, m = self.H, self.foot_h, self.m
        t = self.shoe.get("type", "sneakers")
        name = f"{self.id}_shoe_{side}"
        if t == "heels":
            self._mesh(core.ball(name, (0.06 * H, 0.11 * H, fh * 0.6), m["shoes"], (0, -0.05 * H, -fh * 0.1), parent=ft, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.cyl(f"{name}_heel", 0.012 * H, 0.008 * H, fh * 0.9, m["shoes"], (0, 0.03 * H, -fh * 0.5), parent=ft, coll=self.coll, seg=6))
        elif t == "boots":
            self._mesh(core.ball(name, (0.08 * H, 0.135 * H, fh * 0.8), m["shoes"], (0, -0.05 * H, -fh * 0.25), parent=ft, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.cyl(f"{name}_shaft", 0.068 * H, 0.072 * H, 0.13 * H, m["shoes"], (0, 0, 0.05 * H), parent=ft, coll=self.coll, ink=self.ink, seg=8))
        elif t == "sandals":
            self._mesh(core.ball(f"{name}_foot", (0.065 * H, 0.12 * H, fh * 0.55), m["skin"], (0, -0.05 * H, -fh * 0.15), parent=ft, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.box(f"{name}_sole", (0.14 * H, 0.25 * H, 0.018 * H), m["shoes"], (0, -0.05 * H, -fh * 0.62), parent=ft, coll=self.coll, bevel=0.005))
            self._mesh(core.torus(f"{name}_strap", 0.05 * H, 0.008 * H, m["shoes"], (0, -0.07 * H, -fh * 0.3), (D(90), 0, 0), parent=ft, coll=self.coll))
        elif t == "slippers":
            self._mesh(core.ball(name, (0.09 * H, 0.15 * H, fh * 0.85), m["shoes"], (0, -0.05 * H, -fh * 0.2), parent=ft, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.ball(f"{name}_pom", (0.035 * H,) * 3, m["sole"], (0, -0.17 * H, fh * 0.15), parent=ft, coll=self.coll, detail=1))
        elif t == "dress_shoes":
            self._mesh(core.ball(name, (0.068 * H, 0.15 * H, fh * 0.62), m["shoes"], (0, -0.06 * H, -fh * 0.3), parent=ft, coll=self.coll, ink=self.ink, detail=1))
        else:   # sneakers
            self._mesh(core.ball(name, (0.075 * H, 0.13 * H, fh * 0.75), m["shoes"], (0, -0.05 * H, -fh * 0.25), parent=ft, coll=self.coll, ink=self.ink, detail=1))
            self._mesh(core.box(f"{name}_sole", (0.15 * H, 0.265 * H, 0.022 * H), m["sole"], (0, -0.05 * H, -fh * 0.82), parent=ft, coll=self.coll, bevel=0.006))

    def _late_accessories(self, spine, hips):
        acc = set(self.d.get("accessories", []))
        H, r, tw, td, th = self.H, self.head_r, self.torso_w, self.torso_d, self.torso_h
        neck = self.joints["neck"]
        if "scarf" in acc:
            sm = self.acc_mat("scarf")
            sc_ = self._mesh(core.torus(f"{self.id}_scarf", 0.075 * H, 0.032 * H, sm, (0, 0, 0.0), parent=neck, coll=self.coll, ink=self.ink * 0.6))
            self._mesh(core.box(f"{self.id}_scarf_tail", (0.06 * H, 0.02, 0.2 * H), sm, (tw * 0.3, self.front_y(0.01), th * 0.72), (D(6), 0, D(-6)), parent=spine, coll=self.coll, ink=self.ink * 0.5))
        if "necklace" in acc or "gold_chain" in acc:
            gold = "gold_chain" in acc
            nm = self.acc_mat("gold_chain" if gold else "necklace", "#F4C430" if gold else None)
            nk = self._mesh(core.torus(f"{self.id}_necklace", (0.1 if gold else 0.085) * H, (0.012 if gold else 0.006) * H, nm, (0, -td * 0.35, th * 0.9), (D(32), 0, 0), parent=spine, coll=self.coll))
            self._mesh(core.ball(f"{self.id}_pendant", (0.02 * H,) * 3, nm, (0, self.front_y(0.004), th * 0.72), parent=spine, coll=self.coll, detail=1))
        if "watch" in acc:
            fl = self.joints["forearm_L"]
            wm = self.acc_mat("watch", "#2B2B2B")
            self._mesh(core.torus(f"{self.id}_watch", 0.046 * self.H, 0.012 * self.H, wm, (0, 0, -self.fore * 0.82), parent=fl, coll=self.coll))
            self._mesh(core.box(f"{self.id}_watchface", (0.035 * H, 0.012, 0.035 * H), self.m["gold"], (0, -0.046 * H, -self.fore * 0.82), parent=fl, coll=self.coll))
        if "backpack" in acc:
            bm = self.acc_mat("backpack")
            self._mesh(core.box(f"{self.id}_backpack", (tw * 1.45, td * 0.9, th * 0.72), bm, (0, td * 1.45, th * 0.5), parent=spine, coll=self.coll, ink=self.ink, bevel=0.02))
            for s_ in (1, -1):
                self._mesh(core.box(f"{self.id}_bp_strap{s_}", (0.028 * H, 0.012, th * 0.6), bm, (s_ * tw * 0.5, self.front_y(0.002), th * 0.62), parent=spine, coll=self.coll))
        if "shoulder_bag" in acc:
            bm = self.acc_mat("shoulder_bag")
            self._mesh(core.box(f"{self.id}_bag_strap", (0.025 * H, 0.012, th * 1.15), bm, (0, self.front_y(0.003), th * 0.55), (0, D(38), 0), parent=spine, coll=self.coll))
            self._mesh(core.box(f"{self.id}_bag", (0.16 * H, 0.06 * H, 0.12 * H), bm, (-tw * 1.12, -td * 0.2, -0.02 * H), parent=hips, coll=self.coll, ink=self.ink, bevel=0.01))
        if "badge" in acc:
            self._mesh(core.box(f"{self.id}_badge", (0.06 * H, 0.01, 0.075 * H), self.acc_mat("badge", "#F4C430"), (-tw * 0.42, self.front_y(0.002), th * 0.66), parent=spine, coll=self.coll, ink=self.ink * 0.3))
        if "flower_pin" in acc:
            fm = self.acc_mat("flower_pin", "#FF5FA2")
            cx, cz, y = tw * 0.42, th * 0.7, self.front_y(0.006)
            self._mesh(core.ball(f"{self.id}_flower_c", (0.015 * H,) * 3, self.m["gold"], (cx, y - 0.004, cz), parent=spine, coll=self.coll, detail=1))
            for i in range(5):
                a = 2 * math.pi * i / 5
                self._mesh(core.ball(f"{self.id}_petal{i}", (0.017 * H, 0.008 * H, 0.017 * H), fm, (cx + math.cos(a) * 0.022 * H, y, cz + math.sin(a) * 0.022 * H), parent=spine, coll=self.coll, detail=1))

    # ---------------------------------------------------------------- placement / repères
    def place(self, x, y, facing_rad):
        root = self.joints["root"]
        root.location = (x, y, 0)
        root.rotation_euler = (0, 0, facing_rad)

    def landmarks_world(self):
        """Points clés (monde) utilisés par la caméra et les contrôles."""
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
        zs = [(o.matrix_world @ Vector(c)).z for o in self.meshes if o.parent is not None and (o.parent == hj or o.parent.parent == hj) for c in o.bound_box]
        return max(zs) if zs else 0.0

    def facing_vector(self):
        rz = self.joints["root"].matrix_world.to_euler().z
        return Vector((math.sin(rz), -math.cos(rz), 0))
