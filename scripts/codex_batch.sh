#!/usr/bin/env bash
# Exécute une étape d'agent en mode non interactif avec Codex (`codex exec`).
# Exemple : scripts/codex_batch.sh ep_demo_grillepain visual-critic prototype
# L'agent écrit son rapport dans episodes/<ep>/reviews/ ; le pipeline le valide ensuite (studio submit).
set -euo pipefail
EP="$1"; ROLE="$2"; GATE="${3:-prototype}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG="episodes/$EP/checks/codex_${ROLE}_${GATE}.jsonl"
PROMPT="Utilise \$tiktok-3d-studio. Épisode $EP. Délègue à un sous-agent de type $ROLE la revue de la gate $GATE \
(skill \$visual-review si visuel). Le sous-agent écrit uniquement son rapport reviews/${ROLE}_${GATE}_r<N>.json \
puis lance scripts/studio submit. Ne lance aucune commande approve. Résume le verdict et les findings."
codex exec --json --output-last-message "episodes/$EP/checks/codex_${ROLE}_${GATE}_last.md" "$PROMPT" | tee "$LOG"
