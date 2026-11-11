"""Contrôles géométriques exécutés DANS Blender après animation (aucun jugement esthétique ici).

Ils détectent ce qu'un script peut mesurer de façon fiable : personnage hors champ, tête coupée,
visage sous la zone des sous-titres, objets flottants, interpénétrations grossières, sortie du décor.
La qualité visuelle réelle reste du ressort du critique visuel (images rendues) et de l'humain.
"""
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

MIN_HEAD_FRAC = {"wide": 0.025, "full": 0.05, "medium": 0.09, "medium_close": 0.13, "close_up": 0.2, "extreme_close_up": 0.3,
                 "two_shot": 0.07, "over_shoulder": 0.12, "insert": 0.0}


def _proj(sc, cam, p):
    v = world_to_camera_view(sc, cam, p)
    return v.x, v.y, v.z


def run(sc, cam, chars, props_state, set_info, spec, sample_frames):
    out = []
    seen_visible = {cid: False for cid in chars}
    framing = spec["camera"]["framing"]
    subject = spec["camera"].get("subject")
    for f in sample_frames:
        sc.frame_set(f)
        for cid, ch in chars.items():
            lm = ch.landmarks_world()
            hx, hy, hz = _proj(sc, cam, lm["head"])
            tx, ty, _ = _proj(sc, cam, lm["head_top"])
            fx_, fy, _ = _proj(sc, cam, lm["feet"])
            in_frame = hz > 0 and -0.05 <= hx <= 1.05 and -0.05 <= hy <= 1.05
            head_frac = abs(ty - hy) * 2.0 if hz > 0 else 0.0
            is_subject = isinstance(subject, dict) and subject.get("id") == cid
            if in_frame:
                seen_visible[cid] = True
            if not in_frame:
                out.append({"id": f"char_offscreen:{cid}", "severity": "major" if is_subject else "minor", "status": "fail" if is_subject else "warn",
                            "frame": f, "message": f"{cid} présent dans le plan mais hors champ (tête projetée {hx:.2f},{hy:.2f})."})
                continue
            if is_subject:
                if head_frac < MIN_HEAD_FRAC.get(framing, 0.0) * 0.7:
                    out.append({"id": f"subject_too_small:{cid}", "severity": "major", "status": "fail", "frame": f,
                                "message": f"Tête du sujet = {head_frac:.1%} de la hauteur, attendu ≥ {MIN_HEAD_FRAC[framing]:.0%} pour {framing}."})
                if ty > 1.0 and framing not in ("close_up", "extreme_close_up"):
                    out.append({"id": f"head_cropped:{cid}", "severity": "major", "status": "fail", "frame": f,
                                "message": f"Haut de la tête coupé (y={ty:.2f})."})
                if hy < 0.36 and framing not in ("wide", "insert"):
                    out.append({"id": f"face_under_subtitles:{cid}", "severity": "minor", "status": "warn", "frame": f,
                                "message": f"Visage du sujet bas dans l'image (y={hy:.2f}) : risque de recouvrement par les sous-titres."})
            hm = ch.joints["head"].matrix_world
            fwd = (hm.to_3x3() @ Vector((0, -1, 0))).normalized()
            to_cam = (cam.matrix_world.translation - lm["head"]).normalized()
            if fwd.dot(to_cam) < 0.15:
                out.append({"id": f"face_away:{cid}", "severity": "major" if is_subject else "minor", "status": "fail" if is_subject else "warn", "frame": f,
                            "message": f"Visage de {cid} invisible depuis la caméra (dos ou tête penchée, cos={fwd.dot(to_cam):.2f})."})
            x, y = lm["feet"].x, lm["feet"].y
            b = set_info["bounds"]
            if not (b[0] <= x <= b[1] and b[2] <= y <= b[3]) and in_frame:
                out.append({"id": f"out_of_set:{cid}", "severity": "major", "status": "fail", "frame": f,
                            "message": f"{cid} hors des limites du décor ({x:.2f},{y:.2f})."})
            for so in set_info["solids"]:
                lo, hi = _bbox(so)
                if lo.x + 0.1 < x < hi.x - 0.1 and lo.y + 0.1 < y < hi.y - 0.1 and lm["feet"].z < hi.z - 0.3:
                    out.append({"id": f"inside_furniture:{cid}", "severity": "minor", "status": "warn", "frame": f,
                                "message": f"{cid} semble traverser {so.name} (vérifier si intentionnel : assis/couché)."})
        ids = list(chars)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b2 = chars[ids[i]], chars[ids[j]]
                pa, pb = a.landmarks_world()["hips"], b2.landmarks_world()["hips"]
                lim = (a.torso_w + b2.torso_w) * 0.9
                if (Vector((pa.x, pa.y)) - Vector((pb.x, pb.y))).length < lim and abs(pa.z - pb.z) < 0.5:
                    out.append({"id": f"char_overlap:{ids[i]}:{ids[j]}", "severity": "minor", "status": "warn", "frame": f,
                                "message": f"{ids[i]} et {ids[j]} s'interpénètrent probablement."})
        for pid, st in props_state.items():
            if st.get("held") or st.get("airborne_at", {}).get(f):
                continue
            o = st["obj"]
            if o.scale.x < 0.01:
                continue
            lo, hi = _bbox(o)
            if lo.z > 0.05:
                origin = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.002))
                hit, loc, *_ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), origin, Vector((0, 0, -1)), distance=10)
                gap = (origin.z - loc.z) if hit else origin.z
                if gap > 0.06:
                    out.append({"id": f"floating_prop:{pid}", "severity": "minor", "status": "warn", "frame": f,
                                "message": f"{pid} flotte à {gap:.2f} m au-dessus de son support."})
    for cid, vis in seen_visible.items():
        if not vis:
            out.append({"id": f"char_never_visible:{cid}", "severity": "major", "status": "fail", "frame": sample_frames[0],
                        "message": f"{cid} fait partie du plan mais n'est visible à aucune frame contrôlée."})
    # dédoublonnage (même id) : garder la première occurrence + nombre de frames
    seen = {}
    for c in out:
        if c["id"] in seen:
            seen[c["id"]]["frames"].append(c["frame"])
        else:
            c["frames"] = [c["frame"]]
            seen[c["id"]] = c
    res = list(seen.values())
    for c in res:
        if c["severity"] == "major" and len(c["frames"]) < max(2, len(sample_frames) // 3) and c["id"].startswith(("subject_too_small", "head_cropped", "face_away")):
            c["severity"], c["status"] = "minor", "warn"   # transitoire (ex : saut) : avertissement seulement
    return res


def _bbox(o):
    pts = []
    for ob in [o] + list(o.children_recursive):
        if ob.type == 'MESH':
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    if not pts:
        p = o.matrix_world.translation
        return p.copy(), p.copy()
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
