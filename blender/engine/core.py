"""Noyau Blender : remise à zéro de scène, rendu, matériaux cartoon, contours, primitives low-poly.

Compatible Blender 4.2 → 5.x (binaire ou module pip `bpy`). Aucun opérateur dépendant de l'UI :
toute la géométrie est créée via bmesh pour fonctionner en headless.
"""
import math
import bpy
import bmesh
from mathutils import Vector

_MATS = {}


# ------------------------------------------------------------------ scène / rendu
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    return sc


def hex_rgb(h, alpha=None):
    h = h.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    # sRGB -> linéaire (les couleurs du contrat sont en sRGB)
    lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
    return lin + ((alpha,) if alpha is not None else ())


def _engine_ids():
    items = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
    return [i.identifier for i in items]


def setup_render(sc, profile, engine_pref='auto', threads=0):
    """profile : dict issu de config/profiles.toml (+ 'fps')."""
    ids = _engine_ids()
    eevee = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
    engine = 'CYCLES' if engine_pref in ('auto', 'cycles') else eevee
    sc.render.engine = engine
    w, h = profile['resolution']
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = int(w), int(h), 100
    sc.render.fps = int(profile.get('fps', 30))
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'Standard'   # couleurs cartoon franches (AgX désature)
        sc.view_settings.exposure = -0.45               # matériaux semi-émissifs : éviter l'image délavée
        try:
            sc.view_settings.look = 'Medium High Contrast'
        except TypeError:
            sc.view_settings.look = 'None'
    except Exception:
        pass
    if threads:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = int(threads)
    if engine == 'CYCLES':
        cy = sc.cycles
        cy.device = 'CPU'
        cy.samples = int(profile.get('cycles_samples', 12))
        cy.use_adaptive_sampling = True
        cy.max_bounces = 4
        cy.diffuse_bounces = 2
        cy.glossy_bounces = 1
        cy.transmission_bounces = 0
        cy.transparent_max_bounces = 12
        cy.caustics_reflective = False
        cy.caustics_refractive = False
        cy.use_denoising = bool(profile.get('denoise', True))
        try:
            cy.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            cy.use_denoising = False
    else:
        try:
            sc.eevee.taa_render_samples = int(profile.get('eevee_samples', 16))
        except Exception:
            pass
    return engine


# ------------------------------------------------------------------ matériaux
def _bsdf(nt):
    for n in nt.nodes:
        if n.bl_idname == 'ShaderNodeBsdfPrincipled':
            return n
    return nt.nodes.new('ShaderNodeBsdfPrincipled')


def _set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def toon_mat(name, color_hex, rough=0.75, emission=0.0, metallic=0.0):
    """Matériau 'cartoon' : diffus mat, spéculaire faible, légère auto-illumination pour des couleurs franches."""
    key = (name, color_hex, rough, emission, metallic)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = _bsdf(m.node_tree)
    rgb = hex_rgb(color_hex, 1.0)
    _set_input(b, ['Base Color'], rgb)
    _set_input(b, ['Roughness'], rough)
    _set_input(b, ['Metallic'], metallic)
    _set_input(b, ['Specular IOR Level', 'Specular'], 0.15)
    if emission > 0:
        _set_input(b, ['Emission Color', 'Emission'], rgb)
        _set_input(b, ['Emission Strength'], emission)
    m.diffuse_color = rgb
    _MATS[key] = m
    return m


def emit_mat(name, color_hex, strength=2.0):
    key = ('emit', name, color_hex, strength)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = hex_rgb(color_hex, 1.0)
    em.inputs['Strength'].default_value = strength
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    _MATS[key] = m
    return m


def outline_mat():
    """Contour 'inverted hull' compatible Cycles ET EEVEE : faces arrière -> noir, faces avant -> transparent."""
    if 'outline' in _MATS:
        return _MATS['outline']
    m = bpy.data.materials.new('INK_outline')
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.012, 0.010, 0.016, 1.0)
    em.inputs['Strength'].default_value = 1.0
    mix = nt.nodes.new('ShaderNodeMixShader')
    # Normales retournées : la partie de coque côté caméra est « backfacing » -> transparente ;
    # seule la partie arrière, visible autour de la silhouette, reste noire (= contour).
    # La coque n'existe que pour les rayons caméra : sinon elle bloque les rayons d'ombre et
    # chaque objet s'auto-ombre (bug constaté au premier rendu : image presque noire).
    lp = nt.nodes.new('ShaderNodeLightPath')
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lp.outputs['Is Camera Ray'], inv.inputs[1])
    mx = nt.nodes.new('ShaderNodeMath')
    mx.operation = 'MAXIMUM'
    nt.links.new(geo.outputs['Backfacing'], mx.inputs[0])
    nt.links.new(inv.outputs[0], mx.inputs[1])
    nt.links.new(mx.outputs[0], mix.inputs[0])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    try:
        m.use_backface_culling = True
    except Exception:
        pass
    for attr, val in (('surface_render_method', 'DITHERED'), ('blend_method', 'HASHED')):
        try:
            setattr(m, attr, val)
        except Exception:
            pass
    m.diffuse_color = (0, 0, 0, 1)
    _MATS['outline'] = m
    return m


OUTLINES_ENABLED = True


def add_outline(obj, thickness):
    if not OUTLINES_ENABLED or thickness <= 0 or obj.type != 'MESH':
        return
    om = outline_mat()
    obj.data.materials.append(om)
    mod = obj.modifiers.new('ink', 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(obj.data.materials) - 1


# ------------------------------------------------------------------ primitives (bmesh)
def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), parent=None, coll=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.08
    link(e, coll)
    if parent is not None:
        e.parent = parent
    e.location = loc
    return e


def _finish(name, bm, mat, loc, rot, parent, coll, smooth, ink):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    link(o, coll)
    if mat is not None:
        me.materials.append(mat)
    if parent is not None:
        o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    if ink:
        add_outline(o, ink)
    return o


def _scale_bm(bm, sc):
    for v in bm.verts:
        v.co = Vector((v.co.x * sc[0], v.co.y * sc[1], v.co.z * sc[2]))


def box(name, size, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, ink=0.0, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    _scale_bm(bm, size)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES')
    return _finish(name, bm, mat, loc, rot, parent, coll, False, ink)


def ball(name, radii, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, ink=0.0, detail=2, smooth=False):
    """Icosphère low-poly (facettes visibles = style low-poly)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=detail, radius=1.0)
    _scale_bm(bm, radii)
    return _finish(name, bm, mat, loc, rot, parent, coll, smooth, ink)


def uvball(name, radii, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, ink=0.0, seg=12, rings=8, smooth=True, zmin=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    if zmin is not None:   # demi-sphère / calotte
        geom = [v for v in bm.verts if v.co.z < zmin - 1e-4]
        bmesh.ops.delete(bm, geom=geom, context='VERTS')
    _scale_bm(bm, radii)
    return _finish(name, bm, mat, loc, rot, parent, coll, smooth, ink)


def cyl(name, r1, r2, depth, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, ink=0.0, seg=8, base_at_origin=False, smooth=False):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)
    if base_at_origin:
        for v in bm.verts:
            v.co.z += depth / 2.0
    return _finish(name, bm, mat, loc, rot, parent, coll, smooth, ink)


def limb(name, r_top, r_bot, length, mat=None, parent=None, coll=None, ink=0.0, seg=8):
    """Cylindre qui PEND sous son pivot (origine en haut, extrémité à -length)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r_bot, radius2=r_top, depth=length)
    for v in bm.verts:
        v.co.z -= length / 2.0
    return _finish(name, bm, mat, (0, 0, 0), (0, 0, 0), parent, coll, True, ink)


def torus(name, R, r, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, seg=16, ring=6, ink=0.0):
    bm = bmesh.new()
    verts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        row = []
        for j in range(ring):
            b = 2 * math.pi * j / ring
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    for i in range(seg):
        for j in range(ring):
            a, b2 = verts[i][j], verts[(i + 1) % seg][j]
            c, d = verts[(i + 1) % seg][(j + 1) % ring], verts[i][(j + 1) % ring]
            bm.faces.new((a, b2, c, d))
    return _finish(name, bm, mat, loc, rot, parent, coll, True, ink)


def arc_strip(name, radius, angle_deg, thickness, depth, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None, segs=10, bend=1.0):
    """Bande courbe dans le plan XZ (bouche, sourcils). bend>0 : sourire (creux vers le haut), bend<0 : moue."""
    bm = bmesh.new()
    a0 = math.radians(angle_deg)
    rows = []
    for i in range(segs + 1):
        t = -a0 / 2 + a0 * i / segs
        x = radius * math.sin(t)
        z = bend * (radius - radius * math.cos(t))
        rows.append([bm.verts.new((x, yy, z + dz)) for (yy, dz) in ((-depth, -thickness), (-depth, thickness), (depth, thickness), (depth, -thickness))])
    for i in range(segs):
        for j in range(4):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][(j + 1) % 4], rows[i][(j + 1) % 4]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])
    return _finish(name, bm, mat, loc, rot, parent, coll, True, 0.0)


def star(name, r_out, r_in, points, depth, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, coll=None):
    bm = bmesh.new()
    front, back = [], []
    for i in range(points * 2):
        a = math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        front.append(bm.verts.new((r * math.cos(a), -depth, r * math.sin(a))))
        back.append(bm.verts.new((r * math.cos(a), depth, r * math.sin(a))))
    bm.faces.new(front)
    bm.faces.new(back[::-1])
    n = len(front)
    for i in range(n):
        bm.faces.new((front[i], back[i], back[(i + 1) % n], front[(i + 1) % n]))
    return _finish(name, bm, mat, loc, rot, parent, coll, False, 0.0)


def text_obj(name, body, size, mat=None, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), parent=None, coll=None, extrude=0.01):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.extrude = extrude
    o = bpy.data.objects.new(name, cu)
    link(o, coll)
    if mat is not None:
        cu.materials.append(mat)
    if parent is not None:
        o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    return o


def world_bbox(obj, include_children=True):
    pts = []
    objs = [obj] + (list(obj.children_recursive) if include_children else [])
    for o in objs:
        if o.type in ('MESH', 'FONT', 'CURVE') and not o.name.endswith('_hidden'):
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        p = obj.matrix_world.translation
        return Vector(p), Vector(p)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def set_world_color(sc, color_hex, strength=1.0):
    w = bpy.data.worlds.new('World')
    sc.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = None
    for n in w.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBackground':
            bg = n
    if bg is None:
        bg = w.node_tree.nodes.new('ShaderNodeBackground')
        out = w.node_tree.nodes.new('ShaderNodeOutputWorld')
        w.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs['Color'].default_value = hex_rgb(color_hex, 1.0)
    bg.inputs['Strength'].default_value = strength
    return w
