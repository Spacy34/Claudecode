#!/usr/bin/env bash
# Lance la production COMPLÈTE d'un épisode en arrière-plan (tmux + codex exec), journal compris.
#
#   scripts/produire.sh episodes/_inbox/mon_script.txt            -> script imposé (texte verrouillé)
#   scripts/produire.sh episodes/_inbox/mon_histoire.txt --libre   -> histoire brute (Codex écrit le script)
#   scripts/produire.sh ... --nom ep_mon_episode --duree 45
#
# Suivre : tmux attach -t <ep>   |   scripts/studio status <ep>   |   tail -f episodes/<ep>/checks/codex_journal.log
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STUDIO="$ROOT/scripts/studio"

FILE="${1:-}"; shift || true
MODE="script"; EP=""; DUREE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --libre) MODE="libre" ;;
    --nom) EP="$2"; shift ;;
    --duree) DUREE="$2"; shift ;;
    *) echo "option inconnue : $1"; exit 1 ;;
  esac
  shift
done
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Usage : scripts/produire.sh <fichier.txt> [--libre] [--nom ep_xxx] [--duree 45]"; exit 1; }

# nom d'épisode dérivé du fichier : episodes/_inbox/La Poule.txt -> ep_la_poule
if [ -z "$EP" ]; then
  base="$(basename "$FILE" .txt | iconv -f utf-8 -t ascii//TRANSLIT 2>/dev/null || basename "$FILE" .txt)"
  EP="ep_$(echo "$base" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/_/g; s/^_//; s/_$//' | cut -c1-40)"
fi

command -v codex >/dev/null || { echo "Codex n'est pas installé (VPS.md §4)."; exit 1; }
command -v tmux >/dev/null || { echo "tmux manquant : sudo apt-get install -y tmux"; exit 1; }

# Contrôles avant lancement
AUTO="$(".venv/bin/python" -c "import sys;sys.path.insert(0,'pipeline');from studio.util import load_config as l;print(l()['quality']['autonomous'])" 2>/dev/null || echo "?")"
if [ "$AUTO" != "True" ]; then
  echo "ATTENTION : mode autonome désactivé -> Codex s'arrêtera à chaque validation humaine."
  echo "            (config/local.toml : [quality] autonomous = true)"
fi
if pgrep -f "run_shot.py" >/dev/null; then
  echo "ATTENTION : un rendu Blender tourne déjà. Avec peu de RAM, attendez sa fin (ou Ctrl+C pour annuler)."
  sleep 5
fi
if tmux has-session -t "$EP" 2>/dev/null; then
  echo "Une production de $EP tourne déjà : tmux attach -t $EP"; exit 1
fi

# Création (ou reprise) de l'épisode
if [ ! -d "episodes/$EP" ]; then
  if [ "$MODE" = "script" ]; then
    "$STUDIO" new "$EP" --script-file "$FILE" ${DUREE:+--duration "$DUREE"} --stop-after final
    CONSIGNE="L'épisode $EP existe avec le script IMPOSÉ par l'utilisateur (verrouillé) : fais-le habiller par le story-architect sans changer le texte."
  else
    "$STUDIO" new "$EP" --story-file "$FILE" --duration "${DUREE:-60}" --stop-after final
    CONSIGNE="L'épisode $EP existe avec une histoire brute : fais écrire le script par le story-architect."
  fi
else
  echo "L'épisode $EP existe déjà : reprise là où il s'est arrêté."
  CONSIGNE="L'épisode $EP existe déjà : reprends-le à la première étape non terminée (scripts/studio status $EP)."
fi

mkdir -p "episodes/$EP/checks"
LOG="episodes/$EP/checks/codex_journal.log"
LAST="episodes/$EP/checks/codex_rapport_final.md"
PROMPT="Utilise \$tiktok-3d-studio. $CONSIGNE Enchaîne ensuite toute la production avec les sous-agents spécialisés \
et les critiques indépendants, jusqu'à renders/final.mp4 si le mode autonome est activé (sinon arrête-toi à la première \
validation humaine). Respecte AGENTS.md. Si une étape est refusée ou bloquée, arrête-toi et écris un rapport clair : \
ce qui est fait, ce qui bloque, preuves."

# Le message passe par un fichier : aucun caractère ($, apostrophes…) n'est réinterprété par le shell de tmux
PFILE="episodes/$EP/checks/codex_consigne.txt"
printf '%s\n' "$PROMPT" > "$PFILE"
tmux new-session -d -s "$EP" -c "$ROOT" \
  "codex exec --output-last-message '$LAST' \"\$(cat '$PFILE')\" 2>&1 | tee -a '$LOG'; echo; echo '=== PRODUCTION TERMINÉE (rapport : $LAST) ==='; '$STUDIO' status '$EP'; read -r -p 'Entrée pour fermer' _"

echo
echo "Production lancée en arrière-plan : épisode $EP"
echo "  Regarder en direct  : tmux attach -t $EP      (quitter sans arrêter : Ctrl+b puis d)"
echo "  Avancement          : scripts/studio status $EP"
echo "  Journal             : tail -f $LOG"
echo "  Rapport de fin      : $LAST"
echo "  Vidéo finale        : episodes/$EP/renders/final.mp4"
