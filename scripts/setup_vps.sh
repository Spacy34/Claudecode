#!/usr/bin/env bash
# Installation du studio sur un VPS Ubuntu 24.04 (CPU ; GPU NVIDIA facultatif).
# À lancer en utilisateur NORMAL avec sudo, depuis la racine du dépôt :  bash scripts/setup_vps.sh
# Tout ce qui est téléchargé vient des dépôts Ubuntu, de PyPI ou de download.blender.org (somme SHA-256 vérifiée).
set -euo pipefail
BLENDER_VERSION="${BLENDER_VERSION:-5.2.3}"            # adaptez si besoin (voir download.blender.org/release)
BLENDER_SERIES="${BLENDER_VERSION%.*}"
BLENDER_DIR="/opt/blender-${BLENDER_VERSION}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "$(id -u)" = "0" ]; then echo "Ne lancez pas ce script en root : créez un utilisateur (voir VPS.md §1)."; exit 1; fi
. /etc/os-release
echo "== Système : $PRETTY_NAME, $(nproc) cœurs, $(free -g | awk '/Mem/{print $2}') Go RAM, $(df -h "$ROOT" | awk 'NR==2{print $4}') libres"

# Dossier non modifiable (ex. cloné avec sudo dans /opt) : on le dit clairement au lieu d'échouer plus loin
if [ ! -w "$ROOT" ]; then
  echo "Le dossier $ROOT n'est pas modifiable par $(whoami). Corrigez puis relancez :"
  echo "  sudo chown -R $(whoami):$(whoami) $ROOT"
  exit 1
fi

# Petite machine : le rendu Blender + Codex peuvent dépasser la RAM -> proposer un swap
RAM_GB=$(free -g | awk '/Mem/{print $2}')
SWAP_GB=$(free -g | awk '/Swap/{print $2}')
if [ "${RAM_GB:-0}" -lt 6 ] && [ "${SWAP_GB:-0}" -lt 2 ]; then
  echo "RAM faible (${RAM_GB} Go) et pas de swap : risque d'arrêt brutal pendant les rendus."
  read -r -p "Créer un fichier de swap de 4 Go (/swapfile) ? [o/N] " ans
  if [ "${ans:-N}" = "o" ]; then
    sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
    grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
    echo "Swap actif : $(free -g | awk '/Swap/{print $2}') Go"
  fi
fi

echo "== 1/6 Paquets système"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip ffmpeg espeak-ng fontconfig git tmux curl xz-utils \
  libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1 fonts-inter >/dev/null || \
  sudo apt-get install -y -qq python3 python3-venv python3-pip ffmpeg espeak-ng fontconfig git tmux curl xz-utils \
  libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ requis (Ubuntu 24.04 recommandé)"'

echo "== 2/6 Environnement Python isolé (.venv)"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "== 3/6 Blender ${BLENDER_VERSION} (binaire officiel, headless)"
if [ ! -x "${BLENDER_DIR}/blender" ]; then
  TMP="$(mktemp -d)"
  URL="https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}-linux-x64.tar.xz"
  echo "Téléchargement : $URL"
  curl -fL --retry 3 -o "$TMP/blender.tar.xz" "$URL"
  if curl -fsL -o "$TMP/sums.sha256" "https://download.blender.org/release/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}.sha256"; then
    EXPECTED="$(grep "linux-x64.tar.xz" "$TMP/sums.sha256" | awk '{print $1}')"
    ACTUAL="$(sha256sum "$TMP/blender.tar.xz" | awk '{print $1}')"
    [ -n "$EXPECTED" ] && [ "$EXPECTED" = "$ACTUAL" ] && echo "SHA-256 vérifiée" || { echo "SHA-256 différente : arrêt"; exit 1; }
  else
    echo "ATTENTION : fichier de sommes introuvable, vérifiez manuellement : $(sha256sum "$TMP/blender.tar.xz")"
  fi
  sudo mkdir -p "$BLENDER_DIR"
  sudo tar -xJf "$TMP/blender.tar.xz" -C "$BLENDER_DIR" --strip-components=1
  rm -rf "$TMP"
fi
"${BLENDER_DIR}/blender" -b --factory-startup -noaudio --version | head -1

echo "== 4/6 Variables d'environnement (~/.bashrc)"
grep -q "BLENDER_BIN=" ~/.bashrc || cat >> ~/.bashrc <<RC
# --- studio TikTok 3D ---
export BLENDER_BIN="${BLENDER_DIR}/blender"
export STUDIO_PYTHON="${ROOT}/.venv/bin/python"
export STUDIO_BLENDER_MODE=binary
alias studio="${ROOT}/scripts/studio"
RC
export BLENDER_BIN="${BLENDER_DIR}/blender" STUDIO_PYTHON="${ROOT}/.venv/bin/python" STUDIO_BLENDER_MODE=binary

if [ "$(nproc)" -le 2 ]; then   # petite machine : un seul rendu à la fois
  sed -i 's/^max_parallel_renders = .*/max_parallel_renders = 1        # processus Blender simultanés/' config/studio.toml
fi

echo "== 5/6 Diagnostic"
chmod +x scripts/studio
scripts/studio doctor | tail -25 || true

echo "== 6/6 Tests (rapides puis rendus Blender réels)"
.venv/bin/python -m pytest -q -m "not blender" | tail -2
.venv/bin/python -m pytest -q -m blender | tail -2 || echo "Tests Blender en échec : voir VPS.md §Dépannage"
echo "Terminé. Rechargez le shell :  source ~/.bashrc"
