# Installation sous Windows (pas à pas)

## Tu as déjà installé le studio sur ce PC : mettre à jour + tableau de bord

1. **Mettre à jour le code.** Avec Git (dans PowerShell, dans le dossier du studio) :
   ```powershell
   git pull
   ```
   Sans Git (installation par ZIP) : retélécharge le ZIP de la branche `claude/awesome-rubin-fftz1l` et décompresse-le
   **par-dessus** l'ancien dossier (tes `episodes\` et `config\local.toml` sont conservés).
2. **Compléter l'installation** (nouveautés : Git, Codex en option, raccourci du Bureau) :
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
   ```
3. **Connecter Codex** (une fois, si tu l'as installé) : nouveau PowerShell, puis `codex login`, puis lance `codex` une
   fois dans le dossier du studio et accepte de lui faire confiance (« trusted »), puis quitte avec `/quit`.
4. **Ouvrir le tableau de bord** : double-clic sur le raccourci **Studio TikTok 3D** du Bureau, ou
   ```powershell
   scripts\dashboard.cmd
   ```
   Le navigateur s'ouvre sur `http://127.0.0.1:8765`. Tout se fait ensuite à la souris :
   - **+ Nouvelle vidéo** : colle ton script (une réplique par ligne, `Prénom: réplique` pour un personnage) ou une
     histoire, coche « Lancer la production tout de suite », clique **Créer la vidéo**.
   - **Mode autonome** (en haut) : coché = plus aucune validation, la production va jusqu'à la vidéo finale.
     **Rendu final** : `final` (1080p, lent sans carte graphique) ou `preview` (rapide). Clique **Enregistrer**.
   - Pour chaque épisode : **Avancement** (où ça en est, étape par étape, bouton « Réessayer »), **Vérifications**
     (contrôles automatiques et avis des critiques), **Vidéos & images** (prototype, montage, vidéo finale, planches),
     **Voix & sons** (ta propre voix pour une réplique, ta musique, un bruitage sur un mot précis), **Journal** (en direct).
   - **Lancer / reprendre** et **Arrêter** : la production tourne en arrière-plan ; fermer le tableau de bord ne
     l'arrête pas. Relancer reprend là où elle s'était arrêtée (les images déjà rendues sont gardées).

Sans tableau de bord, les mêmes actions en ligne de commande :
```powershell
scripts\studio.cmd produire episodes\_inbox\mon_script.txt
```
```powershell
scripts\studio.cmd arreter ep_mon_script
```

Deux méthodes. **Essaie d'abord la méthode A** (tout dans Windows). Si quelque chose bloque, la méthode B
(WSL, un Linux intégré à Windows) est celle sur laquelle le pipeline a été testé.

---

## Méthode A — Windows natif (environ 20 minutes)

### Étape 1 : télécharger le projet
1. Va sur `https://github.com/Spacy34/Claudecode`.
2. Clique sur le menu des branches et choisis **`claude/awesome-rubin-fftz1l`**.
3. Bouton vert **Code** → **Download ZIP**.
4. Décompresse le ZIP dans un dossier **simple et sans espaces ni accents**, par exemple `C:\studio`.
   (Évite OneDrive, Bureau et Documents s'ils sont synchronisés.)

### Étape 2 : ouvrir PowerShell dans le dossier
Dans l'explorateur, ouvre `C:\studio`, clique dans la barre d'adresse, tape `powershell` puis Entrée.

### Étape 3 : lancer l'installateur
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```
Il installe avec `winget` (l'outil officiel de Microsoft) : Python 3.12, FFmpeg, Blender, puis les
bibliothèques Python. Accepte les fenêtres d'autorisation qui s'ouvrent.

**espeak-ng** (voix de test) doit être installé à la main : télécharge `espeak-ng.msi` sur
`https://github.com/espeak-ng/espeak-ng/releases` et double-clique dessus.

### Étape 4 : FERMER et ROUVRIR PowerShell
Obligatoire : sinon Windows ne trouve pas les programmes qui viennent d'être installés.
Rouvre PowerShell dans `C:\studio` (étape 2).

### Étape 5 : vérifier
```powershell
scripts\studio.cmd doctor
```
Regarde la fin du résultat : `"blocking": false` = c'est bon. Sinon, la section `"advice"` dit quoi installer.

### Étape 6 : premier test réel
```powershell
scripts\studio.cmd voice ep_demo_grillepain --force
```
```powershell
scripts\studio.cmd compile ep_demo_grillepain --force
```
```powershell
scripts\studio.cmd render ep_demo_grillepain --shots sh_001 --profile draft --out renders/test.mp4
```
Ouvre ensuite `episodes\ep_demo_grillepain\renders\test.mp4` : tu dois voir Kevin animé, avec voix et sous-titres.

Sous Windows, remplace toujours `scripts/studio` (dans la doc) par `scripts\studio.cmd`.

---

## Méthode B — WSL (Linux dans Windows), la plus fiable

### Étape 1 : installer WSL
PowerShell **en administrateur** (clic droit sur PowerShell → Exécuter en tant qu'administrateur) :
```powershell
wsl --install -d Ubuntu-24.04
```
Redémarre le PC, ouvre « Ubuntu » dans le menu Démarrer, choisis un nom d'utilisateur et un mot de passe.

### Étape 2 : dans la fenêtre Ubuntu
```bash
git clone -b claude/awesome-rubin-fftz1l https://github.com/Spacy34/Claudecode.git
```
```bash
cd Claudecode && scripts/install.sh
```
Quand il propose le module `bpy`, réponds `o`. Puis :
```bash
scripts/studio doctor
```
Tes fichiers sont visibles depuis l'explorateur Windows à l'adresse `\\wsl$\Ubuntu-24.04\home\<ton-nom>\Claudecode`.

Limite : sous WSL, le rendu se fait sur le processeur (plus lent que la carte graphique de la méthode A).

---

## Ouvrir le projet dans Codex
Ouvre Codex dans le dossier du projet (`C:\studio`, ou le dossier WSL), accepte de lui faire confiance,
puis écris ta demande (voir `README.md` §2). Les validations se font dans PowerShell :
```powershell
scripts\studio.cmd approve <episode> gate_script
```

## Problèmes fréquents
| Message | Solution |
|---|---|
| `No module named 'tomllib'` | Python trop ancien (3.8/3.9/3.10). Installe Python 3.12 : `winget install --id Python.Python.3.12 -e`, rouvre PowerShell, puis `py -3.12 -m pip install -r requirements.txt`. `studio.cmd` choisit ensuite automatiquement Python 3.12. |
| `winget n'est pas reconnu` | Installe « App Installer » depuis le Microsoft Store. |
| `python` / `ffmpeg` introuvable après installation | Ferme et rouvre PowerShell (étape 4). Sinon redémarre le PC. |
| `l'exécution de scripts est désactivée` | Utilise exactement la commande de l'étape 3 (avec `-ExecutionPolicy Bypass`). |
| `doctor` : « installer Blender » alors qu'il est installé | Indique le chemin : `setx BLENDER_BIN "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"` (adapter la version), puis rouvre PowerShell. |
| `doctor` : « aucun moteur TTS » | Installe espeak-ng (.msi), ou configure Piper (`references/voice-options.md`). |
| Erreur `pip` sur un paquet | `py -3 -m pip install --upgrade pip` puis relance l'étape 3. |
| Accents illisibles dans la console | Lance `chcp 65001` avant les commandes. |

Si ça bloque encore : copie le message d'erreur exact (ou une capture d'écran) et envoie-le.
