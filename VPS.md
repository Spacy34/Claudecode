# Déployer le studio sur un VPS (plan d'action)

Cible recommandée : **Ubuntu 24.04**, accès SSH. Tout tourne en ligne de commande : Blender sans écran,
Codex en terminal, vidéos récupérées sur ton PC. Aucun port web n'est ouvert sur Internet.

## 0. Choisir le VPS
| Usage | CPU | RAM | Disque | Remarque |
|---|---|---|---|---|
| Minimum (tests, draft) | 4 vCPU | 8 Go | 40 Go | ≈ 1,2 s/image en draft (mesuré sur 4 cœurs) |
| Recommandé | 8–16 vCPU dédiés | 16 Go | 80 Go SSD | le rendu Cycles CPU accélère presque linéairement avec les cœurs |
| GPU (facultatif) | + NVIDIA | 16 Go | 80 Go | EEVEE beaucoup plus rapide ; **non testé** : à valider avec `check-shots` |

Évite les VPS « OpenVZ/LXC » bas de gamme : le bac à sable de Codex a besoin d'un noyau Linux complet (KVM).
Astuce coût : un petit VPS CPU permanent pour écrire/valider, et un serveur GPU loué à l'heure uniquement
pour les rendus `final` (journaliser la dépense : `studio cost`).

## 1. Sécuriser le serveur (une fois, en root)
```bash
adduser studio
```
```bash
usermod -aG sudo studio
```
```bash
rsync --archive --chown=studio:studio ~/.ssh /home/studio
```
```bash
ufw allow OpenSSH && ufw --force enable
```
Puis désactive la connexion root par mot de passe (`PermitRootLogin no`, `PasswordAuthentication no` dans
`/etc/ssh/sshd_config`, puis `systemctl restart ssh`) **après** avoir vérifié que la connexion par clé de
l'utilisateur `studio` fonctionne. Petit VPS : ajoute 4 Go de swap pour éviter les arrêts brutaux.

## 2. Installer le studio (en utilisateur `studio`)
```bash
git clone -b claude/awesome-rubin-fftz1l https://github.com/Spacy34/Claudecode.git studio
```
```bash
cd studio && bash scripts/setup_vps.sh
```
```bash
source ~/.bashrc
```
Le script installe FFmpeg, espeak-ng, un environnement Python isolé (`.venv`), le **binaire officiel de
Blender** dans `/opt` (somme SHA-256 vérifiée), règle les variables (`BLENDER_BIN`, mode binaire), puis
lance `doctor` et les tests (rapides + rendus Blender réels). Il doit finir avec des tests verts.

## 3. Voix de production (Piper)
```bash
.venv/bin/pip install piper-tts
```
Place une voix française (`.onnx` + `.onnx.json`) dans `assets/voices/` **après avoir vérifié sa licence
commerciale**, puis dans `config/studio.toml` : `backend = "piper"` et `piper_model = "assets/voices/<voix>.onnx"`.
Test : `studio voice ep_demo_grillepain --force`.

## 4. Installer et connecter Codex
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs
```
```bash
sudo npm install -g @openai/codex
```
Connexion : lance `codex` dans le dossier `studio` et suis les instructions de connexion affichées
(sur un serveur sans navigateur, utilise l'option de connexion par code proposée, ou une clé API exportée
dans l'environnement — jamais écrite dans le dépôt). Marque le dossier comme « trusted » pour charger
`.codex/config.toml`. Vérifie : `/skills` doit lister `tiktok-3d-studio`.

## 5. Travailler au quotidien
Toujours dans **tmux** (la session survit à une déconnexion SSH ; un rendu interrompu reprend de toute façon) :
```bash
tmux new -A -s studio
```
Dans Codex : « Crée un épisode TikTok 3D de 60 secondes à partir de cette histoire : … ».
Les validations humaines se font dans un **second panneau tmux** (`Ctrl+b` puis `%`) :
```bash
studio approve ep_mon_histoire gate_script
```
Détacher sans arrêter : `Ctrl+b` puis `d`. Revenir : `tmux attach -t studio`.

## 6. Récupérer et visionner les vidéos sur ton PC
Copie simple (depuis ton PC, PowerShell ou terminal) :
```bash
scp studio@IP_DU_VPS:studio/episodes/ep_mon_histoire/renders/prototype.mp4 .
```
Tout un épisode (rendus + planches de contrôle) :
```bash
rsync -av studio@IP_DU_VPS:studio/episodes/ep_mon_histoire/ ./ep_mon_histoire/
```
Aperçu dans le navigateur sans rien exposer : sur le VPS `cd ~/studio/episodes && python3 -m http.server 8765 --bind 127.0.0.1`,
puis sur ton PC `ssh -L 8765:127.0.0.1:8765 studio@IP_DU_VPS` et ouvre `http://localhost:8765`.

## 7. Entretien
- Mise à jour : `git pull` puis `studio doctor` et `.venv/bin/python -m pytest -q -m "not blender"`.
- Cache des rendus : `studio cache` (taille), purge auto chaque nuit :
  `crontab -e` → `30 3 * * * cd ~/studio && ./scripts/studio cache --prune >/dev/null 2>&1`
- Sauvegarde : les artefacts d'épisode (JSON) se versionnent avec git ; les vidéos se rapatrient (§6).
- Rendus parallèles : `config/studio.toml [limits] max_parallel_renders` = valeur recommandée par `doctor`.

## 8. Dépannage
| Symptôme | Cause / solution |
|---|---|
| `Permission denied: .../.venv` | dépôt cloné avec sudo : `sudo chown -R $USER:$USER <dossier>` puis relancer |
| `ImportError ... pip._internal` | `.venv` corrompu par un essai interrompu : `rm -rf .venv` puis relancer le script |
| `doctor` : Blender introuvable | `source ~/.bashrc` ; vérifier `ls /opt/blender-*/blender` |
| Blender : `libXi.so`/`libGL` manquant | `sudo apt-get install libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1` |
| Rendu très lent | normal sur CPU : itérer en `draft`, `preview` seulement pour les gates ; GPU pour `final` |
| Processus tué pendant un rendu | mémoire insuffisante : swap, ou `max_parallel_renders = 1` ; relancer la même commande (reprise) |
| Erreur EEVEE sur serveur GPU | forcer Cycles : `export STUDIO_RENDER_ENGINE=cycles` |
| Codex : erreur de sandbox | VPS non-KVM (conteneur) : changer d'offre |
| Accents bizarres dans le terminal | `export LANG=C.UTF-8` |

**Non testé ici** : le script complet sur un VPS réel, le mode « binaire Blender » (le développement a utilisé
le module `bpy`), EEVEE/GPU, Piper. Le premier passage de `setup_vps.sh` (tests Blender inclus) sert de vérification.
