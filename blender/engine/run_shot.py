"""Point d'entrée Blender : construit et rend UN plan à partir de sa spec résolue (shots/<id>.json).

Usage :
  blender -b --factory-startup -noaudio --python blender/engine/run_shot.py -- --spec S --out DIR --profile P.json [--mode render|stills|blend]
  python3 blender/engine/run_shot.py --spec S --out DIR --profile P.json        (module pip `bpy`)

Sorties dans DIR : f0001.png..., scene_report.json (contrôles + métadonnées), done.json en cas de succès.
Reprise : en mode render, les frames déjà présentes sont sautées.
"""
import argparse
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from engine import core, characters, animation, sets, props, lighting, camera, fx, checks, registry  # noqa: E402

D = math.radians


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--mode", default="render", choices=["render", "stills", "blend"])
    ap.add_argument("--frames", default="", help="liste de frames locales pour --mode stills (ex: 1,24,48)")
    ap.add_argument("--engine", default="cycles", choices=["cycles", "eevee"])
    ap.add_argument("--threads", type=int, default=0)
    return ap.parse_args(argv)


class Shot:
    def __init__(self, spec, profile, engine, threads):
        self.spec = spec
        self.N = int(spec["frames"])
        self.fps = int(spec["fps"])
        core.OUTLINES_ENABLED = bool(profile.get("outlines", True))
        self.sc = core.reset_scene()
        self.sc.frame_start, self.sc.frame_end = 1, self.N
        self.render_engine = core.setup_render(self.sc, dict(profile, fps=self.fps), engine, threads)
        self.anim = animation.Animator(self.fps)
        self.chars, self.cas, self.props, self.props_state = {}, {}, {}, {}
        self.report = {"shot_id": spec["shot_id"], "events": [], "warnings": []}

    # ------------------------------------------------------------ résolution des cibles
    def target_xy(self, t, f=1):
        if t is None:
            return None
        if isinstance(t, (list, tuple)):
            return Vector((t[0], t[1]))
        k = t.get("kind")
        if k == "char":
            return self.cas[t["id"]].root_xy(f)
        if k == "prop":
            o = self.props[t["id"]]
            return Vector((o.location.x, o.location.y))
        if k == "point":
            return Vector((t["pos"][0], t["pos"][1]))
        return None

    def target_world(self, t, f):
        """Position monde évaluée (scène positionnée à f)."""
        k = t.get("kind")
        if k == "char":
            return self.chars[t["id"]].landmarks_world()["head"]
        if k == "prop":
            lo, hi = core.world_bbox(self.props[t["id"]])
            return Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z + 0.1))
        p = t["pos"]
        return Vector((p[0], p[1], p[2] if len(p) > 2 else 1.0))

    # ------------------------------------------------------------ construction
    def build(self):
        sp = self.spec
        self.set = sets.build_set(sp["set"])
        cam_d = bpy.data.cameras.new("CAM")
        cam_d.sensor_fit = 'VERTICAL'
        cam_d.sensor_height = camera.SENSOR_H
        cam_d.clip_start, cam_d.clip_end = 0.05, 300
        self.cam = bpy.data.objects.new("CAM", cam_d)
        self.sc.collection.objects.link(self.cam)
        self.sc.camera = self.cam
        col = bpy.data.collections.new("CAST")
        self.sc.collection.children.link(col)
        for i, c in enumerate(sp["characters"]):
            ch = characters.Character(c["id"], c["design"], col)
            x, y = c["pos"]
            if c.get("facing_target") is not None:
                tx, ty = c["facing_target"]
                fr = math.atan2(tx - x, -(ty - y))
            else:
                fr = D(c.get("facing_deg") or 0.0)
            ch.place(x, y, fr)
            self.chars[c["id"]] = ch
            ca = animation.CharAnim(self.anim, ch, self.N, seed=i + 1)
            root = ch.joints["root"]
            for ax, v in ((0, x), (1, y), (2, 0.0)):
                self.anim.key(root, 'location', ax, 1, v)
            self.anim.key(root, 'rotation_euler', 2, 1, fr)
            self.anim.key(root, 'rotation_euler', 0, 1, 0.0)
            self.cas[c["id"]] = ca
        pcol = bpy.data.collections.new("PROPS")
        self.sc.collection.children.link(pcol)
        for p in sp.get("props", []):
            o = props.build(p["type"], p["id"], p.get("color"), p.get("scale", 1.0), p.get("label"), pcol)
            pos = p.get("pos") or [0, 0]
            o.location = (pos[0], pos[1], p.get("height", 0.0))
            o.rotation_euler = (0, 0, D(p.get("rot_deg", 0.0)))
            self.props[p["id"]] = o
            self.props_state[p["id"]] = {"obj": o, "held": p.get("held_by"), "hand": p.get("hand", "R"), "airborne_at": {}}
        lighting.setup(self.sc, sp["mood"], center=(0, 0.5, 1.0), interior=self.set["interior"])

    # ------------------------------------------------------------ animation personnages
    def animate_characters(self):
        sp = self.spec
        for cid, ca in self.cas.items():
            if sp.get("auto_idle", True):
                ca.idle(1, self.N)
            start = next((c.get("start_pose") for c in sp["characters"] if c["id"] == cid), "stand")
            if start == "sit":
                ca.act_sit(1, 1, 1.0, None, None)
            elif start == "lying":
                ca._fall(1, 1.0)
        for a in sorted(sp.get("actions", []), key=lambda a: a["frame"]):
            ca = self.cas.get(a["char"])
            if ca is None:
                self.report["warnings"].append(f"action sur personnage absent : {a}")
                continue
            tgt = a.get("target")
            txy = self.target_xy(tgt, a["frame"]) if tgt is not None else None
            if a["action"] == "sit" and tgt is not None:
                txy = None
            ca.do(a["action"], int(a["frame"]), int(a.get("duration_frames") or 0), float(a.get("intensity", 1.0)), txy)
        for cid, ca in self.cas.items():
            exprs = sorted([e for e in sp.get("expressions", []) if e["char"] == cid], key=lambda e: e["frame"])
            if not exprs or exprs[0]["frame"] > 1:
                ca.expression(1, "neutral", 1.0, ramp=0)
            for e in exprs:
                ca.expression(int(e["frame"]), e["expr"], float(e.get("intensity", 1.0)))
        for t in sp.get("talk", []):
            if t["char"] in self.cas:
                self.cas[t["char"]].talk([tuple(w) for w in t["words"]])
        for ca in self.cas.values():
            ca.blinks(1, self.N)
            self.report["events"] += [{"char": ca.c.id, "frame": f, "what": w} for f, w in ca.events]
        self.anim.apply()

    # ------------------------------------------------------------ accessoires (cuits frame par frame)
    def animate_props(self):
        pa = animation.Animator(self.fps)
        acts = sorted(self.spec.get("prop_actions", []), key=lambda a: a["frame"])
        by_prop = {}
        for a in acts:
            by_prop.setdefault(a["prop"], []).append(a)
        for pid, st in self.props_state.items():
            o = st["obj"]
            seq = by_prop.get(pid, [])
            holder, hand = st["held"], st["hand"]
            events = {a["frame"]: a for a in seq}
            ballistic = None
            visible = True
            if any(a["action"] == "appear" for a in seq):
                visible = False
                for i in range(3):
                    pa.key(o, 'scale', i, 1, 0.001, 'CONSTANT')
            for f in range(1, self.N + 1):
                a = events.get(f)
                if a:
                    act = a["action"]
                    if act == "attach":
                        holder, hand = a.get("char"), a.get("hand", "R")
                    elif act in ("detach", "fall"):
                        holder = None
                        ballistic = self._drop(o, f) if act == "fall" or o.location.z > 0.05 else None
                    elif act == "throw":
                        holder = None
                        tgt = self.target_xy(a.get("target"), f) or Vector((o.location.x, o.location.y - 2))
                        dur = int(a.get("duration_frames") or 14)
                        ballistic = (f, f + dur, o.location.copy(), Vector((tgt.x, tgt.y, 0.0)), 1.2)
                    elif act in ("appear", "disappear"):
                        for i in range(3):
                            pa.key(o, 'scale', i, f - 1, 0.001 if act == "appear" else o.scale[i], 'CONSTANT' if act == "appear" else 'BEZIER')
                            pa.key(o, 'scale', i, f + 3, 1.15 if act == "appear" else 0.001)
                            if act == "appear":
                                pa.key(o, 'scale', i, f + 5, 1.0)
                    elif act == "explode":
                        for i in range(3):
                            pa.key(o, 'scale', i, f, o.scale[i])
                            pa.key(o, 'scale', i, f + 3, o.scale[i] * 1.35)
                            pa.key(o, 'scale', i, f + 4, 0.001, 'CONSTANT')
                        self.spec.setdefault("fx", []).append({"type": "explosion", "frame": f + 3, "target": {"kind": "point", "pos": list(o.location + Vector((0, 0, 0.2)))}, "scale": 0.8})
                    elif act == "shake":
                        base = o.location.copy()
                        for k in range(0, int(a.get("duration_frames") or 12), 2):
                            for ax in (0, 1):
                                pa.key(o, 'location', ax, f + k, base[ax] + (0.02 if (k // 2) % 2 else -0.02))
                        for ax in (0, 1):
                            pa.key(o, 'location', ax, f + int(a.get("duration_frames") or 12), base[ax])
                    elif act == "spin":
                        dur = int(a.get("duration_frames") or 20)
                        pa.key(o, 'rotation_euler', 2, f, o.rotation_euler.z)
                        pa.key(o, 'rotation_euler', 2, f + dur, o.rotation_euler.z + D(720))
                if holder and holder in self.chars:
                    self.sc.frame_set(f)
                    hj = self.chars[holder].joints[f"hand_{hand}"]
                    p = hj.matrix_world @ Vector((0, -0.05, -0.09 * self.chars[holder].H))
                    p.z -= 0.05
                    rz = self.chars[holder].joints["root"].matrix_world.to_euler().z
                    for ax in range(3):
                        pa.key(o, 'location', ax, f, p[ax], 'LINEAR')
                    pa.key(o, 'rotation_euler', 2, f, rz, 'LINEAR')
                    o.location = p
                    st["held"] = holder
                elif ballistic:
                    f0, f1, p0, p1, apex = ballistic
                    u = min(1.0, (f - f0) / float(max(1, f1 - f0)))
                    pos = p0.lerp(p1, u)
                    pos.z += math.sin(math.pi * u) * apex
                    for ax in range(3):
                        pa.key(o, 'location', ax, f, pos[ax], 'LINEAR')
                    pa.key(o, 'rotation_euler', 0, f, D(540) * u, 'LINEAR')
                    st["airborne_at"][f] = True
                    o.location = pos
                    if u >= 1.0:
                        ballistic = None
                        st["held"] = None
                else:
                    if st["held"]:
                        st["held"] = None
        pa.apply()

    def _drop(self, o, f):
        p0 = o.location.copy()
        dg = bpy.context.evaluated_depsgraph_get()
        hit, loc, *_ = self.sc.ray_cast(dg, p0 + Vector((0, 0, -0.01)), Vector((0, 0, -1)), distance=10)
        zf = loc.z if hit else 0.0
        return (f, f + 8, p0, Vector((p0.x, p0.y, zf)), 0.05)

    # ------------------------------------------------------------ effets
    def add_fx(self):
        fa = animation.Animator(self.fps)
        col = bpy.data.collections.new("FX")
        self.sc.collection.children.link(col)
        for i, e in enumerate(self.spec.get("fx", [])):
            self.sc.frame_set(int(e["frame"]))
            at = self.target_world(e["target"], int(e["frame"]))
            fx.spawn(e["type"], fa, at, int(e["frame"]), self.cam, float(e.get("scale", 1.0)), col, seed=i)
        fa.apply()

    # ------------------------------------------------------------ caméra
    def _subject_fn(self, t):
        if t is None:
            return None

        def fn(f):
            self.sc.frame_set(f)
            k = t.get("kind")
            if k == "char" and t["id"] in self.chars:
                ch = self.chars[t["id"]]
                return {"kind": "char", "lm": ch.landmarks_world(), "head_r": ch.head_r, "facing": ch.facing_vector()}
            if k == "prop" and t["id"] in self.props:
                return {"kind": "bbox", "bbox": core.world_bbox(self.props[t["id"]])}
            p = t.get("pos", [0, 0, 1])
            return {"kind": "point", "point": Vector((p[0], p[1], p[2] if len(p) > 2 else 1.0))}
        return fn

    def _occluder(self, aim, direction, dist):
        dg = bpy.context.evaluated_depsgraph_get()
        org = aim + direction * 0.3
        rem = dist - 0.3
        travelled = 0.3
        char_prefix = tuple(c + "_" for c in self.chars)
        prop_prefix = tuple(self.props) or ("\0",)
        for _ in range(16):
            hit, loc, nrm, idx, ob, mw = self.sc.ray_cast(dg, org, direction, distance=rem)
            if not hit:
                return None
            step = (loc - org).length
            travelled += step
            name = ob.name if ob else ""
            if name.startswith(char_prefix) or name.startswith("fx_") or name.startswith(prop_prefix) or "floor" in name or "ground" in name or "rug" in name or "_fl" in name:
                org = loc + direction * 0.02
                rem -= step + 0.02
                travelled += 0.02
                if rem <= 0:
                    return None
                continue
            return travelled
        return None

    def setup_camera(self):
        cs = self.spec["camera"]
        rig = camera.CameraRig(self.cam, animation.Animator(self.fps), self.N, seed=7)
        subj = self._subject_fn(cs["subject"])
        sec = self._subject_fn(cs.get("secondary_subject"))
        move = cs.get("move", "static")
        if move == "track_subject":
            for f in list(range(1, self.N + 1, 4)) + [self.N]:
                pos, aim, lens, roll = rig.solve(cs, subj, sec, f, self._occluder, 0.0)
                rig.key(f, pos, aim, lens, roll)
        elif move == "crash_zoom":
            fz = max(2, int(self.N * 0.35))
            for f, t in ((1, 0.0), (fz, 0.0), (min(self.N, fz + 5), 1.0), (self.N, 1.0)):
                pos, aim, lens, roll = rig.solve(cs, subj, sec, f, self._occluder, t)
                rig.key(f, pos, aim, lens, roll)
        else:
            p0 = rig.solve(cs, subj, sec, 1, self._occluder, 0.0)
            p1 = rig.solve(cs, subj, sec, self.N, self._occluder, 1.0)
            if move in ("static", "shake", "handheld"):
                p1 = (p0[0], p0[1], p0[2], p0[3])   # cadre fixe : pas de dérive si le sujet bouge peu
            rig.key(1, *p0)
            rig.key(self.N, *p1)
        self.cam.data.lens = rig.keys[0][3]
        if move == "shake":
            impacts = [a["frame"] for a in self.spec.get("actions", []) if a["action"] in ("take_hit", "fall_back", "slip_fall", "stomp", "shocked_jump")]
            impacts += [e["frame"] for e in self.spec.get("fx", []) if e["type"] in ("explosion", "impact_star")]
            rig.add_shake(min(impacts) if impacts else max(1, self.N // 3), 14, 2.5)
        if move == "handheld":
            rig.add_handheld()
        rig.a.apply()
        self.report["camera"] = {"framing": cs["framing"], "move": move, "lens": rig.keys[0][3],
                                 "keys": [{"frame": k[0], "pos": [round(v, 3) for v in k[1]], "aim": [round(v, 3) for v in k[2]]} for k in rig.keys[:8]]}

    # ------------------------------------------------------------ contrôles
    def run_checks(self):
        acts = sorted({a["frame"] for a in self.spec.get("actions", [])})
        sample = sorted({1, max(1, self.N // 2), self.N} | {min(self.N, f + 8) for f in acts})
        res = checks.run(self.sc, self.cam, self.chars, self.props_state, self.set, self.spec, sample)
        self.report["checks"] = res
        self.report["sample_frames"] = sample


def main():
    args = parse()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    spec = json.load(open(args.spec))
    profile = json.load(open(args.profile)) if os.path.exists(args.profile) else json.loads(args.profile)
    report_path = os.path.join(args.out, "scene_report.json")
    try:
        shot = Shot(spec, profile, args.engine, args.threads)
        shot.build()
        shot.animate_characters()
        shot.animate_props()
        shot.setup_camera()
        shot.add_fx()
        shot.run_checks()
        rep = shot.report
        rep.update({"blender_version": bpy.app.version_string, "engine_version": registry.ENGINE_VERSION,
                    "render_engine": shot.render_engine, "frames": shot.N, "build_seconds": round(time.time() - t0, 2)})
        sc = shot.sc
        if args.mode == "blend":
            bpy.ops.wm.save_as_mainfile(filepath=os.path.join(args.out, f"{spec['shot_id']}.blend"))
        else:
            if args.mode == "stills":
                frames = [int(x) for x in args.frames.split(",") if x.strip()] or rep["sample_frames"]
            else:
                step = int(profile.get("render_every_n_frames", 1))
                frames = list(range(1, shot.N + 1, step))
                if frames[-1] != shot.N:
                    frames.append(shot.N)
            t1 = time.time()
            done = 0
            for f in frames:
                path = os.path.join(args.out, f"f{f:04d}.png")
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    continue
                sc.frame_set(f)
                sc.render.filepath = path + ".tmp.png"
                bpy.ops.render.render(write_still=True)
                os.replace(path + ".tmp.png", path)
                done += 1
            rep["rendered_frames"] = frames
            rep["render_seconds"] = round(time.time() - t1, 2)
            rep["seconds_per_frame"] = round((time.time() - t1) / max(1, done), 3)
        json.dump(rep, open(report_path, "w"), indent=1, default=str)
        json.dump({"ok": True, "mode": args.mode, "seconds": round(time.time() - t0, 2)}, open(os.path.join(args.out, "done.json"), "w"))
        print("STUDIO_SHOT_OK", spec["shot_id"])
    except Exception as e:
        json.dump({"ok": False, "error": repr(e), "traceback": traceback.format_exc()}, open(report_path, "w"), indent=1)
        print("STUDIO_SHOT_FAIL", repr(e))
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
