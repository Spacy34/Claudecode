"""Bibliothèque de mouvements paramétrables et combinables.

Principe : chaque action écrit des clés dans un `Animator` (stockage intermédiaire indépendant de l'API
d'animation de Blender, qui change entre 4.x et 5.x). Une action « réclame » ses canaux sur sa fenêtre
temporelle : les clés antérieures (idle) y sont effacées, ce qui rend les actions combinables sans conflit.
Les clés sont ensuite écrites via `keyframe_insert` (API stable).

Conventions (personnage regardant -Y, côté gauche = +X) :
- chaînes « pendantes » (bras, jambes) : avancer = rotation X négative ;
- chaînes « montantes » (colonne, tête) : pencher en avant = rotation X positive ;
- abduction du bras gauche = rotation Y négative, du bras droit = positive.
"""
import math
import random
import bpy
from mathutils import Vector

D = math.radians


class Animator:
    def __init__(self, fps):
        self.fps = fps
        self.tracks = {}   # (obj_name, path, idx) -> {frame: (value, interp)}
        self.objs = {}

    def _t(self, obj, path, idx):
        self.objs[obj.name] = obj
        return self.tracks.setdefault((obj.name, path, idx), {})

    def key(self, obj, path, idx, f, v, interp='BEZIER'):
        self._t(obj, path, idx)[int(round(f))] = (float(v), interp)

    def clear(self, obj, path, idx, f0, f1):
        t = self._t(obj, path, idx)
        for f in [f for f in t if f0 <= f <= f1]:
            del t[f]

    def rest_value(self, obj, path, idx):
        return getattr(obj, path)[idx]

    def value_at(self, obj, path, idx, f):
        t = self._t(obj, path, idx)
        if not t:
            return self.rest_value(obj, path, idx)
        fs = sorted(t)
        if f <= fs[0]:
            return t[fs[0]][0]
        if f >= fs[-1]:
            return t[fs[-1]][0]
        for a, b in zip(fs, fs[1:]):
            if a <= f <= b:
                va, ia = t[a]
                if ia == 'CONSTANT':
                    return va
                u = (f - a) / float(b - a)
                return va + (t[b][0] - va) * u
        return t[fs[-1]][0]

    def apply(self):
        prefs = bpy.context.preferences.edit
        old = (prefs.keyframe_new_interpolation_type, prefs.keyframe_new_handle_type)
        prefs.keyframe_new_handle_type = 'AUTO_CLAMPED'
        try:
            for (oname, path, idx), keys in self.tracks.items():
                obj = self.objs[oname]
                for f in sorted(keys):
                    v, interp = keys[f]
                    prefs.keyframe_new_interpolation_type = interp
                    prop = getattr(obj, path)
                    prop[idx] = v
                    obj.keyframe_insert(data_path=path, index=idx, frame=f)
        finally:
            prefs.keyframe_new_interpolation_type, prefs.keyframe_new_handle_type = old


# --------------------------------------------------------------------- poses sémantiques
REST = dict(armL=(0, 8, 10), armR=(0, 8, 10), legL=(0, 0), legR=(0, 0), spine=(0, 0, 0), head=(0, 0, 0), hip_dz=0.0, shrug=0.0)


def P(**k):
    d = dict(REST)
    d.update(k)
    return d


POSES = {
    "rest": P(),
    "crouch": P(armL=(-35, 15, 20), armR=(-35, 15, 20), legL=(45, 85), legR=(45, 85), spine=(22, 0, 0), hip_dz=-0.13),
    "air": P(armL=(30, 70, 20), armR=(30, 70, 20), legL=(15, 35), legR=(-10, 25), spine=(-6, 0, 0), head=(-8, 0, 0)),
    "shocked": P(armL=(25, 75, 70), armR=(25, 75, 70), legL=(8, 5), legR=(-8, 5), spine=(-12, 0, 0), head=(-12, 0, 0), shrug=0.04),
    "shrug": P(armL=(15, 40, 85), armR=(15, 40, 85), spine=(-4, 0, 0), head=(0, 14, 0), shrug=0.05),
    "facepalm": P(armR=(105, 12, 135), spine=(12, 0, 0), head=(26, 0, 0)),
    "point": P(armR=(88, 6, 0), spine=(4, 0, 0)),
    "wave": P(armR=(15, 145, 45), head=(-4, 8, 0)),
    "cower": P(armL=(150, 25, 110), armR=(150, 25, 110), legL=(50, 95), legR=(50, 95), spine=(30, 0, 0), head=(25, 0, 0), hip_dz=-0.16),
    "celebrate": P(armL=(10, 160, 15), armR=(10, 160, 15), head=(-15, 0, 0), spine=(-8, 0, 0)),
    "arms_crossed": P(armL=(65, -12, 125), armR=(60, -12, 125), spine=(-4, 0, 0), head=(-6, 6, 0)),
    "hands_on_hips": P(armL=(-15, 45, 95), armR=(-15, 45, 95), spine=(-5, 0, 0), head=(-5, 0, 0)),
    "lean_in": P(spine=(22, 0, 0), head=(-14, 0, 0), armL=(-20, 12, 30), armR=(-20, 12, 30)),
    "stomp_up": P(legL=(55, 70), armL=(10, 30, 100), armR=(10, 30, 100), spine=(6, 0, 0), head=(8, 0, 0)),
    "throw_back": P(armR=(-60, 30, 60), spine=(-10, 0, 25), legL=(20, 10), legR=(-15, 10)),
    "throw_fwd": P(armR=(120, 10, 0), spine=(18, 0, -20), legL=(25, 20), legR=(-25, 10)),
    "hit": P(spine=(-25, 0, 0), head=(-25, 0, 0), armL=(20, 60, 30), armR=(20, 60, 30), legL=(-15, 10), legR=(10, 20)),
    "sit": P(legL=(88, 90), legR=(88, 90), armL=(35, 12, 35), armR=(35, 12, 35)),
    "lying": P(armL=(0, 75, 20), armR=(0, 75, 20), legL=(5, 10), legR=(-5, 10), head=(-10, 0, 0)),
    "talk_a": P(armR=(35, 14, 70), armL=(8, 12, 20), head=(-3, 4, 0)),
    "talk_b": P(armR=(25, 25, 55), armL=(30, 18, 60), head=(3, -4, 0)),
}


EXPRESSIONS = {
    #            eye_sq pupil  browL_up browR_up inL  inR   mouth       blush tears
    "neutral":   (1.00, 1.00, 0.00, 0.00, 0, 0, "line", 0, 0),
    "happy":     (0.75, 1.00, 0.05, 0.05, 10, 10, "smile", 0, 0),
    "laugh":     (0.20, 1.00, 0.07, 0.07, 18, 18, "open_wide", 0, 0),
    "sad":       (0.85, 1.05, 0.02, 0.02, 28, 28, "frown", 0, 0),
    "angry":     (0.70, 0.80, -0.05, -0.05, -28, -28, "frown", 0, 0),
    "shocked":   (1.30, 0.50, 0.14, 0.14, 8, 8, "open_o", 0, 0),
    "scared":    (1.25, 0.45, 0.10, 0.10, 28, 28, "open_wide", 0, 0),
    "smug":      (0.55, 1.00, 0.10, -0.02, -6, -12, "smirk", 0, 0),
    "disgusted": (0.55, 1.00, -0.04, 0.03, -16, -8, "frown", 0, 0),
    "confused":  (1.05, 0.90, 0.11, -0.03, 12, -10, "smirk", 0, 0),
    "deadpan":   (0.42, 1.00, -0.01, -0.01, 0, 0, "line", 0, 0),
    "crying":    (0.25, 1.00, 0.03, 0.03, 32, 32, "open_wide", 0, 1),
    "evil_grin": (0.55, 0.75, -0.04, -0.04, -32, -32, "grin", 0, 0),
    "love":      (0.65, 1.25, 0.06, 0.06, 15, 15, "smile", 1, 0),
}


class CharAnim:
    """Pilote d'animation d'un personnage : poses, déplacement, visage, parole."""

    def __init__(self, anim, ch, frames, seed=0):
        self.a = anim
        self.c = ch
        self.frames = frames
        self.rng = random.Random(seed)
        self.mouth_base = {}   # frame -> forme de bouche de l'expression active
        self.events = []       # (frame, description) pour le rapport

    # ---------------- bas niveau
    def j(self, n):
        return self.c.joints[n]

    HEAD_LIMITS = {0: (-20.0, 16.0), 1: (-25.0, 25.0), 2: (-75.0, 75.0)}   # au-delà, on ne voit plus le visage

    def rot(self, joint, axis, f, deg, interp='BEZIER'):
        if joint == "head":
            lo, hi = self.HEAD_LIMITS[axis]
            deg = max(lo, min(hi, deg))
        self.a.key(self.j(joint), 'rotation_euler', axis, f, D(deg), interp)

    def pose(self, name_or_dict, f, interp='BEZIER', blend=1.0):
        p = POSES[name_or_dict] if isinstance(name_or_dict, str) else name_or_dict
        r = POSES["rest"]
        mix = (lambda k, i: r[k][i] + (p[k][i] - r[k][i]) * blend)
        for side, s in (("L", 1), ("R", -1)):
            k = "arm" + side
            self.rot(f"upper_arm_{side}", 0, f, -mix(k, 0), interp)
            self.rot(f"upper_arm_{side}", 1, f, -s * mix(k, 1), interp)
            self.rot(f"forearm_{side}", 0, f, -mix(k, 2), interp)
            k = "leg" + side
            self.rot(f"thigh_{side}", 0, f, -mix(k, 0), interp)
            self.rot(f"shin_{side}", 0, f, mix(k, 1), interp)
            sh = self.j(f"shoulder_{side}")
            self.a.key(sh, 'location', 2, f, self.c.rest[f"shoulder_{side}"][0][2] + (r["shrug"] + (p["shrug"] - r["shrug"]) * blend) * self.c.H, interp)
        for i in range(3):
            self.rot("spine", i, f, mix("spine", i), interp)
            self.rot("head", i, f, mix("head", i), interp)
        hz = self.c.hip_z + (r["hip_dz"] + (p["hip_dz"] - r["hip_dz"]) * blend) * self.c.H
        self.a.key(self.j("hips"), 'location', 2, f, hz, interp)

    BODY_JOINTS = ["upper_arm_L", "upper_arm_R", "forearm_L", "forearm_R", "thigh_L", "thigh_R", "shin_L", "shin_R", "spine", "head"]

    def claim(self, f0, f1, joints=None, loc=False):
        for n in joints or self.BODY_JOINTS:
            for i in range(3):
                self.a.clear(self.j(n), 'rotation_euler', i, f0, f1)
        if loc:
            for n in ("hips", "shoulder_L", "shoulder_R"):
                self.a.clear(self.j(n), 'location', 2, f0, f1)

    def hold_current(self, f):
        """Fige la valeur courante (interpolée) de tous les canaux du corps à f : évite les sauts."""
        for n in self.BODY_JOINTS:
            for i in range(3):
                o = self.j(n)
                self.a.key(o, 'rotation_euler', i, f, self.a.value_at(o, 'rotation_euler', i, f))
        for n in ("hips", "shoulder_L", "shoulder_R"):
            o = self.j(n)
            self.a.key(o, 'location', 2, f, self.a.value_at(o, 'location', 2, f))

    def root_xy(self, f):
        o = self.j("root")
        return Vector((self.a.value_at(o, 'location', 0, f), self.a.value_at(o, 'location', 1, f)))

    def root_rz(self, f):
        return self.a.value_at(self.j("root"), 'rotation_euler', 2, f)

    def face_to(self, f, target_xy, frames=6, max_turn=None):
        p = self.root_xy(f)
        d = Vector(target_xy) - p
        if d.length < 1e-3:
            return
        ang = math.atan2(d.x, -d.y)
        cur = self.root_rz(f)
        while ang - cur > math.pi:
            ang -= 2 * math.pi
        while ang - cur < -math.pi:
            ang += 2 * math.pi
        if max_turn is not None:   # geste vers une cible : ne jamais tourner le dos à la caméra
            ang = cur + max(-max_turn, min(max_turn, ang - cur))
        root = self.j("root")
        self.a.key(root, 'rotation_euler', 2, f, cur)
        self.a.key(root, 'rotation_euler', 2, f + frames, ang)

    # ---------------- couches automatiques
    def idle(self, f0, f1, energy=1.0):
        """Respiration, balancement, micro-mouvements de tête : jamais de personnage figé."""
        self.pose("rest", f0)
        period = int(self.a.fps * 1.6)
        f = f0
        k = 0
        while f <= f1:
            ph = math.sin(k * 0.9 + self.rng.random())
            self.rot("spine", 0, f, 1.5 * ph * energy)
            self.rot("spine", 1, f, 1.8 * math.cos(k * 0.7) * energy)
            self.rot("head", 1, f, 3.0 * math.sin(k * 0.6 + 1.3) * energy)
            self.rot("head", 2, f, 4.0 * math.sin(k * 0.45) * energy)
            for side in ("L", "R"):
                s = 1 if side == "L" else -1
                self.rot(f"upper_arm_{side}", 1, f, -s * (8 + 2.5 * ph * energy))
            self.a.key(self.j("hips"), 'location', 2, f, self.c.hip_z + 0.006 * self.c.H * ph * energy)
            f += period // 2
            k += 1

    def blinks(self, f0, f1):
        f = f0 + self.rng.randint(10, 40)
        while f < f1 - 4:
            for side in ("L", "R"):
                e = self.c.face[f"eye_{side}"]
                cur = self.a.value_at(e, 'scale', 2, f - 1) if self.a._t(e, 'scale', 2) else 1.0
                self.a.key(e, 'scale', 2, f - 1, cur)
                self.a.key(e, 'scale', 2, f + 1, 0.08)
                self.a.key(e, 'scale', 2, f + 3, cur)
            f += self.rng.randint(int(self.a.fps * 2.2), int(self.a.fps * 4.5))

    # ---------------- visage
    def expression(self, f, name, intensity=1.0, ramp=3):
        e = EXPRESSIONS[name]
        eye_sq, pup, bl, br, il, ir, mouth, blush, tears = e
        lerp = (lambda a, b: a + (b - a) * min(intensity, 1.5))
        r = self.c.head_r
        fa, fb = f, f + ramp
        for side, up, inner, s in (("L", bl, il, 1), ("R", br, ir, -1)):
            eye, pupil, brow = self.c.face[f"eye_{side}"], self.c.face[f"pupil_{side}"], self.c.face[f"brow_{side}"]
            # le sourcil glisse SUR la surface de la tête (sinon il flotte devant le front quand il monte)
            bz = r * 0.50 + max(-0.08, min(0.14, lerp(0, up))) * r * 1.6
            bx = brow.location.x
            by = -(math.sqrt(max(r * r - bz * bz - bx * bx * 0.6, 0.0)) * 0.97 + r * 0.06)
            for obj, path, idx, val in ((eye, 'scale', 2, lerp(1, eye_sq)), (pupil, 'scale', 0, lerp(1, pup)), (pupil, 'scale', 2, lerp(1, pup)),
                                        (brow, 'location', 2, bz), (brow, 'location', 1, by), (brow, 'rotation_euler', 1, s * D(lerp(0, inner)))):
                self.a.key(obj, path, idx, fa, self.a.value_at(obj, path, idx, fa))
                self.a.key(obj, path, idx, fb, val)
            for part, on in ((f"blush_{side}", blush), (f"tear_{side}", tears)):
                o = self.c.face[part]
                for i in range(3):
                    self.a.key(o, 'scale', i, fb, 1.0 if on else 0.001, 'CONSTANT')
        self.set_mouth(fb, mouth)
        self.mouth_base[fb] = mouth
        self.events.append((f, f"expr:{name}"))

    def set_mouth(self, f, shape):
        for k, o in self.c.face["mouths"].items():
            v = 1.0 if k == shape else 0.001
            for i in range(3):
                self.a.key(o, 'scale', i, f, v, 'CONSTANT')

    def base_mouth_at(self, f):
        cands = [k for k in self.mouth_base if k <= f]
        return self.mouth_base[max(cands)] if cands else "line"

    def talk(self, words):
        """words : liste (f_start, f_end) locales. Ouvre/ferme la bouche par syllabe approximative."""
        alt = 0
        for fs, fe in words:
            n = max(1, int((fe - fs) / 5))
            step = (fe - fs) / float(n)
            for i in range(n):
                a = int(fs + i * step)
                self.set_mouth(a, "talk_a" if alt % 2 == 0 else "talk_b")
                alt += 1
                self.set_mouth(int(a + step * 0.65), "line" if self.base_mouth_at(a) in ("open_o", "open_wide", "grin") else self.base_mouth_at(a))
            self.set_mouth(int(fe), self.base_mouth_at(fe))
            # hochements de tête synchronisés sur les mots
            self.a.key(self.j("head"), 'rotation_euler', 0, fs, D(-3))
            self.a.key(self.j("head"), 'rotation_euler', 0, fs + 3, D(3))

    # ---------------- actions de la bibliothèque
    def do(self, action, f0, dur, intensity=1.0, target=None, world=None):
        fn = getattr(self, "act_" + action, None)
        if fn is None:
            raise ValueError(f"action inconnue {action}")
        self.events.append((f0, f"action:{action}"))
        return fn(f0, dur, intensity, target, world)

    def _hold_pose(self, name, f0, dur, k=1.0, settle=True):
        f1 = f0 + max(dur, 8)
        self.hold_current(f0)
        self.claim(f0 + 1, f1, loc=True)
        self.pose(name, f0 + 5, blend=1.15 * k)    # léger dépassement
        self.pose(name, f0 + 8, blend=1.0 * k)
        if settle:
            self.pose(name, f1 - 6, blend=0.97 * k)
            self.pose("rest", f1)
        return f1

    def act_idle(self, f0, dur, k, target, world):
        self.idle(f0, f0 + dur, energy=k)

    def act_wave(self, f0, dur, k, target, world):
        f1 = self._hold_pose("wave", f0, dur, k)
        f = f0 + 8
        s = 1
        while f < f1 - 8:
            self.rot("upper_arm_R", 1, f, 145 * k + 18 * s)
            self.rot("forearm_R", 0, f, -45 - 20 * s)
            s = -s
            f += 5

    def act_point(self, f0, dur, k, target, world):
        if target is not None:
            self.face_to(f0, target, 5, max_turn=D(50))
        self._hold_pose("point", f0, dur, k)

    def act_shrug(self, f0, dur, k, target, world):
        self._hold_pose("shrug", f0, max(dur, 18), k)

    def act_facepalm(self, f0, dur, k, target, world):
        self._hold_pose("facepalm", f0, max(dur, 24), k)

    def act_arms_crossed(self, f0, dur, k, target, world):
        self._hold_pose("arms_crossed", f0, dur, k)

    def act_hands_on_hips(self, f0, dur, k, target, world):
        self._hold_pose("hands_on_hips", f0, dur, k)

    def act_lean_in(self, f0, dur, k, target, world):
        self._hold_pose("lean_in", f0, dur, k)

    def act_cower(self, f0, dur, k, target, world):
        f1 = self._hold_pose("cower", f0, dur, k)
        for f in range(f0 + 8, f1 - 6, 2):   # tremblement
            self.rot("spine", 2, f, 3 * (1 if (f // 2) % 2 else -1))

    def act_celebrate(self, f0, dur, k, target, world):
        f1 = self._hold_pose("celebrate", f0, dur, k)
        f, s = f0 + 8, 1
        while f < f1 - 6:
            self.rot("upper_arm_L", 1, f, -(160 - 25 * s))
            self.rot("upper_arm_R", 1, f, 160 + 25 * s)
            self.a.key(self.j("hips"), 'location', 2, f, self.c.hip_z + (0.04 if s > 0 else 0) * self.c.H)
            s, f = -s, f + 5

    def act_talk_gesture(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + dur, joints=["upper_arm_L", "upper_arm_R", "forearm_L", "forearm_R"])
        f, i = f0 + 4, 0
        while f < f0 + dur - 6:
            self.pose("talk_a" if i % 2 == 0 else "talk_b", f, blend=k)
            f += self.rng.randint(9, 15)
            i += 1
        self.pose("rest", f0 + dur)

    def act_nod(self, f0, dur, k, target, world):
        for i, f in enumerate(range(f0, f0 + max(dur, 12), 6)):
            self.rot("head", 0, f, (14 if i % 2 else -4) * k)
        self.rot("head", 0, f0 + max(dur, 12) + 4, 0)

    def act_shake_head(self, f0, dur, k, target, world):
        for i, f in enumerate(range(f0, f0 + max(dur, 12), 5)):
            self.rot("head", 2, f, (22 if i % 2 else -22) * k)
        self.rot("head", 2, f0 + max(dur, 12) + 4, 0)

    def act_look_at(self, f0, dur, k, target, world):
        if target is None:
            return
        p = self.root_xy(f0)
        d = Vector(target) - p
        ang = math.atan2(d.x, -d.y) - self.root_rz(f0)
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        if abs(ang) > D(70):
            self.face_to(f0, target, 6)
            ang = 0
        self.a.key(self.j("head"), 'rotation_euler', 2, f0, self.a.value_at(self.j("head"), 'rotation_euler', 2, f0))
        self.a.key(self.j("head"), 'rotation_euler', 2, f0 + 5, ang)
        if dur:
            self.a.key(self.j("head"), 'rotation_euler', 2, f0 + dur, ang)

    def act_turn_to(self, f0, dur, k, target, world):
        if target is not None:
            self.face_to(f0, target, max(4, min(dur or 6, 10)))
            self.a.key(self.j("hips"), 'location', 2, f0 + 3, self.c.hip_z + 0.03 * self.c.H)

    def _jump(self, f0, k, pose_air="air", height=0.35):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + 30, loc=True)
        self.pose("crouch", f0 + 5, blend=0.8)
        self.pose(pose_air, f0 + 9)
        root = self.j("root")
        z = self.a.value_at(root, 'location', 2, f0)
        self.a.key(root, 'location', 2, f0 + 5, z)
        self.a.key(root, 'location', 2, f0 + 13, z + height * k * self.c.H)
        self.a.key(root, 'location', 2, f0 + 21, z, 'LINEAR')
        self.pose("crouch", f0 + 23, blend=0.6)
        self.pose("rest", f0 + 30)
        return f0 + 30

    def act_jump(self, f0, dur, k, target, world):
        self._jump(f0, k)

    def act_shocked_jump(self, f0, dur, k, target, world):
        f1 = self._jump(f0, k * 1.2, "shocked", 0.45)
        if dur and dur > 30:
            self._hold_pose("shocked", f1, dur - 30, k)

    def act_stomp(self, f0, dur, k, target, world):
        f = f0
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + max(dur, 24), loc=True)
        side = "L"
        while f < f0 + max(dur, 24) - 8:
            p = dict(POSES["stomp_up"])
            if side == "R":
                p["legR"], p["legL"] = p["legL"], (0, 0)
            self.pose(p, f + 4, blend=k)
            self.pose("rest", f + 8, interp='LINEAR')
            side = "R" if side == "L" else "L"
            f += 10
        self.pose("rest", f0 + max(dur, 24))

    def act_flail(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + max(dur, 20), loc=False)
        for f in range(f0 + 2, f0 + max(dur, 20) - 4, 3):
            for side, s in (("L", 1), ("R", -1)):
                self.rot(f"upper_arm_{side}", 0, f, self.rng.uniform(-60, 160) * k)
                self.rot(f"upper_arm_{side}", 1, f, -s * self.rng.uniform(20, 140) * k)
                self.rot(f"forearm_{side}", 0, f, -self.rng.uniform(0, 120))
            self.rot("head", 1, f, self.rng.uniform(-15, 15))
        self.pose("rest", f0 + max(dur, 20))

    def act_dance(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + max(dur, 24), loc=True)
        for i, f in enumerate(range(f0 + 4, f0 + max(dur, 24) - 4, 7)):
            s = 1 if i % 2 else -1
            p = P(armL=(40 + 50 * (s > 0), 60, 90), armR=(40 + 50 * (s < 0), 60, 90), spine=(0, 10 * s, 15 * s), head=(0, -12 * s, 0), legL=(15 * s, 20), legR=(-15 * s, 20), hip_dz=-0.03)
            self.pose(p, f, blend=k)
        self.pose("rest", f0 + max(dur, 24))

    def act_take_hit(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + max(dur, 20), loc=True)
        self.pose("hit", f0 + 2, blend=1.2 * k)
        root = self.j("root")
        back = -self.c.facing_vector() * 0.25 * k
        x, y = self.a.value_at(root, 'location', 0, f0), self.a.value_at(root, 'location', 1, f0)
        self.a.key(root, 'location', 0, f0, x)
        self.a.key(root, 'location', 1, f0, y)
        self.a.key(root, 'location', 0, f0 + 6, x + back.x)
        self.a.key(root, 'location', 1, f0 + 6, y + back.y)
        self.pose("rest", f0 + max(dur, 20))

    def _fall(self, f0, k, slip=False):
        root = self.j("root")
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + 10 ** 6, loc=True)
        z0 = self.a.value_at(root, 'location', 2, f0)
        rx0 = self.a.value_at(root, 'rotation_euler', 0, f0)
        self.a.key(root, 'rotation_euler', 0, f0, rx0)
        if slip:
            self.pose(P(legL=(80, 0), legR=(60, 10), armL=(40, 120, 30), armR=(40, 120, 30), spine=(-25, 0, 0)), f0 + 4)
            self.a.key(root, 'location', 2, f0 + 6, z0 + 0.35 * self.c.H)
        else:
            self.pose("hit", f0 + 4)
        self.a.key(root, 'rotation_euler', 0, f0 + 12, D(-88), 'LINEAR')
        self.a.key(root, 'location', 2, f0 + 12, 0.12 * self.c.H * self.c.d["body"]["girth"], 'LINEAR')
        self.a.key(root, 'rotation_euler', 0, f0 + 15, D(-80))
        self.a.key(root, 'rotation_euler', 0, f0 + 18, D(-88))
        self.pose("lying", f0 + 14)

    def act_fall_back(self, f0, dur, k, target, world):
        self._fall(f0, k)

    def act_slip_fall(self, f0, dur, k, target, world):
        self._fall(f0, k, slip=True)

    def act_faint(self, f0, dur, k, target, world):
        self.expression(f0, "deadpan", 1.0)
        for i, f in enumerate(range(f0, f0 + 16, 4)):
            self.rot("spine", 1, f, (8 if i % 2 else -8))
        self._fall(f0 + 16, k)

    def act_sit(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + 10 ** 6, loc=True)
        seat = (target if isinstance(target, (int, float)) else 0.45)
        self.pose(P(**{**POSES["sit"], "hip_dz": (seat + 0.05 - self.c.hip_z) / self.c.H}), f0 + 8)
        self.pose(P(**{**POSES["sit"], "hip_dz": (seat - self.c.hip_z + 0.02) / self.c.H}), f0 + 12)

    def act_stand_up(self, f0, dur, k, target, world):
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + 14, loc=True)
        self.pose("lean_in", f0 + 6)
        self.pose("rest", f0 + 14)
        root = self.j("root")
        self.a.key(root, 'rotation_euler', 0, f0, self.a.value_at(root, 'rotation_euler', 0, f0))
        self.a.key(root, 'rotation_euler', 0, f0 + 10, 0.0)
        self.a.key(root, 'location', 2, f0, self.a.value_at(root, 'location', 2, f0))
        self.a.key(root, 'location', 2, f0 + 10, 0.0)

    def act_throw(self, f0, dur, k, target, world):
        if target is not None:
            self.face_to(f0, target, 4, max_turn=D(70))
        self.hold_current(f0)
        self.claim(f0 + 1, f0 + 26, loc=True)
        self.pose("throw_back", f0 + 7, blend=k)
        self.pose("throw_fwd", f0 + 11, blend=k)
        self.pose("rest", f0 + 26)
        return f0 + 11   # frame de lâcher

    def _locomote(self, f0, dur, target, speed, run=False):
        root = self.j("root")
        p0 = self.root_xy(f0)
        p1 = Vector(target)
        dist = (p1 - p0).length
        if dist < 0.05:
            return
        fps = self.a.fps
        if not dur:
            dur = max(8, int(dist / speed * fps))
        stride = (self.c.thigh + self.c.shin) * (1.15 if run else 0.8)
        self.face_to(f0, p1, 4)
        f_start = f0 + 3
        f_end = f_start + dur
        self.hold_current(f0)
        self.claim(f_start, f_end + 8, loc=True)
        amp = math.degrees(math.asin(min(0.95, stride / 2 / (self.c.thigh + self.c.shin))))
        for f in range(f_start, f_end + 1, 2):
            u = (f - f_start) / float(dur)
            pos = p0.lerp(p1, u)
            self.a.key(root, 'location', 0, f, pos.x, 'LINEAR')
            self.a.key(root, 'location', 1, f, pos.y, 'LINEAR')
            ph = 2 * math.pi * (dist * u) / (2 * stride)   # phase liée à la distance : pas de glissement
            sw = math.sin(ph)
            self.rot("thigh_L", 0, f, -amp * sw)
            self.rot("thigh_R", 0, f, amp * sw)
            self.rot("shin_L", 0, f, (55 if run else 30) * max(0.0, -math.cos(ph)))
            self.rot("shin_R", 0, f, (55 if run else 30) * max(0.0, math.cos(ph)))
            self.rot("upper_arm_L", 0, f, amp * sw * (1.3 if run else 0.9))
            self.rot("upper_arm_R", 0, f, -amp * sw * (1.3 if run else 0.9))
            self.rot("forearm_L", 0, f, -(70 if run else 20))
            self.rot("forearm_R", 0, f, -(70 if run else 20))
            self.rot("spine", 0, f, 14 if run else 4)
            bob = abs(math.cos(ph)) * (0.05 if run else 0.025) * self.c.H
            self.a.key(self.j("hips"), 'location', 2, f, self.c.hip_z - (0.03 * self.c.H if run else 0) + bob)
        self.pose("rest", f_end + 6)
        # arrivé à destination, il se retourne vers la caméra (« triche ») : on ne finit pas un déplacement de dos
        if dist > 0.3 and abs(math.atan2(p1.x - p0.x, -(p1.y - p0.y))) > D(65):
            heading = math.atan2(p1.x - p0.x, -(p1.y - p0.y))
            self.a.key(root, 'rotation_euler', 2, f_end + 2, self.a.value_at(root, 'rotation_euler', 2, f_end + 2))
            self.a.key(root, 'rotation_euler', 2, f_end + 9, max(-D(55), min(D(55), heading)))
        return f_end

    def act_walk_to(self, f0, dur, k, target, world):
        return self._locomote(f0, dur, target, 1.1 * self.c.H * k)

    def act_run_to(self, f0, dur, k, target, world):
        return self._locomote(f0, dur, target, 3.0 * self.c.H * k, run=True)
