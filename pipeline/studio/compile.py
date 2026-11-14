"""Étape `compile` : storyboard + animation_plan + audio_timeline -> shot_manifest.json + shots/<id>.json.

Seul endroit où les ancrages (réplique/mot) deviennent des frames. Le storyboard ne contient aucun
timecode absolu : modifier une réplique ou la voix recalcule tout le minutage de façon déterministe.
Chaque spec de plan est hachée : seuls les plans dont la spec change sont re-rendus.
"""
import math
import sys
from pathlib import Path

from .contracts import CONTRACT_VERSION, provenance_deps
from .util import ROOT, now, read_json, sha256_file, sha256_json, write_json

sys.path.insert(0, str(ROOT / "blender"))
from engine import kitdata, registry  # noqa: E402

MIN_SHOT_S, LONG_SHOT_S = 0.5, 4.0   # montage nerveux : au-delà de 4 s, avertir


class CompileError(Exception):
    pass


def _anchor_time(at, words_by_line, segs, shot_t0, shot_t1):
    if "shot_t" in at:
        return shot_t0 + (shot_t1 - shot_t0) * at["shot_t"]
    seg = segs[at["line"]]
    if "word" in at:
        w = words_by_line[at["line"]][at["word"]]
        t = w["end_s"] if at.get("edge") == "end" else w["start_s"]
    else:
        t = seg["end_s"] if at.get("edge") == "end" else seg["start_s"]
    return t + at.get("offset_s", 0.0)


def compile_episode(ep_dir, cfg):
    ep_dir = Path(ep_dir)
    fps = int(cfg["render"]["fps"])
    script = read_json(ep_dir / "story_script.json")
    cast = {c["id"]: c for c in read_json(ep_dir / "cast_bible.json")["characters"]}
    assets = read_json(ep_dir / "asset_manifest.json")
    sets_ = {s["id"]: s for s in assets["sets"]}
    props_ = {p["id"]: p for p in assets["props"]}
    sb = read_json(ep_dir / "storyboard.json")
    ap = read_json(ep_dir / "animation_plan.json")
    tl = read_json(ep_dir / "audio_timeline.json")
    segs = {s["line_id"]: s for s in tl["segments"]}
    words = {s["line_id"]: s["words"] for s in tl["segments"]}
    # fraîcheur : la timeline doit correspondre au texte actuel du script
    for l in script["lines"]:
        if l["id"] not in segs or segs[l["id"]]["text_sha256"] != sha256_json(l["text"]):
            raise CompileError(f"audio_timeline obsolète pour {l['id']} : relancer `studio voice`")
        from .audio import is_emphasis
        want = {w["i"] for w in segs[l["id"]]["words"] if is_emphasis(w["text"], w["i"], set(l.get("emphasis_words", [])))}
        have = {w["i"] for w in segs[l["id"]]["words"] if w.get("emph")}
        if want != have:
            raise CompileError(f"mots forts modifiés pour {l['id']} : relancer `studio voice`")
    duration = tl["duration_s"]
    total_frames = int(math.ceil(duration * fps))
    shots = sb["shots"]
    starts = []
    for i, s in enumerate(shots):
        if i == 0:
            starts.append(0.0)
            continue
        st = s.get("start") or {"line": s["line_ids"][0]}
        t = _anchor_time(st, words, segs, 0, 0)
        if "word" not in st and "shot_t" not in st:
            t -= 0.12   # couper juste avant la première syllabe
        starts.append(t)
    warnings = []
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            raise CompileError(f"{shots[i]['id']} commence avant ou en même temps que {shots[i - 1]['id']} : vérifier l'ordre/ancrages")
    f_starts = [int(round(t * fps)) for t in starts] + [total_frames]
    manifest_shots = []
    shots_dir = ep_dir / "shots"
    shots_dir.mkdir(exist_ok=True)
    for i, s in enumerate(shots):
        f0, f1 = f_starts[i], f_starts[i + 1]
        N = f1 - f0
        t0, t1 = f0 / fps, f1 / fps
        if N / fps < MIN_SHOT_S:
            warnings.append(f"{s['id']} très court ({N / fps:.2f}s)")
        if N / fps > LONG_SHOT_S:
            warnings.append(f"{s['id']} long ({N / fps:.1f}s) : risque de baisse de rétention, envisager un découpage")
        loc = (lambda t: max(1, min(N, int(round((t - t0) * fps)) + 1)))
        set_spec = sets_[s["set_id"]]
        marks = _marks(set_spec)

        def resolve(t):
            if t is None:
                return None
            if isinstance(t, list):
                return [float(t[0]), float(t[1])]
            if t.startswith("ch_"):
                return {"kind": "char", "id": t}
            if t.startswith("pr_"):
                return {"kind": "prop", "id": t}
            if t in marks:
                return [marks[t][0], marks[t][1]]
            raise CompileError(f"{s['id']} : cible inconnue '{t}' (marks disponibles : {sorted(marks)})")

        chars = []
        for c in s["characters"]:
            pos = resolve(c["mark"])
            if not isinstance(pos, list):
                raise CompileError(f"{s['id']} : la position de {c['id']} doit être un mark ou [x,y]")
            fac = c.get("facing", "camera")
            facing_deg, facing_target = 0.0, None
            if isinstance(fac, (int, float)):
                facing_deg = float(fac)
            elif fac != "camera":
                ft = resolve(fac)
                if isinstance(ft, dict):
                    pool = s["characters"] if ft["kind"] == "char" else s.get("props", [])
                    other = next((o for o in pool if o["id"] == ft["id"]), None)
                    if other is None or not other.get("mark"):
                        raise CompileError(f"{s['id']} : {c['id']} regarde {ft['id']} qui n'a pas de position dans le plan")
                    ft = resolve(other["mark"])
                facing_target = ft
            chars.append({"id": c["id"], "design": cast[c["id"]]["design"], "pos": pos, "facing_deg": facing_deg, "facing_target": facing_target,
                          "start_pose": c.get("start_pose", "stand"), "offscreen": bool(c.get("offscreen", False))})
        props = []
        for p in s.get("props", []):
            a = props_[p["id"]]
            pos = resolve(p["mark"]) if p.get("mark") else None
            if isinstance(pos, dict):
                raise CompileError(f"{s['id']} : position d'accessoire invalide")
            ext_abs = None
            if a.get("external_path"):
                ext_abs = str((ROOT / "assets" / a["external_path"]).resolve())
            props.append({"id": p["id"], "type": a["type"], "color": a.get("color"), "scale": a.get("scale", 1.0), "label": a.get("label"),
                          "parts": a.get("parts"), "external_path_abs": ext_abs, "target_height": a.get("target_height"),
                          "rot_offset_deg": a.get("rot_offset_deg", 0.0),
                          "external_sha256": sha256_file(ROOT / "assets" / a["external_path"]) if a.get("external_path") else None,
                          "pos": pos, "height": p.get("height", 0.0), "held_by": p.get("held_by"), "hand": p.get("hand", "R"), "rot_deg": p.get("rot_deg", 0.0)})
        block = ap["shots"].get(s["id"], {})
        T = (lambda at: loc(_anchor_time(at, words, segs, t0, t1)))
        actions = [{"char": a["char"], "action": a["action"], "frame": T(a["at"]), "duration_frames": int(round(a.get("duration_s", 0) * fps)),
                    "intensity": a.get("intensity", 1.0), "target": resolve(a.get("target")), "prop": a.get("prop")} for a in block.get("actions", [])]
        exprs = [{"char": e["char"], "expr": e["expr"], "frame": T(e["at"]), "intensity": e.get("intensity", 1.0)} for e in block.get("expressions", [])]
        pacts = [{"prop": p["prop"], "action": p["action"], "frame": T(p["at"]), "duration_frames": int(round(p.get("duration_s", 0) * fps)),
                  "char": p.get("char"), "hand": p.get("hand", "R"), "target": resolve(p.get("target"))} for p in block.get("props", [])]
        fxs = []
        for e in block.get("fx", []):
            tg = resolve(e["target"])
            fxs.append({"type": e["type"], "frame": T(e["at"]), "scale": e.get("scale", 1.0),
                        "target": tg if isinstance(tg, dict) else {"kind": "point", "pos": [tg[0], tg[1], 1.0]}})
        present = {c["id"] for c in s["characters"]}
        talkers = {}
        for line in script["lines"]:
            spk = line["speaker"]
            if spk in present:
                talkers.setdefault(spk, []).append(line["id"])
        for t in block.get("talk", []):
            talkers.setdefault(t["char"], []).append(t["line"])
        talk = []
        for cid, lids in talkers.items():
            ws = []
            for lid in lids:
                for w in words[lid]:
                    if t0 <= w["start_s"] < t1:
                        ws.append([loc(w["start_s"]), loc(w["end_s"])])
            if ws:
                talk.append({"char": cid, "words": ws})
        # zooms « punch » sur les mots forts du plan : 2 max par plan, espacés d'au moins 1,5 s
        punches = []
        if s["camera"].get("move", "static") not in ("crash_zoom",):
            for lid in s["line_ids"]:
                for w in words[lid]:
                    if w.get("emph") and t0 + 0.25 <= w["start_s"] < t1 - 0.3:
                        fr = loc(w["start_s"])
                        if all(abs(fr - q["frame"]) > fps * 1.5 for q in punches) and len(punches) < 2:
                            punches.append({"frame": fr, "strength": 1.0, "word": w["text"]})
        cam = dict(s["camera"])
        cam["subject"] = resolve(cam["subject"]) if not isinstance(resolve(cam["subject"]), list) else {"kind": "point", "pos": resolve(cam["subject"]) + [1.0]}
        if cam.get("secondary_subject") is not None:
            sec = resolve(cam["secondary_subject"])
            cam["secondary_subject"] = sec if isinstance(sec, dict) else {"kind": "point", "pos": sec + [1.0]}
        spec = {"shot_id": s["id"], "episode_id": script["episode_id"], "fps": fps, "frames": N, "engine_version": registry.ENGINE_VERSION,
                "set": set_spec, "mood": s["mood"], "characters": chars, "props": props, "camera": cam, "actions": actions,
                "expressions": exprs, "prop_actions": pacts, "fx": fxs, "talk": talk, "punches": punches, "auto_idle": block.get("auto_idle", True),
                "transition_out": s.get("transition_out", "cut")}
        h = sha256_json(spec)
        sp = shots_dir / f"{s['id']}.json"
        write_json(sp, spec)
        manifest_shots.append({"id": s["id"], "start_frame": f0, "end_frame": f1, "frames": N, "start_s": round(t0, 3), "end_s": round(t1, 3),
                               "spec_sha256": h, "spec_path": str(sp.relative_to(ep_dir)), "line_ids": s["line_ids"],
                               "transition_out": s.get("transition_out", "cut")})
    tight = [s["id"] for s in shots if s["camera"]["framing"] in ("close_up", "extreme_close_up")]
    if len(shots) >= 5 and len(tight) > 0.35 * len(shots):
        warnings.append(f"{len(tight)}/{len(shots)} plans en gros plan ou très gros plan : trop serré, alterner avec medium / medium_close / wide")
    for a, b in zip(shots, shots[1:]):
        if a["camera"]["framing"] in ("close_up", "extreme_close_up") and b["camera"]["framing"] in ("close_up", "extreme_close_up"):
            warnings.append(f"{a['id']} et {b['id']} : deux gros plans d'affilée, respirer avec un plan plus large")
    for a, b in zip(shots, shots[1:]):
        if a["camera"]["framing"] == b["camera"]["framing"] and a["camera"]["subject"] == b["camera"]["subject"] and a["set_id"] == b["set_id"]:
            warnings.append(f"{a['id']} et {b['id']} : même cadrage sur le même sujet (plans quasi identiques) : varier la valeur de plan ou l'angle")
    for old in shots_dir.glob("*.json"):
        if old.stem not in {s["id"] for s in shots}:
            old.unlink()
    man = {"contract": "shot_manifest", "contract_version": CONTRACT_VERSION, "episode_id": script["episode_id"], "status": "generated",
           "provenance": {"created_by": "studio compile", "created_at": now(),
                          "depends_on": provenance_deps(ep_dir, ["story_script", "cast_bible", "asset_manifest", "storyboard", "animation_plan", "audio_timeline"])},
           "fps": fps, "total_frames": total_frames, "shots": manifest_shots, "warnings": warnings}
    write_json(ep_dir / "shot_manifest.json", man)
    return man


def _marks(set_spec):
    m = dict(kitdata.BASE_MARKS)
    m.update(kitdata.KIT_MARKS[set_spec["kit"]])
    m.update({k: tuple(v) for k, v in set_spec.get("marks", {}).items()})
    return m
