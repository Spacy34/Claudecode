#!/usr/bin/env python3
"""Pilote de production : alterne étapes automatiques (rendus, sans limite de temps, sans Codex en mémoire)
et sessions Codex COURTES limitées aux étapes qui demandent du jugement (écriture, critique).

Usage : python3 scripts/pilote.py ep_xxx [--modele NOM] [--max-tours 25]
Lancé par scripts/produire.sh dans tmux. S'arrête : épisode livré, validation humaine requise, blocage, ou
absence de progrès (même état deux tours de suite).
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from studio.launcher import studio_cmd, studio_env  # noqa: E402  (Windows / macOS / Linux : pas de bash)
from studio.state import _lock  # noqa: E402
from studio.util import episode_dir, load_config, which  # noqa: E402  (respecte paths.episodes_dir et ses surcharges)


def ep_dir(ep):
    return episode_dir(load_config(), ep)


def log(msg):
    print(f"[pilote {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def studio(*args, capture=False):
    r = subprocess.run(studio_cmd(*args), cwd=ROOT, env=studio_env(), text=True, capture_output=capture, encoding="utf-8", errors="replace")
    if not capture:
        sys.stdout.flush()
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
        if st.startswith("gate_") or st == "shots_check":
            lines.append(f"- {'validation' if st.startswith('gate_') else 'contrôle'} `{st}` REFUSÉ par la QA : {err}")
            lines.append("  -> fais corriger chaque défaut par le rôle indiqué entre crochets, dans SES artefacts (storyboard, "
                         "animation_plan, asset_manifest… ; moteur seulement pour pipeline-engineer), valide avec `scripts/studio validate` ; "
                         "ne lance AUCUN rendu : le pilote re-rendra les plans modifiés et revérifiera.")
        else:
            lines.append(f"- `{st}` a échoué au tour précédent : {err}. Fais corriger par le `fix_owner` des findings, puis refais l'étape.")
    stp = ep_dir(ep) / "state.json"
    decisions = json.loads(stp.read_text(encoding="utf-8")).get("human_decisions", []) if stp.exists() else []
    for d in decisions:
        lines.append(f"DÉCISION HUMAINE (s'impose à tous les rôles, critiques compris ; ne pas re-bloquer pour ce motif, "
                     f"seulement vérifier que ses conditions sont respectées) : {d['note']}")
    brief = ep_dir(ep) / "episode_brief.json"
    if brief.exists() and json.loads(brief.read_text(encoding="utf-8")).get("script_lock"):
        lines.append("ATTENTION : script IMPOSÉ par l'utilisateur (episode_brief.script_lock) : ne jamais modifier texte, ordre ni locuteurs.")
    lines.append(f"PÉRIMÈTRE : pendant cette production, ne modifie AUCUN fichier hors de episodes/{ep}/ (ni pipeline/, blender/, "
                 "tests/, schemas/, config/, .codex/, mémoire versionnée). Si le moteur ou un contrôle te semble fautif, "
                 "décris-le dans ton rapport (et `scripts/studio memory add`) au lieu de modifier le code.")
    if os.name == "nt":
        lines.append("WINDOWS : lance toujours `scripts\\studio.cmd <commande>` (jamais `scripts/studio`, script bash inexécutable sous PowerShell).")
    lines.append("Respecte AGENTS.md (jamais `studio approve`). Termine par un rapport court : fait / vérifié / bloquant.")
    return "\n".join(lines)


CODEX_HINTS = [
    (("not logged in", "codex login", "unauthorized", "401 ", "authentication required"), "Codex n'est pas connecté : ouvrez PowerShell et lancez `codex login`."),
    (("model is not supported", "not supported when using codex", "model_not_found", "unknown model", "model does not exist"), "modèle Codex refusé : videz le champ « Modèle Codex » du tableau de bord "
                                                                    "(ou config/local.toml [codex] model), ou mettez un modèle listé par /model dans `codex`."),
    (("trusted", "git repo", "skip-git-repo-check"), "dossier non approuvé par Codex : lancez `codex` une fois dans le dossier du studio et acceptez."),
    (("unexpected argument", "unrecognized", "usage:"), "version de Codex trop ancienne : `npm install -g @openai/codex@latest`."),
    (("n'est pas reconnu", "is not recognized", "node: not found", "cannot find module"), "Node.js/Codex mal installé : `winget install --id OpenJS.NodeJS.LTS -e`, puis "
                                                          "`npm install -g @openai/codex`, puis rouvrir PowerShell."),
    (("rate limit", "usage limit", "quota", "429"), "limite d'utilisation de Codex atteinte : réessayer plus tard."),
]


def codex_hint(text):
    low = text.lower()
    for keys, hint in CODEX_HINTS:
        if any(k in low for k in keys):
            return hint
    return None


def run_codex(ep, prompt, model, logf):
    """-> (code retour, dernières lignes de sortie). La sortie est recopiée en direct dans le journal."""
    exe = which("codex")
    if not exe:
        log("Codex introuvable (commande `codex`) : installez-le et connectez-vous (`codex login`), puis relancez.")
        return 127, ""
    cmd = [exe, "exec", "--skip-git-repo-check"]   # dossier issu d'un ZIP (pas un dépôt Git) : autorisé explicitement
    if model:
        cmd += ["-c", f'model="{model}"']
    # consigne transmise sur l'entrée standard (« - ») : aucun problème d'échappement (cmd.exe, $, retours à la ligne)
    cmd += ["--output-last-message", str(ep_dir(ep) / "checks" / "codex_rapport_final.md"), "-"]
    log("session Codex : " + prompt.splitlines()[4] if len(prompt.splitlines()) > 4 else "session Codex")
    sys.stdout.flush()
    tail = collections.deque(maxlen=40)
    with open(logf, "a", encoding="utf-8") as f:
        try:
            p = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            log(f"impossible de lancer Codex ({exe}) : {e}")
            return 126, str(e)
        try:
            p.stdin.write(prompt)
            p.stdin.close()
        except OSError:
            pass
        for line in p.stdout:
            f.write(line)
            f.flush()
            if line.strip():
                tail.append(line.rstrip())
        rc = p.wait()
    return rc, "\n".join(tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--modele", default=os.environ.get("CODEX_MODEL", ""))
    ap.add_argument("--max-tours", type=int, default=25)
    a = ap.parse_args()
    ep = a.episode
    logf = ep_dir(ep) / "checks" / "codex_journal.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    # verrou « production en cours » (tableau de bord, studio produire) : un seul pilote par épisode
    lock_h = open(logf.parent / "pilote.lock", "a+b")
    try:
        _lock(lock_h)
    except OSError:
        log(f"une production de {ep} tourne déjà : arrêt.")
        return 7
    (logf.parent / "pilote.pid").write_text(str(os.getpid()), encoding="utf-8")
    last_fp, stale, quick_fail = None, 0, 0
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
            t_start = time.time()
            rc, out = run_codex(ep, codex_prompt(ep, n), a.modele, logf)
            if rc == 127:
                return 6
            if rc != 0:
                last = [l for l in out.splitlines() if l.strip()][-6:]
                log(f"Codex a terminé avec le code {rc}. Ses derniers messages :")
                for l in last:
                    print(f"    | {l[:300]}", flush=True)
                hint = codex_hint(out)
                if hint:
                    log("→ " + hint)
                if time.time() - t_start < 20:
                    quick_fail += 1
                    if quick_fail >= 2:
                        log("ARRÊT : Codex refuse de démarrer (deux échecs immédiats). Corrigez la cause ci-dessus, puis relancez.")
                        return 8
                else:
                    quick_fail = 0
            else:
                quick_fail = 0
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
