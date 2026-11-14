"""Caméra verticale 9:16 auto-cadrée sur les positions RÉELLES (évaluées) des sujets.

Le cadrage est calculé, pas réglé à la main (leçon reprise de make-short : les caméras manuelles ratent
les personnages et traversent les décors). Chaque mouvement correspond à une intention du storyboard.
"""
import math
import random
from mathutils import Vector

D = math.radians
SENSOR_H = 24.0
ASPECT = 9.0 / 16.0

LENS = {"wide": 24, "full": 28, "medium": 35, "medium_close": 45, "close_up": 55, "extreme_close_up": 75,
        "two_shot": 30, "over_shoulder": 45, "insert": 50}
ELEV = {"eye": -4, "low": -20, "high": 28, "dutch": -2, "top_down": 72}


def vfov(lens):
    return 2 * math.atan(SENSOR_H / 2.0 / lens)


def span_for(framing, lm, head_r):
    """-> (z_lo, z_hi, centre_xy, marge) pour un personnage (landmarks monde)."""
    top = lm["head_top"].z
    c = Vector((lm["head"].x, lm["head"].y))
    if framing == "wide":
        return 0.0, top, Vector((lm["hips"].x, lm["hips"].y)), 3.0
    if framing == "full":
        return 0.0, top, Vector((lm["hips"].x, lm["hips"].y)), 1.22
    if framing == "medium":
        return lm["hips"].z - 0.12, top, c, 1.45
    if framing in ("medium_close", "over_shoulder"):
        return lm["chest"].z - 0.05, top, c, 1.62
    if framing == "close_up":
        return lm["neck"].z - 0.10, top, c, 1.85   # tête entière + épaules : jamais de crâne coupé
    if framing == "extreme_close_up":
        return lm["eyes"].z - head_r * 0.55, lm["eyes"].z + head_r * 0.5, c, 1.15
    return 0.0, top, c, 1.3


class CameraRig:
    def __init__(self, cam_obj, anim, frames, seed=0):
        self.cam = cam_obj
        self.a = anim
        self.N = frames
        self.rng = random.Random(seed)
        self.keys = []   # (frame, pos, aim, lens, roll) pour le rapport
        self.base_az = None   # azimut figé sur la 1re évaluation : la caméra ne suit pas les rotations du sujet
        self.blocked = False  # obstacle impossible à contourner : run_shot le masque pour la caméra

    def solve(self, spec, subject_fn, secondary_fn, frame, occluder_fn, move_t=0.0):
        """subject_fn(frame) -> dict(kind, lm|bbox|point, head_r). Retourne (pos, aim, lens, roll)."""
        framing = spec["framing"]
        lens = float(spec.get("lens_mm", LENS[framing]))
        subj = subject_fn(frame)
        sec = secondary_fn(frame) if secondary_fn else None
        if subj["kind"] == "char":
            lo, hi, cxy, marg = span_for("medium" if framing == "two_shot" else framing, subj["lm"], subj["head_r"])
            width = 0.7 * subj["head_r"] * 4
            facing = subj["facing"]
        elif subj["kind"] == "bbox":
            blo, bhi = subj["bbox"]
            lo, hi = blo.z, bhi.z
            cxy = Vector(((blo.x + bhi.x) / 2, (blo.y + bhi.y) / 2))
            width = max(bhi.x - blo.x, bhi.y - blo.y)
            marg = 2.2 if framing in ("insert", "close_up", "extreme_close_up") else 3.0
            facing = Vector((0, -1, 0))
        else:
            p = subj["point"]
            # repère (mark) : hauteur de cadre selon la valeur de plan, référence = personnage de 1,5 m
            H_ref = {"wide": 1.55, "full": 1.0, "medium": 0.7, "two_shot": 0.9}.get(framing, 0.5)
            lo, hi, cxy, marg, width = p.z - 1.0, p.z + 0.5, Vector((p.x, p.y)), H_ref * 3.0 / 1.5, 1.0
            facing = Vector((0, -1, 0))
        if framing == "two_shot" and sec is not None and sec["kind"] == "char":
            lo2, hi2, c2, _ = span_for("medium", sec["lm"], sec["head_r"])
            lo, hi = min(lo, lo2), max(hi, hi2)
            width = (cxy - c2).length + sec["head_r"] * 3
            cxy = (cxy + c2) / 2
            marg = 1.3
        span = max(hi - lo, 0.15)
        fit_w = 1.15 if framing in ("two_shot", "wide") else (1.9 if subj["kind"] == "bbox" else 0.0)
        H = max(span * marg, width / ASPECT * fit_w)
        # direction de base : vers le côté caméra (-Y), tirée vers la face du sujet pour voir les visages
        if self.base_az is None:
            base = Vector((facing.x * 0.45, -1.0 + min(facing.y, 0.0) * 0.45, 0))
            base.normalize()
            self.base_az = math.atan2(base.x, -base.y)
        az = self.base_az + D(spec.get("side_deg", 0.0))
        if spec.get("move") == "orbit_left":
            az += D(-28) * move_t
        elif spec.get("move") == "orbit_right":
            az += D(28) * move_t
        if framing == "over_shoulder" and sec is not None:
            sp = sec["lm"]["head"] if sec["kind"] == "char" else sec.get("point", Vector((0, 0, 1)))
            v = Vector((sp.x - cxy.x, sp.y - cxy.y))
            if v.length > 0.1:
                az = math.atan2(v.x, -v.y) + D(12)
        el = D(ELEV.get(spec.get("angle", "eye"), -4))
        if subj["kind"] == "bbox" and subj["bbox"][0].z > 0.3:
            el = max(el, D(10))   # objet posé sur un meuble : une contre-plongée filmerait le meuble
        roll = D(14) if spec.get("angle") == "dutch" else 0.0
        aim = Vector((cxy.x, cxy.y, (lo + hi) / 2))
        if framing in ("medium", "over_shoulder", "two_shot"):
            aim.z -= 0.08 * H   # visages dans la moitié haute : les sous-titres occupent le tiers bas
        elif framing in ("medium_close", "close_up"):
            aim.z -= 0.04 * H   # plan serré : décalage réduit, sinon le haut du crâne sort du cadre
        d = (H / 2.0) / math.tan(vfov(lens) / 2.0)
        if spec.get("move") == "push_in":
            d *= 1.0 - 0.2 * move_t
            if subj["kind"] == "char":
                aim = aim.lerp(Vector((aim.x, aim.y, subj["lm"]["eyes"].z - 0.08 * H)), 0.5 * move_t)
        elif spec.get("move") == "pull_out":
            d *= 1.0 + 0.4 * move_t
        elif spec.get("move") == "crash_zoom":
            d *= 1.35 if move_t < 0.5 else 0.62
        right = Vector((math.cos(az), math.sin(az), 0))
        if spec.get("move") == "pan_left":
            aim += right * (0.35 * H * (1 - move_t))
        elif spec.get("move") == "pan_right":
            aim -= right * (0.35 * H * (1 - move_t))
        direction = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
        if subj["kind"] == "char" and framing != "extreme_close_up":
            d = max(d, 6.5 * subj["head_r"] * lens / 55.0)   # ≈ 80 % de la distance d'un gros plan
        d = max(d, 0.6)
        if occluder_fn and spec.get("avoid_occluders", True):
            # plusieurs rayons (yeux, torse, centre) : un seul rayon passait sous un plateau de table et laissait
            # la caméra filmer « entre les pieds », tête cachée
            pts = [aim]
            if subj["kind"] == "char":
                pts = [subj["lm"]["eyes"], subj["lm"]["chest"], aim]
            base_occ = occluder_fn

            def occluder_fn(a_, dir_, d_, _pts=pts, _occ=base_occ, _aim=aim):
                cam_p = _aim + dir_ * d_
                worst = None
                for p_ in _pts:
                    v = cam_p - p_
                    L = v.length
                    if L < 1e-3:
                        continue
                    h = _occ(p_, v / L, L)
                    if h is not None and h < L - 0.05:
                        rel = d_ * h / L
                        worst = rel if worst is None else min(worst, rel)
                return worst
            hit = occluder_fn(aim, direction, d)
            if hit is not None and hit < d:
                # 1) comme un cadreur : monter pour regarder par-dessus l'obstacle (meuble au premier plan)
                for extra in (8, 16, 24, 32, 40):
                    el2 = min(D(70), el + D(extra))
                    dir2 = Vector((math.sin(az) * math.cos(el2), -math.cos(az) * math.cos(el2), math.sin(el2)))
                    h2 = occluder_fn(aim, dir2, d)
                    if h2 is None or h2 >= d:
                        direction = dir2
                        hit = None
                        break
                # 2) puis tourner autour du sujet (comme un cadreur qui change d'axe), en remontant un peu
                if hit is not None:
                    for daz, extra in ((20, 0), (-20, 0), (20, 12), (-20, 12), (40, 8), (-40, 8)):
                        az2, el2 = az + D(daz), min(D(70), el + D(extra))
                        dir2 = Vector((math.sin(az2) * math.cos(el2), -math.cos(az2) * math.cos(el2), math.sin(el2)))
                        h2 = occluder_fn(aim, dir2, d)
                        if h2 is None or h2 >= d:
                            direction, az, hit = dir2, az2, None
                            break
                # 3) en dernier recours : on garde un cadrage normal et l'obstacle sera masqué pour la caméra
                #    (jamais de plan collé au visage : c'était la cause des « plans bizarres trop proches »)
                if hit is not None:
                    self.blocked = True
        pos = aim + direction * d
        if pos.z < 0.12:
            pos.z = 0.12
        if framing == "over_shoulder" and sec is not None and sec["kind"] == "char":
            # décaler derrière l'épaule de l'interlocuteur
            pos += right * sec["head_r"] * 1.6
        return pos, aim, lens, roll

    def key(self, f, pos, aim, lens, roll, interp='BEZIER'):
        rot = (aim - pos).to_track_quat('-Z', 'Y').to_euler()
        if roll:
            q = rot.to_quaternion()
            from mathutils import Quaternion
            q = q @ Quaternion((0, 0, 1), roll)
            rot = q.to_euler()
        if self.keys:
            rot.make_compatible(self.keys[-1][5])
        for i in range(3):
            self.a.key(self.cam, 'location', i, f, pos[i], interp)
            self.a.key(self.cam, 'rotation_euler', i, f, rot[i], interp)
        self.keys.append((f, pos.copy(), aim.copy(), lens, roll, rot.copy()))

    def add_shake(self, f0, frames, amp_deg):
        """Secousse amortie et LISSÉE (une clé toutes les 2 images, alternance de sens) : impact lisible sans saccade."""
        fs = list(range(f0, min(self.N, f0 + frames) + 1, 2))
        for i, f in enumerate(fs):
            decay = (1.0 - i / float(len(fs))) ** 1.5
            sign = 1 if i % 2 == 0 else -1
            for ax in (0, 1):
                base = self.a.value_at(self.cam, 'rotation_euler', ax, f)
                jitter = sign * amp_deg * (0.6 + 0.4 * self.rng.random()) * (1.0 if ax == 0 else 0.7)
                self.a.key(self.cam, 'rotation_euler', ax, f, base + D(jitter * decay), 'BEZIER')

    def add_handheld(self, amp_deg=0.35):
        for f in range(1, self.N + 1, 6):
            for ax in (0, 2):
                base = self.a.value_at(self.cam, 'rotation_euler', ax, f)
                self.a.key(self.cam, 'rotation_euler', ax, f, base + D(self.rng.uniform(-amp_deg, amp_deg)))

    def add_punch(self, f, strength=1.0, hold_frames=26, face=None, framing="medium"):
        """Zoom « punch » : avance rapide mais lissée vers le visage (5 images), tenue, puis retour doux (12 images).
        Superposé au mouvement existant (on lit la position de base à chaque clé)."""
        if f < 1 or f >= self.N - 2 or not self.keys:
            return
        k = {"wide": 0.08, "two_shot": 0.09, "full": 0.10, "medium": 0.12, "medium_close": 0.09, "over_shoulder": 0.08,
             "close_up": 0.05, "insert": 0.05, "extreme_close_up": 0.0}.get(framing, 0.1) * strength
        if k <= 0:
            return   # déjà très serré : un zoom de plus collerait la caméra au visage
        aim = min(self.keys, key=lambda kk: abs(kk[0] - f))[2]
        f_in, f_hold = f + 5, min(self.N, f + hold_frames)
        f_out = f_hold + 12 if f_hold + 12 <= self.N else None
        frames = [f, f_in, f_hold] + ([f_out] if f_out else [])
        base = {fr: Vector([self.a.value_at(self.cam, 'location', i, fr) for i in range(3)]) for fr in frames}
        amt = {f: 0.0, f_in: 1.0, f_hold: 1.0 if f_out else 1.0}
        if f_out:
            amt[f_out] = 0.0
        for fr in frames:
            # on zoome VERS LE VISAGE du sujet (sinon la tête sort du cadre si le personnage saute)
            tgt = aim.lerp(face, 0.6 * amt[fr]) if face is not None else aim
            p = base[fr] + (tgt - base[fr]) * (k * amt[fr])
            rot = (tgt - p).to_track_quat('-Z', 'Y').to_euler()
            cur = [self.a.value_at(self.cam, 'rotation_euler', i, fr) for i in range(3)]
            from mathutils import Euler
            rot.make_compatible(Euler(cur))
            for i in range(3):
                self.a.key(self.cam, 'location', i, fr, p[i], 'LINEAR' if fr == f else 'BEZIER')
                self.a.key(self.cam, 'rotation_euler', i, fr, rot[i], 'LINEAR' if fr == f else 'BEZIER')
