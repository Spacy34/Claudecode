"""Éclairage cartoon par ambiance : clé (soleil), remplissage (area), contre-jour (rim) + couleur du monde.
Lisibilité des silhouettes avant réalisme : le rim détache les personnages du fond."""
import math
import bpy
from mathutils import Vector
from . import core

D = math.radians

#        world, world_str, sun_col, sun_str, sun_rot(x,z), fill_col, fill_W, rim_col, rim_W
MOODS = {
    "day_warm":      ("#BFE3FF", 0.7, "#FFF1D6", 3.0, (50, 35), "#D8ECFF", 300, "#FFFFFF", 450),
    "day_cool":      ("#CDE7FF", 0.7, "#F2F7FF", 2.6, (55, 20), "#E0F0FF", 300, "#FFFFFF", 350),
    "night":         ("#1D2A4D", 0.6, "#9DB4FF", 1.6, (60, 40), "#5A6FB8", 220, "#9FC3FF", 600),
    "interior_warm": ("#FFE2C2", 0.55, "#FFE0B5", 2.4, (55, 30), "#FFD8B0", 350, "#FFF3E0", 400),
    "office_flat":   ("#EEF2F5", 0.8, "#FFFFFF", 2.2, (60, 15), "#F0F4F8", 420, "#FFFFFF", 250),
    "dramatic":      ("#2B2D42", 0.35, "#FFD6A5", 5.0, (35, 70), "#3A3D5C", 80, "#FF6B6B", 900),
    "spooky":        ("#14281D", 0.45, "#9EF01A", 1.4, (65, -40), "#2D6A4F", 150, "#B5E48C", 700),
    "sunset":        ("#FFB4A2", 0.8, "#FF9F1C", 3.6, (20, 60), "#CDB4DB", 260, "#FFD166", 650),
}


def _look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def setup(sc, mood, center=(0, 0, 1.0), interior=False):
    w, ws, sc_col, s_str, (rx, rz), f_col, f_w, r_col, r_w = MOODS[mood]
    core.set_world_color(sc, w, ws)
    sun_d = bpy.data.lights.new("KEY_sun", 'SUN')
    sun_d.energy = s_str
    sun_d.color = core.hex_rgb(sc_col)
    sun_d.angle = D(8)
    sun = bpy.data.objects.new("KEY_sun", sun_d)
    sc.collection.objects.link(sun)
    # Le soleil éclaire selon son -Z local. rx>0 : la lumière part du côté caméra (-Y) vers le fond,
    # donc les visages (tournés vers -Y) sont éclairés ; rz décale latéralement la source.
    sun.rotation_euler = (D(rx), 0, D(rz))
    c = Vector(center)
    fill_d = bpy.data.lights.new("FILL", 'AREA')
    fill_d.energy = f_w
    fill_d.size = 4.0
    fill_d.color = core.hex_rgb(f_col)
    fill = bpy.data.objects.new("FILL", fill_d)
    sc.collection.objects.link(fill)
    fill.location = c + Vector((3.5, -5.0, 2.5))
    _look_at(fill, c)
    rim_d = bpy.data.lights.new("RIM", 'AREA')
    rim_d.energy = r_w
    rim_d.size = 2.0
    rim_d.color = core.hex_rgb(r_col)
    rim = bpy.data.objects.new("RIM", rim_d)
    sc.collection.objects.link(rim)
    rim.location = c + Vector((-2.5, 2.2 if interior else 4.0, 3.2))
    _look_at(rim, c)
    return {"sun": sun, "fill": fill, "rim": rim}
