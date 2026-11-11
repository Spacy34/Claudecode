# Installation sous Windows (pas à pas)

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
| `winget n'est pas reconnu` | Installe « App Installer » depuis le Microsoft Store. |
| `python` / `ffmpeg` introuvable après installation | Ferme et rouvre PowerShell (étape 4). Sinon redémarre le PC. |
| `l'exécution de scripts est désactivée` | Utilise exactement la commande de l'étape 3 (avec `-ExecutionPolicy Bypass`). |
| `doctor` : « installer Blender » alors qu'il est installé | Indique le chemin : `setx BLENDER_BIN "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"` (adapter la version), puis rouvre PowerShell. |
| `doctor` : « aucun moteur TTS » | Installe espeak-ng (.msi), ou configure Piper (`references/voice-options.md`). |
| Erreur `pip` sur un paquet | `py -3 -m pip install --upgrade pip` puis relance l'étape 3. |
| Accents illisibles dans la console | Lance `chcp 65001` avant les commandes. |

Si ça bloque encore : copie le message d'erreur exact (ou une capture d'écran) et envoie-le.
