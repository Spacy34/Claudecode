"""Pré-vérification AVANT soumission (studio preflight) : réussir du premier coup.

Ce qui coûtait des tours de correction n'apparaissait qu'APRÈS le rendu du prototype (repère inconnu, personnage
jamais visible, objet dans un personnage, plan collé…). Ici, en quelques dizaines de secondes et sans aucun rendu :
1. validation des contrats (schémas, références croisées, repères, cibles) ;
2. compilation « à blanc » dans un dossier temporaire (ordre des plans, ancrages, durées, cadrages équilibrés) ;
3. construction de chaque plan dans Blender et contrôles géométriques (mode « checks » : aucune image rendue).
Résultat : BLOQUANTS (à corriger avant de soumettre) et CONSEILS (qualité). Rien n'est modifié dans l'épisode.
"""
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import contracts, render
from .compile import OPEN, CompileError, compile_episode
from .util import cache_dir, read_json, write_json


def run(ep_dir, cfg, with_3d=True, only=None, log=lambda *_: None):
    ep_dir = Path(ep_dir)
    t0 = time.time()
    blocking, advice, stats = [], [], {}
    rep = contracts.validate_episode(ep_dir)
    for k, errs in rep.items():
        for e in errs:
            blocking.append(f"[contrat {k}] {e}")
    if blocking:
        return _done(ep_dir, blocking, advice, stats, t0, "validation")
    if not (ep_dir / "audio_timeline.json").exists() or not (ep_dir / "storyboard.json").exists():
        advice.append("voix ou storyboard pas encore disponible : seule la validation des contrats a été faite")
        return _done(ep_dir, blocking, advice, stats, t0, "validation")
    tmp = Path(tempfile.mkdtemp(prefix="preflight_", dir=cache_dir(cfg)))
    try:
        try:
            man = compile_episode(ep_dir, cfg, out_dir=tmp)
        except CompileError as e:
            msg = str(e)
            if "audio_timeline obsolète" in msg or "mots forts modifiés" in msg:
                advice.append(f"voix à recalculer par le pilote ({msg}) : contrôles 3D reportés")
                return _done(ep_dir, blocking, advice, stats, t0, "validation")
            blocking.append(f"[compilation] {msg}")
            return _done(ep_dir, blocking, advice, stats, t0, "compilation")
        advice += [f"[compilation] {w}" for w in man["warnings"]]
        sb = {s["id"]: s for s in read_json(ep_dir / "storyboard.json")["shots"]}
        specs = {s["id"]: read_json(tmp / s["spec_path"]) for s in man["shots"]}
        fr = [specs[s["id"]]["camera"]["framing"] for s in man["shots"]]
        stats = {"plans": len(fr), "duree_moyenne_s": round(sum(s["end_s"] - s["start_s"] for s in man["shots"]) / max(1, len(fr)), 2),
                 "decor_visible": f"{sum(f in OPEN for f in fr)}/{len(fr)}",
                 "plans_a_plusieurs_personnages": sum(len(specs[k]["characters"]) > 1 for k in specs),
                 "plans_avec_accessoires": sum(bool(specs[k]["props"]) for k in specs),
                 "plans_avec_figurants": sum(bool(specs[k].get("extras")) for k in specs),
                 "plans_avec_action": sum(bool(specs[k]["actions"]) for k in specs)}
        if stats["plans_avec_action"] < 0.6 * len(fr) and (ep_dir / "animation_plan.json").exists():
            advice.append(f"seulement {stats['plans_avec_action']}/{len(fr)} plans ont une action : un plan sans action = personnage qui ne fait que parler")
        if with_3d:
            shots = [s for s in man["shots"] if not only or s["id"] in only]
            workers = max(1, min(6, (os.cpu_count() or 2) // 2))
            log(f"contrôles 3D de {len(shots)} plans ({workers} en parallèle, sans rendu)…")
            try:
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    recs = list(ex.map(lambda s: render.render_shot(cfg, tmp, s, "draft", mode="checks", log=lambda *_: None), shots))
            except Exception as e:   # pas de Blender dans cet environnement : on n'invente rien
                advice.append(f"contrôles 3D indisponibles ici ({type(e).__name__}: {str(e)[:160]}) : ils seront faits au prototype")
                recs = []
                shots = []
            from .cli import _is_hard
            for s, r in zip(shots, recs):
                if r["status"] == "failed":
                    rep_ = r.get("scene_report") or {}
                    if rep_.get("error"):   # exception dans la construction de la scène : vrai problème de contrat
                        blocking.append(f"[{s['id']}] la scène ne se construit pas : {str(rep_['error'])[:300]}")
                    else:
                        advice.append(f"[{s['id']}] contrôle 3D non abouti ({str(r.get('error', ''))[:160]})")
                    continue
                for c in (r.get("scene_report") or {}).get("checks", []):
                    line = f"[{s['id']}] {c['id']} : {c['message']}"
                    if _is_hard(c):
                        blocking.append(line)
                    elif c.get("status") != "pass" and c.get("severity") in ("major", "minor"):
                        advice.append(line)
                for a in (r.get("scene_report") or {}).get("adjustments", []):
                    advice.append(f"[{s['id']}] ajustement automatique : {a}")
            stats["contrôles_3d"] = len(recs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _done(ep_dir, blocking, advice, stats, t0, "complet" if with_3d else "sans 3D")


def _done(ep_dir, blocking, advice, stats, t0, level):
    rep = {"ok": not blocking, "level": level, "seconds": round(time.time() - t0, 1), "blocking": blocking,
           "advice": list(dict.fromkeys(advice))[:60], "stats": stats}
    (Path(ep_dir) / "checks").mkdir(exist_ok=True)
    write_json(Path(ep_dir) / "checks" / "preflight.json", rep)
    return rep
