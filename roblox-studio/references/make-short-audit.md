# Audit de nocodehack/make-short et choix d'architecture

Dépôt étudié : `github.com/nocodehack/make-short` (branche master, clone du 10/11/2026). Licence **MIT**
(© 2026 NoCodeHack) ; sons `v3/voice/sfx/*.mp3` générés via l'API ElevenLabs par l'auteur (droits de ces
fichiers non précisés au-delà de la mention) ; three.js MIT ; polices OFL.

## Ce que fait make-short
- **Skill Claude Code** (`SKILL.md`), pas Codex. Workflow : mesure d'une vidéo de référence → histoire
  « paradoxe » (gate humaine) → voix (enregistrement + Whisper, ou ElevenLabs payant) → `CONTRACT.md` +
  `shots.json`/`acting.json` → gate stills (`gate.py` : bandes saturation/luminance via `signalstats`) → rendu
  natif → **critique frais** (sous-agent qui n'a pas construit le film, rubrique notée, findings par plage de
  frames) → corrections par « beat director » (`beats/<nom>.json` fusionnés) → leçons (`references/lessons.md`).
- **Moteur Blender v3** : `scene.py` (≈ 630 lignes) intègre décors (`lib/sets.py`), personnages « haricots »
  (`lib/chars.py` : poses clés, visages, encre par coque inversée), look/grades (`lib/look.py`), caméra
  auto-cadrée sur les positions réelles + anti-occlusion par lancer de rayons, transitions dans le compositeur.
- Rendu EEVEE GPU, scripts bash pour Windows/Git Bash, Node pour la voix et le mix.

## Points forts à reprendre (idées, pas code)
1. Critique indépendant et « ne jamais s'auto-noter » (+ vérifier les affirmations du critique).
2. Cadrage automatique à partir des positions évaluées + anti-occlusion (repris et généralisé dans `camera.py`).
3. Une réplique = un beat = une image lisible ; tenue de réaction après chaque gag.
4. Fichiers d'override par agent pour paralléliser sans collision (repris : un artefact = un propriétaire).
5. Leçons écrites après chaque tour (repris : `memory/`, récupération ciblée).
6. Rendu à la résolution de livraison, re-rendu partiel par plages.

## Limites majeures pour notre besoin
1. **Moteur mono-film** : `scene.py` contient des identifiants de plans et des numéros de frames codés en dur
   (`s25`, frame 1133, ouvre-boîte 1858, marteau 1383…), quatre décors (`camp`, `insert`, `night`, `tent`) et trois
   personnages (soldats « haricots » de la guerre de Sécession). Chaque nouvelle histoire impose de réécrire
   le moteur : incompatible avec des histoires absurdes variées et un personnage original par épisode.
2. Pas de schéma JSON validé ni de règles croisées : désynchronisations possibles (leçon 24c : ids de plans
   changés silencieusement).
3. Minutage en frames absolues dans `shots.json` : modifier la voix casse la synchronisation.
4. Anglais, voix enregistrée ou ElevenLabs payant ; Whisper anglais.
5. Windows + Git Bash + Node ; pas d'état de job persistant ni de reprise structurée ; cache non adressé par contenu.
6. QA chiffrée limitée (bandes de couleur) ; pas de contrôle de cadrage générique, de son, de spécifications MP4.

## Trois stratégies comparées
| | Adaptation directe | Fork + refonte partielle | **Pipeline indépendant (retenu)** |
|---|---|---|---|
| Effort initial | faible | moyen-élevé (démêler scene.py) | moyen |
| Généralité (histoires variées) | nulle (moteur mono-film) | moyenne | élevée (data-driven) |
| Français, TTS local | à ajouter | à ajouter | natif |
| Contrats validés, reprise, cache | absents | à greffer | natifs |
| Codex natif (agents TOML, skills) | non | à réécrire | natif |
| Dette | maximale | élevée (code dense, hypothèses Windows) | faible |
| Coût marginal par épisode | réécriture du moteur | modifications fréquentes | 0 code (données seulement) |

**Choix : pipeline indépendant**, en reprenant les *principes* éprouvés (critique frais, cadrage auto,
anti-occlusion, leçons) et quelques leçons adaptées dans `memory/lessons.md` (avec attribution MIT).
Aucun fichier de make-short n'est copié ; aucune dépendance à ses sons (licence ElevenLabs non clarifiée).
Justification économique : le coût dominant d'une production régulière est la modification du moteur par
épisode ; un moteur piloté par données le ramène à zéro.
