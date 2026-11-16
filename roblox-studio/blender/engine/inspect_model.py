"""Inspection d'un modèle 3D externe AVANT usage (Blender) : géométrie, matériaux, textures, rig, échelle,
plus une vignette de contrôle rendue sur fond neutre. Ne modifie jamais le fichier source.

Usage : python3 blender/engine/inspect_model.py --model M.glb --out DIR [--target-height 1.0]
        blender -b --factory-startup --python blender/engine/inspect_model.py -- --model ... --out ...
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bpy  # noqa: E402
from engine import core, props, lighting, camera  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-height", type=float, default=0.0)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    sc = core.reset_scene()
    core.setup_render(sc, {"resolution": [360, 640], "cycles_samples": 6, "denoise": True}, "cycles")
    before = set(bpy.data.objects)
    root = props.build("custom", "pr_inspect", None, 1.0, None, None,
                       external={"path": os.path.abspath(a.model), "target_height": a.target_height or None})
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    rep = {"model": os.path.abspath(a.model), "import_ok": not root.get("external_failed", False)}
    if rep["import_ok"]:
        mats = {m for o in new for m in o.data.materials if m}
        imgs = [i for i in bpy.data.images if i.source == 'FILE']
        lo, hi = core.world_bbox(root)
        rep.update({
            "meshes": len(new),
            "faces": sum(len(o.data.polygons) for o in new),
            "vertices": sum(len(o.data.vertices) for o in new),
            "materials": len(mats),
            "textures": len(imgs),
            "missing_textures": [i.filepath for i in imgs if not i.packed_file and not os.path.exists(bpy.path.abspath(i.filepath))],
            "armatures": len([o for o in bpy.data.objects if o.type == 'ARMATURE']),
            "animations": len(bpy.data.actions),
            "dimensions_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
        })
        lighting.setup(sc, "day_warm", center=(0, 0, (hi.z - lo.z) / 2), interior=False)
        floor = core.box("floor", (20, 20, 0.1), core.toon_mat("floor", "#E9E3D5"), (0, 0, -0.05))
        cam_d = bpy.data.cameras.new("CAM")
        cam_d.sensor_fit = 'VERTICAL'
        cam_d.sensor_height = camera.SENSOR_H
        cam = bpy.data.objects.new("CAM", cam_d)
        sc.collection.objects.link(cam)
        sc.camera = cam
        from mathutils import Vector
        h = max(hi.z - lo.z, 0.1)
        w = max(hi.x - lo.x, hi.y - lo.y, 0.1)
        size = max(h, w / camera.ASPECT) * 1.5
        aim = Vector((0, 0, h / 2))
        cam_d.lens = 45
        import math
        d = (size / 2) / math.tan(camera.vfov(45) / 2)
        cam.location = aim + Vector((0.45, -1.0, 0.35)).normalized() * d
        cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(a.out, "thumbnail.png")
        bpy.ops.render.render(write_still=True)
        rep["thumbnail"] = sc.render.filepath
    json.dump(rep, open(os.path.join(a.out, "inspection.json"), "w"), indent=1)
    print("STUDIO_INSPECT_DONE", json.dumps(rep))


if __name__ == "__main__":
    main()
