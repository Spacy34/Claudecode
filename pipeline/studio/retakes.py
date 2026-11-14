"""Retouches ciblées demandées par l'utilisateur : « refaire ce plan » (tableau de bord ou `studio retake`).

episodes/<ep>/retakes.json : [{id, shot, note, at, status: pending|applied|failed, result}]
- L'utilisateur écrit la demande ; le pilote ouvre UNE session Codex courte qui confie chaque retouche au rôle
  propriétaire (director / animator / motion-designer), limité à ce plan ; l'agent marque la retouche faite.
- « Mode finition » (state.finishing) : après une retouche, les critiques ne sont pas relancés et les étapes de
  rédaction en amont ne sont pas refaites (leurs artefacts restent valides) : l'utilisateur est le juge. Le cache
  ne re-rend que les plans modifiés.
"""
import re
from pathlib import Path

from .util import now, read_json, write_json

SHOT_RE = re.compile(r"^sh_[0-9]{3}$")


def path(ep_dir):
    return Path(ep_dir) / "retakes.json"


def load(ep_dir):
    p = path(ep_dir)
    return read_json(p).get("retakes", []) if p.exists() else []


def save(ep_dir, items):
    write_json(path(ep_dir), {"retakes": items})


def request(ep_dir, shot, note):
    if not SHOT_RE.match(shot or ""):
        raise ValueError(f"plan invalide : {shot}")
    note = (note or "").strip()
    if len(note) < 3:
        raise ValueError("décris ce qu'il faut changer dans ce plan")
    items = load(ep_dir)
    rid = f"r{len(items) + 1:03d}"
    items.append({"id": rid, "shot": shot, "note": note[:600], "at": now(), "status": "pending", "result": ""})
    save(ep_dir, items)
    from .state import State
    st = State(ep_dir)
    st.data["finishing"] = True
    st.log("retake_request", retake=rid, shot=shot)
    st.save()
    return rid


def pending(ep_dir):
    return [r for r in load(ep_dir) if r["status"] == "pending"]


def mark(ep_dir, rid_or_shot, status, result=""):
    items = load(ep_dir)
    hit = [r for r in items if r["status"] == "pending" and rid_or_shot in (r["id"], r["shot"])]
    if not hit:
        raise ValueError(f"aucune retouche en attente pour {rid_or_shot}")
    for r in hit:
        r["status"], r["result"] = status, (result or "")[:600]
        r["done_at"] = now()
    save(ep_dir, items)
    return [r["id"] for r in hit]
