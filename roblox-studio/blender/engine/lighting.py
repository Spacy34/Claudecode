"""Éclairage cartoon par ambiance : clé (soleil), remplissage (area), contre-jour (rim) + couleur du monde.
Lisibilité des silhouettes avant réalisme : le rim détache les personnages du fond."""
import math
import bpy
from mathutils import Vector
from . import core

D = math.radians

#        world, world_str, sun_col, sun_str, sun_rot(x,z), fill_col, fill_W, rim_col, rim_W
MOODS = {
    "day_warm":      ("#BFE3FF", 0.45, "#FFF1D6", 2.2, (50, 35), "#D8ECFF", 300, "#FFFFFF", 450),
    "day_cool":      ("#CDE7FF", 0.45, "#F2F7FF", 2.0, (55, 20), "#E0F0FF", 300, "#FFFFFF", 350),
    "night":         ("#1D2A4D", 0.6, "#9DB4FF", 1.6, (60, 40), "#5A6FB8", 220, "#9FC3FF", 600),
    "interior_warm": ("#FFE2C2", 0.55, "#FFE0B5", 2.4, (55, 30), "#FFD8B0", 350, "#FFF3E0", 400),
    "office_flat":   ("#EEF2F5", 0.5, "#FFFFFF", 1.6, (60, 15), "#F0F4F8", 420, "#FFFFFF", 250),
    "dramatic":      ("#2B2D42", 0.35, "#FFD6A5", 5.0, (35, 70), "#3A3D5C", 80, "#FF6B6B", 900),
    "spooky":        ("#14281D", 0.45, "#9EF01A", 1.4, (65, -40), "#2D6A4F", 150, "#B5E48C", 700),
    "sunset":        ("#FFB4A2", 0.8, "#FF9F1C", 3.6, (20, 60), "#CDB4DB", 260, "#FFD166", 650),
}


def _look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def setup(sc, mood, center=(0, 0, 1.0), interior=False, sky=None):
    w, ws, sc_col, s_str, (rx, rz), f_col, f_w, r_col, r_w = MOODS[mood]
    if sky and mood not in ("night", "spooky", "dramatic"):
        core.set_sky(sc, sky[0], sky[1], ws)          # extérieur de jour : ciel en dégradé
    else:
        core.set_world_color(sc, w, ws)
    sun_d = bpy.data.lights.new("KEY_sun", 'SUN')
    sun_d.energy = s_str * 1.25
    sun_d.color = core.hex_rgb(sc_col)
    sun_d.angle = D(3)   # ombres nettes et franches, comme un jeu en blocs
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
    return {"sun": sun, "fill": fill, "rim": rim, "rim_color": r_col, "rim_energy": r_w}


BLOOM = {"night": 0.45, "dramatic": 0.4, "spooky": 0.4, "sunset": 0.3, "interior_warm": 0.2}


def post_effects(sc, mood, interior=False):
    """Halo lumineux (bloom) sur les sources : lampes, fenêtres, néons — le « Future lighting » des jeux en blocs.
    Compositeur Blender 5 (node group) ; repli sur l'ancien compositeur ; jamais bloquant."""
    strength = BLOOM.get(mood, 0.18)
    try:
        ng = bpy.data.node_groups.new("rbx_post", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        for k, v in (("Type", 'Bloom'), ("Quality", 'High'), ("Threshold", 1.25), ("Strength", strength), ("Size", 0.6)):
            try:
                gl.inputs[k].default_value = v
            except (KeyError, TypeError, ValueError):
                pass
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
        try:
            sc.render.compositor_device = 'CPU'   # serveur sans GPU/EGL : le compositeur GPU planterait le rendu
        except (AttributeError, TypeError):
            pass
        sc.compositing_node_group = ng
        sc.render.use_compositing = True
        return True
    except Exception as e:   # version sans ce compositeur : pas de halo, rendu intact
        print("[lighting] bloom indisponible :", e)
        return False


def interior_fill(sc, center=(0, 0.5, 1.0), mood="interior_warm"):
    """Intérieur : plafonnier doux (grande source) qui remplace la lumière indirecte manquante en rendu rapide."""
    col = {"night": "#9DB4FF", "spooky": "#B5E48C", "dramatic": "#FFD6A5"}.get(mood, "#FFE7C7")
    d = bpy.data.lights.new("CEIL", 'AREA')
    d.energy = 90 if mood not in ("night", "spooky", "dramatic") else 35
    d.size = 5.0
    d.color = core.hex_rgb(col)
    o = bpy.data.objects.new("CEIL", d)
    sc.collection.objects.link(o)
    o.location = (center[0], center[1] + 0.5, 3.1)
    return o


RIM_GAIN = {"night": 1.5, "dramatic": 1.6, "spooky": 1.4, "sunset": 1.3}


def character_rims(sc, chars, mood, interior=False, receivers=None):
    """Lumière de contour PAR personnage : deux petites sources derrière lui (côté fond), en hauteur, qui suivent
    ses déplacements (enfants de sa racine). Elles dessinent un liseré clair sur la tête et les épaules : le
    personnage se détache du décor même quand les couleurs sont proches."""
    _w, _ws, _sc, _ss, _rot, _fc, _fw, r_col, _rw = MOODS[mood]
    gain = RIM_GAIN.get(mood, 1.0) * (0.8 if interior else 1.0)
    made = []
    for cid, ch in chars.items():
        H = ch.H
        root = ch.joints["root"]
        head = ch.joints["head"].matrix_world.translation
        for side in (1, -1):
            d = bpy.data.lights.new(f"RIMC_{cid}_{side}", 'AREA')
            d.energy = 11.0 * H * H * gain * (1.0 if side == 1 else 0.6)
            d.size = 0.35 * H
            try:
                d.spread = math.radians(40)   # faisceau serré : la tête et les épaules, pas la pièce
            except AttributeError:
                pass
            d.color = core.hex_rgb(r_col)
            try:
                d.use_shadow = False   # ne projette pas d'ombre : pur liseré, aucun impact sur le décor
            except AttributeError:
                pass
            o = bpy.data.objects.new(f"RIMC_{cid}_{side}", d)
            sc.collection.objects.link(o)
            o.parent = root
            # repère local du personnage : il regarde -Y ; derrière = +Y ; côté = ±X
            o.location = (side * 0.55 * H, 0.75 * H, 1.55 * H)
            bpy.context.view_layer.update()
            tgt = Vector((head.x, head.y, head.z - 0.15 * H))
            dvec = tgt - o.matrix_world.translation
            o.matrix_world = _aim_matrix(o.matrix_world.translation.copy(), dvec)
            if receivers is not None:
                try:   # « light linking » : seuls les personnages reçoivent ce liseré (le décor n'est jamais éclairé)
                    o.light_linking.receiver_collection = receivers
                except (AttributeError, TypeError):
                    pass
            made.append(o)
    return made


def _aim_matrix(loc, direction):
    from mathutils import Matrix
    q = direction.to_track_quat('-Z', 'Y')
    return Matrix.Translation(loc) @ q.to_matrix().to_4x4()
