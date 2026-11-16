"""Effets cartoon simples, entièrement en géométrie (aucune simulation) : rapides et déterministes."""
import math
import random
from mathutils import Vector
from . import core

D = math.radians


def _pop(anim, o, f_in, f_peak, f_out, peak=1.0, hold=1.0):
    for i in range(3):
        anim.key(o, 'scale', i, f_in - 1, 0.001, 'CONSTANT')
        anim.key(o, 'scale', i, f_in, 0.05)
        anim.key(o, 'scale', i, f_peak, peak)
        anim.key(o, 'scale', i, f_out - 2, hold)
        anim.key(o, 'scale', i, f_out, 0.001)


def _face_camera(o, cam):
    c = o.constraints.new('TRACK_TO')
    c.target = cam
    c.track_axis = 'TRACK_NEGATIVE_Y'
    c.up_axis = 'UP_Z'


def spawn(kind, anim, at, f, cam, scale=1.0, coll=None, seed=0):
    rng = random.Random(seed + f)
    at = Vector(at)
    made = []
    if kind == "smoke_puff":
        m = core.toon_mat("fx_smoke", "#D9D9D9", emission=0.15)
        for i in range(7):
            off = Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.25))) * scale
            o = core.ball(f"fx_smoke_{f}_{i}", (0.22 * scale,) * 3, m, at + off, coll=coll, detail=1, ink=0.006)
            _pop(anim, o, f + i // 2, f + 6, f + 22, 1.2, 0.8)
            anim.key(o, 'location', 2, f, o.location.z)
            anim.key(o, 'location', 2, f + 22, o.location.z + 0.4 * scale)
            made.append(o)
    elif kind == "explosion":
        flash = core.star(f"fx_flash_{f}", 0.9 * scale, 0.45 * scale, 9, 0.02, core.emit_mat("fx_flash", "#FFF3B0", 6.0), at, coll=coll)
        _face_camera(flash, cam)
        _pop(anim, flash, f, f + 2, f + 7, 1.6, 1.0)
        made.append(flash)
        for i in range(9):
            col = "#FF7B00" if i % 2 else "#FFBA08"
            off = Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.4, 0.4), rng.uniform(-0.2, 0.6))) * scale
            o = core.ball(f"fx_fire_{f}_{i}", (0.25 * scale,) * 3, core.emit_mat("fx_fire" + col, col, 4.0), at + off, coll=coll, detail=1)
            _pop(anim, o, f + 1, f + 4, f + 14, 1.3, 0.7)
            made.append(o)
        made += spawn("smoke_puff", anim, at + Vector((0, 0, 0.3)), f + 6, cam, scale * 1.4, coll, seed)
    elif kind == "sparkles":
        for i in range(6):
            off = Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.1, 0.1), rng.uniform(-0.2, 0.5))) * scale
            o = core.star(f"fx_spark_{f}_{i}", 0.08 * scale, 0.03 * scale, 4, 0.005, core.emit_mat("fx_spark", "#FFE066", 5.0), at + off, coll=coll)
            _face_camera(o, cam)
            _pop(anim, o, f + i * 2, f + i * 2 + 3, f + i * 2 + 10, 1.4, 1.0)
            made.append(o)
    elif kind == "impact_star":
        o = core.star(f"fx_impact_{f}", 0.45 * scale, 0.2 * scale, 8, 0.01, core.emit_mat("fx_impact", "#FFD60A", 3.0), at, coll=coll)
        _face_camera(o, cam)
        _pop(anim, o, f, f + 2, f + 10, 1.3, 1.0)
        made.append(o)
    elif kind == "sweat_drops":
        for i in range(3):
            p = at + Vector((0.18 * (i - 1), -0.1, 0.15)) * scale
            o = core.ball(f"fx_sweat_{f}_{i}", (0.03 * scale, 0.03 * scale, 0.05 * scale), core.emit_mat("fx_sweat", "#8ED1FC", 1.5), p, coll=coll, detail=1)
            _pop(anim, o, f + i * 3, f + i * 3 + 2, f + i * 3 + 16, 1.0, 1.0)
            anim.key(o, 'location', 2, f + i * 3, p.z)
            anim.key(o, 'location', 2, f + i * 3 + 16, p.z - 0.3 * scale, 'LINEAR')
            made.append(o)
    elif kind == "question_marks":
        for i in range(2):
            p = at + Vector((0.2 * (i * 2 - 1), 0, 0.35 + 0.1 * i)) * scale
            o = core.text_obj(f"fx_q_{f}_{i}", "?", 0.35 * scale, core.emit_mat("fx_q", "#FFFFFF", 1.2), p, coll=coll, extrude=0.02)
            _face_camera(o, cam)
            _pop(anim, o, f + i * 4, f + i * 4 + 4, f + 40, 1.2, 1.0)
            made.append(o)
    elif kind == "hearts":
        for i in range(4):
            p = at + Vector((rng.uniform(-0.3, 0.3), 0, 0.3 + 0.1 * i)) * scale
            h = core.empty(f"fx_heart_{f}_{i}", p, None, coll)
            hm = core.emit_mat("fx_heart", "#FF4D6D", 2.0)
            for s in (1, -1):
                core.ball(f"fx_heart_{f}_{i}_{s}", (0.06 * scale,) * 3, hm, (s * 0.045 * scale, 0, 0.03 * scale), parent=h, coll=coll, detail=1)
            core.cyl(f"fx_heart_{f}_{i}_tip", 0.085 * scale, 0.0, 0.11 * scale, hm, (0, 0, -0.04 * scale), (D(180), 0, 0), parent=h, coll=coll, seg=4)
            _pop(anim, h, f + i * 3, f + i * 3 + 3, f + i * 3 + 24, 1.2, 1.0)
            anim.key(h, 'location', 2, f + i * 3, p.z)
            anim.key(h, 'location', 2, f + i * 3 + 24, p.z + 0.5 * scale)
            made.append(h)
    else:
        raise ValueError(f"effet inconnu {kind}")
    return made
