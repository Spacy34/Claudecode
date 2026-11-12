# Le studio sur ton PC Windows (machine principale)

Tout se fait sur le PC : écriture et critiques (Codex), rendu 3D (Blender, avec ta carte graphique), voix, montage,
vidéo finale. Le pilotage se fait dans un **tableau de bord** (page web locale). Le VPS n'est plus nécessaire.

Il te faut : Windows 10 ou 11, ~20 Go libres, une connexion Internet pour l'installation, ton compte ChatGPT
(pour Codex). Une carte graphique NVIDIA/AMD récente accélère beaucoup le rendu, mais n'est pas obligatoire.

---

## 1. Récupérer le projet (une fois)
Ouvre PowerShell (menu Démarrer → « PowerShell »). Si Git n'est pas encore installé :
```powershell
winget install --id Git.Git -e
```
Ferme puis rouvre PowerShell, puis :
```powershell
git clone -b claude/awesome-rubin-fftz1l https://github.com/Spacy34/Claudecode.git C:\studio
```
```powershell
cd C:\studio
```
Dossier simple, sans espaces ni accents, hors OneDrive. Tu avais déjà une ancienne copie par ZIP ? Garde-la de côté
(tu pourras y reprendre un épisode, §7) et travaille désormais dans `C:\studio` : les mises à jour se feront avec `git pull`.

## 2. Installer (environ 20 minutes)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```
Il installe avec `winget` (l'outil officiel de Microsoft) Python 3.12, FFmpeg, Blender, Git, puis te pose des questions :
- **Piper** (voix française naturelle, gratuite, locale) : réponds **O**.
- **Codex** (les agents qui écrivent, mettent en scène, critiquent) : réponds **O**.
- **Mode autonome** (aucune validation humaine, jusqu'à la vidéo finale) : réponds **O**.

Il crée aussi `config\local.toml` (tes réglages, jamais écrasés par une mise à jour) et un raccourci
**Studio TikTok 3D** sur le Bureau. Accepte les fenêtres d'autorisation de Windows.

Facultatif : **espeak-ng** (voix robotique de secours) s'installe avec le `.msi` de
`https://github.com/espeak-ng/espeak-ng/releases`.

## 3. Fermer et rouvrir PowerShell, puis vérifier
Obligatoire, sinon Windows ne voit pas les nouveaux programmes.
```powershell
cd C:\studio
```
```powershell
scripts\studio.cmd doctor
```
En bas du résultat : `"blocking": false` = c'est bon. Sinon, `"advice"` dit quoi installer.

## 4. Connecter Codex (une fois)
```powershell
codex login
```
Puis lance Codex **une fois** dans le dossier du studio, pour qu'il lui fasse confiance :
```powershell
codex
```
Réponds oui quand il demande s'il peut faire confiance au dossier ; s'il propose de configurer son bac à sable
Windows, accepte. Tape `/model` pour voir les modèles disponibles avec ton compte (note-en un), puis `/quit`.

## 5. Test rapide (5 minutes)
```powershell
scripts\studio.cmd tts-test --out test_voix.wav
```
Écoute `test_voix.wav` (voix Piper). Puis un plan de la démo, rendu par Blender :
```powershell
scripts\studio.cmd voice ep_demo_grillepain --force
```
```powershell
scripts\studio.cmd compile ep_demo_grillepain --force
```
```powershell
scripts\studio.cmd render ep_demo_grillepain --shots sh_001 --profile draft --out renders/test.mp4
```
Ouvre `episodes\ep_demo_grillepain\renders\test.mp4` : Kevin animé, avec voix et sous-titres.

## 6. Produire une vidéo : le tableau de bord
Double-clic sur **Studio TikTok 3D** (Bureau), ou :
```powershell
scripts\dashboard.cmd
```
Le navigateur s'ouvre sur `http://127.0.0.1:8765` (page locale, invisible depuis Internet). Laisse la fenêtre noire
ouverte tant que tu utilises la page.

1. En haut : coche **Mode autonome**, choisis **Rendu final** (`final` = 1080p ; `preview` = plus rapide), mets le
   **Modèle Codex** vu avec `/model` (ou laisse vide = modèle par défaut de ton compte), clique **Enregistrer**.
2. **+ Nouvelle vidéo** : colle ton script (une réplique par ligne ; `Prénom: réplique` pour un personnage, la ligne
   telle quelle pour le narrateur) ou choisis « Une histoire » pour que Codex écrive le script. Clique **Créer la vidéo**.
3. Suis l'épisode :
   - **Avancement** : chaque étape (script, personnages, storyboard, animation, motion design, voix, rendus…),
     qui travaille dessus, les erreurs, bouton **Réessayer** si une étape est bloquée ;
   - **Vérifications** : contrôles automatiques des rendus et avis des critiques ;
   - **Vidéos & images** : planches de contrôle, prototype, premier montage, **vidéo finale** ;
   - **Voix & sons** : ta propre voix pour une réplique, ta musique, un bruitage sur un mot précis ;
   - **Journal** : ce que font le pilote et Codex, en direct.
4. **Arrêter** coupe proprement (rendus compris) ; **Lancer / reprendre** repart là où ça s'était arrêté (les images
   déjà rendues sont gardées). Fermer le tableau de bord n'arrête PAS une production en cours.

La vidéo finale : `C:\studio\episodes\<épisode>\renders\final.mp4`. Rien n'est jamais publié automatiquement.

## 7. Reprendre un épisode commencé ailleurs (ex. ep_chloe sur le VPS)
Depuis PowerShell, dans `C:\studio` (remplace l'adresse ; `scp` est inclus dans Windows) :
```powershell
scp -r ubuntu@ADRESSE_DU_VPS:/opt/studio/episodes/ep_chloe episodes\
```
Leçons apprises par les agents sur le VPS (facultatif) :
```powershell
scp -r ubuntu@ADRESSE_DU_VPS:/opt/studio/memory/local memory\
```
L'épisode apparaît dans le tableau de bord ; **Lancer / reprendre**. Les rendus sont refaits sur le PC (le cache du VPS
n'est pas copié). Pour garder exactement la même voix, utilise la même voix Piper que sur le VPS
(`config\local.toml`, section `[tts]`). Depuis une ancienne copie ZIP sur le PC : copie simplement le dossier
`episodes\<épisode>` dans `C:\studio\episodes\`.

## 8. Mettre à jour
Ferme le tableau de bord, puis :
```powershell
cd C:\studio
```
```powershell
git pull
```
Tes épisodes et `config\local.toml` ne sont jamais touchés. Si une mise à jour ajoute des dépendances :
`py -3.12 -m pip install -r requirements.txt`.

## 9. Sans tableau de bord (ligne de commande)
Sous Windows, chaque `scripts/studio` de la documentation devient `scripts\studio.cmd`.
```powershell
scripts\studio.cmd produire episodes\_inbox\mon_script.txt
```
(`--libre` pour une histoire brute, `--duree 60`, `--nom ep_xxx`.) Reprendre : `scripts\studio.cmd produire ep_xxx`.
```powershell
scripts\studio.cmd status ep_xxx
```
```powershell
scripts\studio.cmd arreter ep_xxx
```
Mode non autonome : les validations se font dans PowerShell, par toi, avec `scripts\studio.cmd approve <ep> <gate>`.

## 10. Économiser les tokens Codex
- **Économe** (case en haut du tableau de bord) : l'orchestrateur raisonne en effort bas (il ne fait surtout que
  déléguer) et chaque revue n'a droit qu'à 1 tour de correction au lieu de 2. Les rôles gardent leur propre effort.
- Le total de tokens s'affiche par épisode (liste et bandeau) ; le journal donne le coût de chaque session Codex.
- Un script imposé coûte moins cher qu'une histoire libre (pas d'écriture à faire).
- Les rendus, la voix, le montage et les contrôles ne consomment AUCUN token : seules l'écriture, la mise en scène
  et les critiques passent par Codex.
- Ta consommation et tes limites : tape `/status` dans `codex`.

## Problèmes fréquents
| Message | Solution |
|---|---|
| `No module named 'tomllib'` | Python trop ancien. `winget install --id Python.Python.3.12 -e`, rouvre PowerShell, `py -3.12 -m pip install -r requirements.txt`. |
| `winget n'est pas reconnu` | Installe « App Installer » depuis le Microsoft Store. |
| `codex` / `ffmpeg` / `git` introuvable juste après l'installation | Ferme et rouvre PowerShell ; sinon redémarre le PC. |
| Tableau de bord : « ✗ Codex » | `npm install -g @openai/codex` (Node.js : `winget install --id OpenJS.NodeJS.LTS -e`), rouvre PowerShell, `codex login`. |
| Journal : « Codex introuvable » ou modèle refusé | Même chose ; pour le modèle : `/model` dans `codex`, puis le recopier dans le tableau de bord (ou laisser vide). |
| `l'exécution de scripts est désactivée` | Utilise exactement la commande du §2 (avec `-ExecutionPolicy Bypass`). |
| `doctor` : « installer Blender » alors qu'il l'est | `setx BLENDER_BIN "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"` (adapter la version), rouvre PowerShell. |
| `doctor` : « aucun moteur TTS » | Relance l'installateur et réponds O pour Piper (ou installe espeak-ng). |
| Rendu très lent | Sans carte graphique, mets **Rendu final = preview** dans le tableau de bord. |
| Le port 8765 est occupé | Le tableau de bord prend automatiquement le suivant (l'adresse est affichée dans la fenêtre noire). |
| Accents illisibles dans la console | `chcp 65001` avant les commandes. |

Si ça bloque : envoie le message d'erreur exact, ou une capture, avec la sortie de `scripts\studio.cmd doctor`.
Plan B si Windows natif résiste : WSL (Linux dans Windows), `wsl --install -d Ubuntu-24.04`, puis suivre `VPS.md` §2
dans la fenêtre Ubuntu (rendu sur le processeur uniquement).
