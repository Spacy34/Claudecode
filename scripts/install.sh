#!/usr/bin/env bash
# Installation locale (Linux/macOS ; Windows : WSL2 recommandé). À lancer HORS de Codex (accès réseau).
# Ne télécharge que des paquets des dépôts officiels (apt/brew/PyPI). Rien n'est exécuté sans être affiché.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "== 1/4 Paquets système (ffmpeg avec libass/libx264, espeak-ng pour les tests) =="
if command -v apt-get >/dev/null; then
  echo "sudo apt-get install -y ffmpeg espeak-ng fontconfig"
  sudo apt-get install -y ffmpeg espeak-ng fontconfig
elif command -v brew >/dev/null; then
  echo "brew install ffmpeg espeak-ng"
  brew install ffmpeg espeak-ng
else
  echo "Installer manuellement : ffmpeg (avec libass, libx264), espeak-ng"
fi
echo "== 2/4 Dépendances Python =="
python3 -m pip install -r requirements.txt
echo "== 3/4 Blender =="
if command -v blender >/dev/null || [ -n "${BLENDER_BIN:-}" ]; then
  echo "Binaire Blender trouvé : ${BLENDER_BIN:-$(command -v blender)}"
else
  echo "Aucun binaire Blender. Option A (recommandée avec GPU) : installer Blender >= 4.2 depuis blender.org et exporter BLENDER_BIN."
  echo "Option B (headless, CPU) : python3 -m pip install bpy  (vérifier la version de Python supportée)"
  read -r -p "Installer le module pip bpy maintenant ? [o/N] " a
  if [ "${a:-N}" = "o" ]; then python3 -m pip install bpy; fi
fi
echo "== 4/4 Diagnostic =="
chmod +x scripts/studio scripts/codex_batch.sh
scripts/studio doctor || true
echo "Voix de production : voir references/voice-options.md (Piper + voix FR à licence commerciale)."
