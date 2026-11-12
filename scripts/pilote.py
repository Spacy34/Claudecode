#!/usr/bin/env python3
"""Pilote de production : alterne étapes automatiques (rendus, sans limite de temps, sans Codex en mémoire)
et sessions Codex COURTES limitées aux étapes qui demandent du jugement (écriture, critique).

Usage : python3 scripts/pilote.py ep_xxx [--modele NOM] [--max-tours 25]
Lancé par scripts/produire.sh dans tmux. S'arrête : épisode livré, validation humaine requise, blocage, ou
absence de progrès (même état deux tours de suite).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = str(ROOT / "scripts" / "studio")
sys.path.insert(0, str(ROOT / "pipeline"))
from studio.util import episode_dir, load_config  # noqa: E402  (respecte paths.episodes_dir et ses surcharges)


def ep_dir(ep):
    return episode_dir(load_config(), ep)


def log(msg):
    print(f"[pilote {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def studio(*args, capture=False):
    r = subprocess.run([STUDIO, *args], cwd=ROOT, text=True, capture_output=capture)
    return r


def nxt(ep):
    r = studio("next", ep, capture=True)
    return json.loads(r.stdout)


def codex_prompt(ep, n):
    lines = [f"Utilise $tiktok-3d-studio sur l'épisode {ep}. Le PILOTE gère tous les rendus et étapes automatiques :",
             "tu ne lances PAS `studio run`, `prototype`, `first-cut`, `final`, `check-shots` ni aucun rendu long.",
             "Fais UNIQUEMENT les étapes suivantes avec les sous-agents spécialisés, valide chacune avec",
             "`scripts/studio submit`, puis ARRÊTE-TOI (le pilote reprendra la suite) :"]
    for a in n["agent"]:
        lines.append(f"- étape `{a['stage']}` : rôle {a['owner']} -> {', '.join(a['outputs'])}")
    for rv in n["review"]:
        lines.append(f"- revue `{rv['stage']}` : critique(s) {rv['owner']} en lecture seule (rapports dans reviews/, puis submit --review)")
    for st, err in n["failed"].items():
        if st.startswith("gate_"):
            lines.append(f"- validation `{st}` REFUSÉE par la QA : {err}")
            lines.append("  -> fais corriger chaque défaut par le rôle indiqué entre crochets, dans SES artefacts (storyboard, "
                         "animation_plan, asset_manifest… ; moteur seulement pour pipeline-engineer), valide avec `scripts/studio validate` ; "
                         "ne lance AUCUN rendu : le pilote re-rendra les plans modifiés et revérifiera.")
        else:
            lines.append(f"- `{st}` a échoué au tour précédent : {err}. Fais corriger par le `fix_owner` des findings, puis refais l'étape.")
    brief = ep_dir(ep) / "episode_brief.json"
    if brief.exists() and json.loads(brief.read_text(encoding="utf-8")).get("script_lock"):
        lines.append("ATTENTION : script IMPOSÉ par l'utilisateur (episode_brief.script_lock) : ne jamais modifier texte, ordre ni locuteurs.")
    lines.append(f"PÉRIMÈTRE : pendant cette production, ne modifie AUCUN fichier hors de episodes/{ep}/ (ni pipeline/, blender/, "
                 "tests/, schemas/, config/, .codex/, mémoire versionnée). Si le moteur ou un contrôle te semble fautif, "
                 "décris-le dans ton rapport (et `scripts/studio memory add`) au lieu de modifier le code.")
    lines.append("Respecte AGENTS.md (jamais `studio approve`). Termine par un rapport court : fait / vérifié / bloquant.")
    return "\n".join(lines)


def run_codex(ep, prompt, model, logf):
    cmd = ["codex", "exec"]
    if model:
        cmd += ["-c", f'model="{model}"']
    cmd += ["--output-last-message", str(ep_dir(ep) / "checks" / "codex_rapport_final.md"), prompt]
    log("session Codex : " + prompt.splitlines()[4] if len(prompt.splitlines()) > 4 else "session Codex")
    with open(logf, "a", encoding="utf-8") as f:
        p = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, text=True)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--modele", default=os.environ.get("CODEX_MODEL", ""))
    ap.add_argument("--max-tours", type=int, default=25)
    a = ap.parse_args()
    ep = a.episode
    logf = ep_dir(ep) / "checks" / "codex_journal.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    last_fp, stale = None, 0
    for tour in range(1, a.max_tours + 1):
        log(f"tour {tour} : étapes automatiques (rendus inclus, peut être long)")
        r = studio("run", ep)
        n = nxt(ep)
        if n["done"]:
            log(f"ÉPISODE LIVRÉ : {ep_dir(ep) / 'renders' / 'final.mp4'}")
            return 0
        if n["needs_review"]:
            log(f"ARRÊT : intervention humaine requise sur {n['needs_review']} (budget de corrections ou validation refusée).")
            return 2
        if n["gates_human"] and not n["agent"] and not n["review"]:
            log(f"PAUSE : validation humaine attendue {n['gates_human']} -> `scripts/studio approve {ep} {n['gates_human'][0]}` "
                "puis relancer scripts/produire.sh " + ep)
            return 3
        if n["agent"] or n["review"] or n["failed"]:
            rc = run_codex(ep, codex_prompt(ep, n), a.modele, logf)
            if rc != 0:
                log(f"Codex a terminé avec le code {rc} (voir {logf}).")
        elif r.returncode != 0:
            log("une étape automatique a échoué : voir ci-dessus et `scripts/studio status %s`." % ep)
        n2 = nxt(ep)
        if n2["fingerprint"] == last_fp:
            stale += 1
            if stale >= 2:
                log("ARRÊT : aucun progrès depuis deux tours. Voir le journal et `scripts/studio status %s`." % ep)
                return 4
        else:
            stale = 0
        last_fp = n2["fingerprint"]
    log("ARRÊT : nombre maximal de tours atteint.")
    return 5


if __name__ == "__main__":
    sys.exit(main())
