"""Mixage réglable par l'utilisateur (onglet « Mixage » du tableau de bord, `studio mix` / `studio remix`).

Réglages par épisode dans audio/mix.json (fichier de l'utilisateur, jamais écrit par un agent) :
  voice_db / music_db / sfx_db : correction de chaque piste en dB (0 = niveau du studio)
  mute : {"voice", "music", "sfx"} : couper une piste entière
  cues : {"<clé du bruitage>": {"gain_db": x, "mute": bool}} : réglage bruitage par bruitage
`studio remix <ep>` refait le DERNIER montage (prototype, premier montage ou final) avec ces réglages, à partir
des rendus 3D déjà en cache : seul le son (et l'encodage) est refait, l'image ne change pas.
"""
import json
from pathlib import Path

from .util import read_json, write_json

DEFAULT = {"voice_db": 0.0, "music_db": 0.0, "sfx_db": 0.0, "mute": {"voice": False, "music": False, "sfx": False}, "cues": {}}
LIMITS = (-40.0, 12.0)
OUTPUTS = {"final": "renders/final.mp4", "first_cut": "renders/first_cut.mp4", "prototype": "renders/prototype.mp4"}


def path(ep_dir):
    return Path(ep_dir) / "audio" / "mix.json"


def _clamp(v):
    try:
        return max(LIMITS[0], min(LIMITS[1], float(v)))
    except (TypeError, ValueError):
        return 0.0


def load(ep_dir):
    p = path(ep_dir)
    m = json.loads(json.dumps(DEFAULT))
    if p.exists():
        try:
            raw = read_json(p)
        except (OSError, ValueError):
            raw = {}
        for k in ("voice_db", "music_db", "sfx_db"):
            if k in raw:
                m[k] = _clamp(raw[k])
        m["mute"].update({k: bool(v) for k, v in (raw.get("mute") or {}).items() if k in m["mute"]})
        m["cues"] = {str(k): {"gain_db": _clamp(v.get("gain_db", 0.0)), "mute": bool(v.get("mute", False))}
                     for k, v in (raw.get("cues") or {}).items() if isinstance(v, dict)}
    return m


def save(ep_dir, settings):
    m = json.loads(json.dumps(DEFAULT))
    for k in ("voice_db", "music_db", "sfx_db"):
        m[k] = _clamp(settings.get(k, 0.0))
    m["mute"].update({k: bool(v) for k, v in (settings.get("mute") or {}).items() if k in m["mute"]})
    m["cues"] = {str(k): {"gain_db": _clamp(v.get("gain_db", 0.0)), "mute": bool(v.get("mute", False))}
                 for k, v in (settings.get("cues") or {}).items()
                 if isinstance(v, dict) and (v.get("mute") or abs(_clamp(v.get("gain_db", 0.0))) > 0.05)}
    path(ep_dir).parent.mkdir(parents=True, exist_ok=True)
    write_json(path(ep_dir), m)
    return m


def cue_key(c):
    """Identifiant stable d'un bruitage : origine, son et instant (au centième de seconde)."""
    return f"{c.get('source', '?')}|{c.get('name', '?')}|{float(c.get('start_s', 0.0)):.2f}"


def apply(cues, mix):
    """-> bruitages à mixer : piste coupée / bruitage coupé retirés, gains corrigés (piste + bruitage)."""
    if mix["mute"].get("sfx"):
        return []
    out = []
    for c in cues:
        r = mix["cues"].get(cue_key(c), {})
        if r.get("mute"):
            continue
        out.append({**c, "gain_db": float(c.get("gain_db", -8)) + mix["sfx_db"] + float(r.get("gain_db", 0.0))})
    return out


def latest_montage(ep_dir):
    """-> {kind, profile, output} du montage le plus récent encore présent, ou None."""
    ep_dir = Path(ep_dir)
    best = None
    for rm_path in ep_dir.glob("render_manifest_*.json"):
        try:
            rm = read_json(rm_path)
        except (OSError, ValueError):
            continue
        out = rm.get("output")
        if not out or not (ep_dir / out).exists():
            continue
        kind = next((k for k, v in OUTPUTS.items() if v == out), Path(out).stem)
        mt = (ep_dir / out).stat().st_mtime
        if best is None or mt > best["mtime"]:
            best = {"kind": kind, "profile": rm.get("profile"), "output": out, "mtime": mt,
                    "shots": [s["id"] for s in rm.get("shots", [])]}
    return best


def list_cues(ep_dir, cfg):
    """Bruitages du montage, tels qu'ils seront mixés AVANT réglages : pour l'onglet Mixage."""
    from . import compose, sfx as sfxlib
    ep_dir = Path(ep_dir)
    try:
        man = read_json(ep_dir / "shot_manifest.json")
        tl = read_json(ep_dir / "audio_timeline.json")
    except (OSError, ValueError):
        return []
    mix = load(ep_dir)
    out = []
    for c in sorted(compose.sfx_cues(tl, man["shots"], cfg, ep_dir), key=lambda c: c["start_s"]):
        k = cue_key(c)
        r = mix["cues"].get(k, {})
        out.append({"key": k, "t": round(float(c["start_s"]), 2), "name": c.get("name"), "source": c.get("source", ""),
                    "file": c.get("file"), "base_db": round(float(c.get("gain_db", -8)) + sfxlib.trim_db(c.get("name")), 1),
                    "gain_db": r.get("gain_db", 0.0), "mute": r.get("mute", False)})
    return out
