"""État persistant du job de production (episodes/<id>/state.json) et DAG des étapes.

- Chaque étape enregistre le hash de ses entrées à la complétion : si une entrée change, l'étape et
  toutes ses descendantes deviennent `stale` (aucune désynchronisation silencieuse).
- Une étape `running` sans verrou d'exécution actif devient `interrupted` (reprise propre). Verrou de fichier
  (flock / msvcrt) et non PID : les commandes lancées depuis le bac à sable de Codex vivent dans un autre espace de
  PID, un PID y serait invisible et l'étape serait déclarée interrompue à tort (constaté sur VPS, correctif proposé par Codex).
- Les validations humaines sont liées aux hashes des artefacts validés : modifier un artefact
  après validation annule la validation.
"""
import errno
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
    "motion":           ("motion-designer", "agent", ["story_script.json", "storyboard.json"], ["motion_design.json"], ["storyboard"], False),
    "voice":            ("pipeline", "auto", ["story_script.json", "cast_bible.json"], ["audio_timeline.json"], ["gate_script"], False),
    "storyboard_review": ("continuity-auditor", "review", ["storyboard.json", "animation_plan.json"], [], ["animation"], False),
    "compile":          ("pipeline", "auto", ["story_script.json", "cast_bible.json", "asset_manifest.json", "storyboard.json", "animation_plan.json", "audio_timeline.json"], ["shot_manifest.json"], ["storyboard_review", "voice"], False),
    "lookdev":          ("pipeline", "auto", ["cast_bible.json", "asset_manifest.json"], ["lookdev/contact_sheet.png"], ["design"], False),
    "gate_lookdev":     ("human", "gate", ["cast_bible.json", "asset_manifest.json"], [], ["lookdev"], True),
    "prototype":        ("pipeline", "auto", ["shot_manifest.json"], ["renders/prototype.mp4"], ["compile", "gate_lookdev"], False),
    "gate_prototype":   ("human", "gate", ["shot_manifest.json"], [], ["prototype"], True),
    "shots_check":      ("pipeline", "auto", ["shot_manifest.json"], ["checks/shots_contact.png"], ["gate_prototype"], False),
    "first_cut":        ("pipeline", "auto", ["shot_manifest.json", "motion_design.json"], ["renders/first_cut.mp4"], ["shots_check", "motion"], False),
    "reviews":          ("visual-critic+continuity-auditor+retention-editor", "review", ["renders/first_cut.mp4"], [], ["first_cut"], False),
    "gate_first_cut":   ("human", "gate", ["renders/first_cut.mp4"], [], ["reviews"], True),
    "final":            ("pipeline", "auto", ["shot_manifest.json", "motion_design.json"], ["renders/final.mp4"], ["gate_first_cut"], False),
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


def _lock(handle, blocking=False):
    """Verrouille une étape entre processus (y compris d'espaces de PID différents) via le système de fichiers."""
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))


def _unlock(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class State:
    def __init__(self, ep_dir, episode_id=None):
        self.dir = Path(ep_dir)
        self.path = self.dir / "state.json"
        self._stage_locks = {}
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
    # ------------------------------------------------------------ verrous d'exécution
    def _lock_path(self, name):
        return self.dir / ".studio_locks" / f"{name}.lock"

    def _acquire_stage_lock(self, name):
        path = self._lock_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        try:
            _lock(handle)
        except OSError:
            handle.close()
            raise RuntimeError(f"{name} est déjà exécutée par un autre processus")
        self._stage_locks[name] = handle

    def _release_stage_lock(self, name):
        handle = self._stage_locks.pop(name, None)
        if handle is not None:
            try:
                _unlock(handle)
            finally:
                handle.close()

    def _stage_lock_active(self, name):
        path = self._lock_path(name)
        if not path.exists():
            return False   # anciens enregistrements « running » d'avant les verrous
        with path.open("a+b") as handle:
            try:
                _lock(handle)
            except OSError as e:
                if isinstance(e, BlockingIOError) or e.errno in (errno.EACCES, errno.EAGAIN):
                    return True
                raise
            _unlock(handle)
            return False

    # ------------------------------------------------------------ transitions
    def start(self, name):
        self._acquire_stage_lock(name)
        s = self.st(name)
        try:
            s.update(status="running", pid=os.getpid(), started_at=now(), error=None)
            s["attempts"] = s.get("attempts", 0) + 1
            self.log("start", stage=name)
            self.save()
        except BaseException:
            self._release_stage_lock(name)
            raise

    def finish(self, name, status="completed", note=None):
        ins, outs = STAGES[name][2], STAGES[name][3]
        s = self.st(name)
        try:
            s.update(status=status, pid=None, finished_at=now(), inputs=_hash_inputs(self.dir, ins), outputs=_hash_inputs(self.dir, outs), note=note)
            self.log("finish", stage=name, status=status)
            self.save()
        finally:
            self._release_stage_lock(name)

    def fail(self, name, error):
        s = self.st(name)
        try:
            s.update(status="failed", pid=None, finished_at=now(), error=str(error)[-2000:])
            self.log("fail", stage=name, error=str(error)[-300:])
            self.save()
        finally:
            self._release_stage_lock(name)

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
            if s["status"] == "running" and not self._stage_lock_active(name):
                s["status"] = "interrupted"
                s["pid"] = None
                changed.append((name, "interrupted"))
            if s["status"] in DONE + ("needs_review",):
                cur = _hash_inputs(self.dir, STAGES[name][2])
                if s.get("inputs"):
                    # entrée ajoutée au DAG après coup et toujours absente : pas un changement (épisodes existants)
                    cur = {k: v for k, v in cur.items() if k in s["inputs"] or v is not None}
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
