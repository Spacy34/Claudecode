"""Conception sonore automatique : un bruitage discret sur chaque événement visible.

Déterministe, sans token : lit les specs des plans (actions, zooms, accessoires, effets) et le motion design
(téléphone, textes, stickers, compteurs) et pose les bruitages au bon instant. Les bruitages écrits par le
scénariste (story_script.sfx) restent prioritaires ; les automatiques sont plus bas en volume et espacés pour ne
jamais faire « soupe ». Désactivable : config [audio] auto_sfx = false.
"""
from pathlib import Path

from .util import ROOT, read_json

# (bruitage, décalage en images après le début de l'action, gain relatif en dB)
ACTION_SFX = {"jump": ("boing", 6, -4), "shocked_jump": ("boing", 4, -3), "fall_back": ("thud", 12, -2), "slip_fall": ("thud", 12, -2),
              "faint": ("thud", 14, -4), "take_hit": ("bonk", 0, -2), "stomp": ("thud", 8, -6), "throw": ("swish", 10, -6),
              "celebrate": ("sparkle", 2, -8), "turn_to": ("swish", 0, -14)}
PROP_SFX = {"appear": ("pop", 0, -4), "disappear": ("pop", 0, -6), "explode": ("explosion", 3, 0), "fall": ("thud", 8, -4),
            "throw": ("swish", 0, -6), "spin": ("swish", 0, -10)}
FX_SFX = {"impact_star": ("bonk", 0, -6), "sparkles": ("sparkle", 0, -8), "hearts": ("pop", 0, -10), "smoke_puff": ("pop", 0, -12),
          "question_marks": ("pop", 0, -12), "sweat_drops": ("blip", 0, -14)}


def auto_cues(ep_dir, shots, timeline, cfg, existing=()):
    ep_dir = Path(ep_dir)
    sfx_dir = ROOT / cfg["paths"]["assets_dir"] / "sfx"
    base = float(cfg["audio"]["sfx_gain_db"])
    out = []

    def add(name, t, rel_db, source):
        if t < 0:
            return
        out.append({"name": name, "file": str((sfx_dir / f"{name}.wav").relative_to(ROOT)), "start_s": round(t, 3),
                    "gain_db": base + rel_db, "source": f"auto:{source}"})

    for s in shots:
        sp = ep_dir / s.get("spec_path", f"shots/{s['id']}.json")
        if not sp.exists():
            continue
        spec = read_json(sp)
        fps = float(spec.get("fps", 30))
        t0 = float(s["start_s"])
        at = (lambda f: t0 + (float(f) - 1) / fps)
        for a in spec.get("actions", []):
            if a["action"] in ("walk_to", "run_to"):
                dur = max(int(a.get("duration_frames") or 0), int(fps * 0.8))
                step = 0.22 if a["action"] == "run_to" else 0.32
                k = 0.1
                while k < dur / fps:
                    add("step", at(a["frame"]) + k, -14, "pas")
                    k += step
            elif a["action"] in ACTION_SFX:
                n, off, g = ACTION_SFX[a["action"]]
                add(n, at(a["frame"] + off), g, a["action"])
        for p in spec.get("prop_actions", []):
            if p["action"] in PROP_SFX:
                n, off, g = PROP_SFX[p["action"]]
                add(n, at(p["frame"] + off), g, f"objet:{p['action']}")
        for e in spec.get("fx", []):
            if e["type"] in FX_SFX:
                n, off, g = FX_SFX[e["type"]]
                add(n, at(e["frame"] + off), g, f"effet:{e['type']}")
        for pn in spec.get("punches", []):
            add("swish", at(pn["frame"]) - 0.05, -12, "zoom")
        if spec.get("camera", {}).get("move") == "crash_zoom":
            add("whoosh", at(max(2, int(spec["frames"] * 0.35))) - 0.1, -6, "crash_zoom")
    # motion design
    from . import motion
    md = motion.load(ep_dir)
    if md:
        try:
            els = motion.resolve(md, timeline)
        except (KeyError, ValueError, IndexError):
            els = []
        for e in els:
            t = e["_t0"]
            typ = e["type"]
            if typ == "phone":
                add("swish", t, -8, "téléphone")
                scr = e.get("screen", "chat")
                if scr == "call":
                    add("ring", t + 0.2, -8, "appel")
                    if e["_t1"] - t > 2.2:
                        add("ring", t + 1.8, -10, "appel")
                elif scr == "search":
                    add("typing", t + 0.25, -10, "recherche")
                for m in e["_msgs"]:
                    add("ding" if scr == "notification" else "blip", m["t"], -8 if scr == "notification" else -9, f"message:{scr}")
            elif typ in ("text_pop", "sticker"):
                add("pop", t, -7, typ)
            elif typ == "name_tag":
                add("swish", t, -10, typ)
            elif typ == "counter":
                add("count_roll", t + 0.1, -12, "compteur")
                add("ding", t + 0.1 + min(1.2, max(0.4, (e["_t1"] - t) * 0.5)), -10, "compteur")
            elif typ == "arrow":
                add("swish", t + 0.1, -10, typ)
    # pas de doublon avec les bruitages du script ni d'empilement : 0,12 s d'écart mini (les pas exceptés)
    taken = [c["start_s"] for c in existing]
    out.sort(key=lambda c: c["start_s"])
    kept, last = [], -9.0
    for c in out:
        quiet = c["name"] in ("step", "tick")
        if not quiet and (c["start_s"] - last < 0.12 or any(abs(c["start_s"] - x) < 0.15 for x in taken)):
            continue
        kept.append(c)
        if not quiet:
            last = c["start_s"]
    return kept[:120]
