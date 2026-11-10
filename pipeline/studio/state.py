"""État persistant du job de production (episodes/<id>/state.json) et DAG des étapes.

- Chaque étape enregistre le hash de ses entrées à la complétion : si une entrée change, l'étape et
  toutes ses descendantes deviennent `stale` (aucune désynchronisation silencieuse).
- Une étape `running` dont le processus n'existe plus devient `interrupted` (reprise propre).
- Les validations humaines sont liées aux hashes des artefacts validés : modifier un artefact
  après validation annule la validation.
"""
import os
from pathlib import Path

from .util import now, read_json, sha256_file, write_json

# nom : (propriétaire, type, entrées (fichiers relatifs à l'épisode), sorties, dépendances d'étapes, gate humaine)
STAGES = {
    "brief":            ("orchestrator", "agent", [], ["episode_brief.json"], [], False),
    "script":           ("story-architect", "agent", ["episode_brief.json"], ["story_script.json"], ["brief"], False),
    "script_review":    ("script-critic", "review", ["story_script.json"], [], ["script"], False),
    "gate_script":      ("human", "gate", ["story_script.json"], [], ["script_review"], True),
    "design":           ("character-artist+environment-artist", "agent", ["story_script.json"], ["cast_bible.json", "asset_manifest.json"], ["gate_script"], False),
    "storyboard":       ("director", "agent", ["story_script.json", "cast_bible.json", "asset_manifest.json"], ["storyboard.json"], ["design"], False),
    "animation":        ("animator", "agent", ["storyboard.json"], ["animation_plan.json"], ["storyboard"], False),
    "voice":            ("pipeline", "auto", ["story_script.json", "cast_bible.json"], ["audio_timeline.json"], ["gate_script"], False),
    "storyboard_review": ("continuity-auditor", "review", ["storyboard.json", "animation_plan.json"], [], ["animation"], False),
    "compile":          ("pipeline", "auto", ["story_script.json", "cast_bible.json", "asset_manifest.json", "storyboard.json", "animation_plan.json", "audio_timeline.json"], ["shot_manifest.json"], ["storyboard_review", "voice"], False),
    "lookdev":          ("pipeline", "auto", ["cast_bible.json", "asset_manifest.json"], ["lookdev/contact_sheet.png"], ["design"], False),
    "gate_lookdev":     ("human", "gate", ["cast_bible.json", "asset_manifest.json"], [], ["lookdev"], True),
    "prototype":        ("pipeline", "auto", ["shot_manifest.json"], ["renders/prototype.mp4"], ["compile", "gate_lookdev"], False),
    "gate_prototype":   ("human", "gate", ["shot_manifest.json"], [], ["prototype"], True),
    "shots_check":      ("pipeline", "auto", ["shot_manifest.json"], ["checks/shots_contact.png"], ["gate_prototype"], False),
    "first_cut":        ("pipeline", "auto", ["shot_manifest.json"], ["renders/first_cut.mp4"], ["shots_check"], False),
    "reviews":          ("visual-critic+continuity-auditor+retention-editor", "review", ["renders/first_cut.mp4"], [], ["first_cut"], False),
    "gate_first_cut":   ("human", "gate", ["renders/first_cut.mp4"], [], ["reviews"], True),
    "final":            ("pipeline", "auto", ["shot_manifest.json"], ["renders/final.mp4"], ["gate_first_cut"], False),
    "delivery":         ("pipeline", "auto", ["renders/final.mp4"], ["episode_manifest.json"], ["final"], False),
}
ORDER = list(STAGES)
DONE = ("completed", "approved")


def _hash_inputs(ep_dir, files):
    out = {}
    for f in files:
        p = Path(ep_dir) / f
        out[f] = sha256_file(p) if p.exists() else None
    return out


def _alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class State:
    def __init__(self, ep_dir, episode_id=None):
        self.dir = Path(ep_dir)
        self.path = self.dir / "state.json"
        if self.path.exists():
            self.data = read_json(self.path)
        else:
            self.data = {"episode_id": episode_id or self.dir.name, "state_version": 1,
                         "stages": {s: {"status": "pending", "attempts": 0, "revision_rounds": 0} for s in ORDER},
                         "approvals": [], "history": [], "cost_log": []}
        for s in ORDER:
            self.data["stages"].setdefault(s, {"status": "pending", "attempts": 0, "revision_rounds": 0})

    def save(self):
        write_json(self.path, self.data)

    def st(self, name):
        return self.data["stages"][name]

    def log(self, event, **kw):
        self.data["history"].append({"at": now(), "event": event, **kw})

    # ------------------------------------------------------------ transitions
    def start(self, name):
        s = self.st(name)
        s.update(status="running", pid=os.getpid(), started_at=now(), error=None)
        s["attempts"] = s.get("attempts", 0) + 1
        self.log("start", stage=name)
        self.save()

    def finish(self, name, status="completed", note=None):
        ins, outs = STAGES[name][2], STAGES[name][3]
        s = self.st(name)
        s.update(status=status, pid=None, finished_at=now(), inputs=_hash_inputs(self.dir, ins), outputs=_hash_inputs(self.dir, outs), note=note)
        self.log("finish", stage=name, status=status)
        self.save()

    def fail(self, name, error):
        s = self.st(name)
        s.update(status="failed", pid=None, finished_at=now(), error=str(error)[-2000:])
        self.log("fail", stage=name, error=str(error)[-300:])
        self.save()

    def approve(self, gate, by, note=""):
        files = STAGES[gate][2]
        hashes = _hash_inputs(self.dir, files)
        if any(v is None for v in hashes.values()):
            raise RuntimeError(f"impossible d'approuver {gate} : artefacts manquants {[k for k, v in hashes.items() if v is None]}")
        self.data["approvals"].append({"gate": gate, "by": by, "at": now(), "note": note, "artifact_hashes": hashes})
        self.finish(gate, "approved", note=f"approuvé par {by}")

    def approval_valid(self, gate):
        cur = _hash_inputs(self.dir, STAGES[gate][2])
        for a in reversed(self.data["approvals"]):
            if a["gate"] == gate:
                return a["artifact_hashes"] == cur
        return False

    def add_cost(self, kind, amount, unit, note=""):
        self.data["cost_log"].append({"at": now(), "kind": kind, "amount": amount, "unit": unit, "note": note})
        self.save()

    # ------------------------------------------------------------ cohérence
    def refresh(self):
        """Détecte interruptions et entrées modifiées ; propage `stale` aux descendants."""
        changed = []
        for name in ORDER:
            s = self.st(name)
            if s["status"] == "running" and not _alive(s.get("pid")):
                s["status"] = "interrupted"
                changed.append((name, "interrupted"))
            if s["status"] in DONE + ("needs_review",):
                cur = _hash_inputs(self.dir, STAGES[name][2])
                if s.get("inputs") and s["inputs"] != cur:
                    s["status"] = "stale"
                    changed.append((name, "stale:inputs"))
                elif STAGES[name][4] and any(self.st(d)["status"] in ("stale", "pending", "failed", "interrupted") for d in STAGES[name][4]):
                    s["status"] = "stale"
                    changed.append((name, "stale:upstream"))
        if changed:
            self.log("refresh", changes=changed)
            self.save()
        return changed

    def ready(self):
        """Étapes dont toutes les dépendances sont satisfaites et qui ne sont pas terminées."""
        out = []
        for name in ORDER:
            s = self.st(name)
            if s["status"] in DONE or s["status"] == "running":
                continue
            if all(self.st(d)["status"] in DONE for d in STAGES[name][4]):
                out.append(name)
        return out

    def summary(self):
        rows = []
        for name in ORDER:
            s = self.st(name)
            owner, kind = STAGES[name][0], STAGES[name][1]
            rows.append((name, s["status"], owner, kind, s.get("attempts", 0), s.get("error") or s.get("note") or ""))
        return rows
