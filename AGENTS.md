# AGENTS.md — Studio TikTok 3D (Codex)

Instructions permanentes pour tout agent Codex travaillant dans ce dépôt. Elles priment sur les habitudes
par défaut. Les détails sont dans `references/` : ne les charger que lorsque la tâche l'exige.

## Mission du dépôt
Produire des vidéos TikTok narratives françaises (9:16, 1080×1920, H.264/AAC, 60–120 s par défaut) en 3D
cartoon low-poly « goofy », où **chaque plan illustre réellement ce que dit la voix**. Production
reproductible par épisode, contrôlée par des critiques indépendants et des validations humaines.

## Carte du dépôt
- `pipeline/studio/` : pipeline déterministe (CLI `scripts/studio`) : voix, timing, compilation, rendu, montage, QA, état.
- `blender/engine/` : moteur Blender Python (personnages, rig, animations, décors, caméra, effets, contrôles de scène).
- `schemas/` : contrats JSON (source de vérité). `references/` : guides détaillés. `config/` : presets et limites.
- `episodes/<episode_id>/` : un dossier par vidéo (artefacts, `state.json`, rendus, revues).
- `.codex/agents/` : rôles spécialisés. `.agents/skills/` : workflows (`tiktok-3d-studio` = point d'entrée).
- `memory/` : mémoire de production (interroger avec `scripts/studio memory search …`, ne jamais tout lire).

## Règle d'or : déterministe d'abord
Tout ce qu'un script fait de façon fiable passe par `scripts/studio` : synthèse vocale, minutage, conversion
ancrages→frames, rendu, encodage, mixage, sous-titres, mesures techniques, planches contact, état du job.
Le raisonnement des agents est réservé à l'écriture, la mise en scène, la direction artistique et la critique.
Ne jamais recalculer à la main un timecode, ni éditer un fichier GÉNÉRÉ (`audio_timeline.json`,
`shot_manifest.json`, `shots/*.json`, `render_manifest*.json`, `qa_*.json`, `episode_manifest.json`, `state.json`).

## Commandes essentielles
```
scripts/studio doctor                          # diagnostic matériel/logiciel
scripts/studio new <ep> --story-file f.txt --duration 90
scripts/studio status <ep>                     # état du DAG, étapes prêtes, artefacts périmés
scripts/studio validate <ep>                   # schémas + cohérence croisée + capacités moteur
scripts/studio submit <ep> <étape> [--review reviews/x.json]
scripts/studio run <ep>                        # exécute les étapes automatiques prêtes
scripts/studio frames <ep> <video> --per-shot  # frames horodatées pour les critiques
scripts/studio retake-done <ep> <rNNN> --note …  # retouche utilisateur appliquée (--failed si impossible)
scripts/studio memory search <mots>
python3 -m pytest -q tests                      # tests automatiques
```
**Windows (PowerShell)** : toujours `scripts\studio.cmd` à la place de `scripts/studio` (mêmes arguments) ;
`scripts/studio` est un script bash, PowerShell ne sait pas l'exécuter.

## Propriété des fichiers (un seul écrivain par artefact)
| Artefact | Propriétaire |
|---|---|
| `story_script.json` | story-architect |
| `cast_bible.json` | character-artist |
| `asset_manifest.json` | environment-artist |
| `storyboard.json` | director |
| `animation_plan.json` | animator |
| `motion_design.json` (couche 2D TikTok) | motion-designer |
| `voice` (config voix dans `cast_bible.json[*].voice`, `audio/recorded/`) | voice-sound (via le character-artist pour cast_bible) |
| `reviews/<rôle>_<gate>_r<N>.json` | le critique concerné, uniquement son fichier |
| `blender/engine/`, `pipeline/` | pipeline-engineer (avec tests) |
| tout fichier généré | `scripts/studio` uniquement |

Un agent ne modifie jamais l'artefact d'un autre rôle : il signale le problème (finding avec `fix_owner`).

## Règles absolues
1. **Aucune publication** automatique, jamais. Le livrable s'arrête à `renders/final.mp4` + `episode_manifest.json`.
2. **Validations** : par défaut, `gate_script`, `gate_lookdev`, `gate_prototype`, `gate_first_cut` se valident
   UNIQUEMENT par l'utilisateur dans un terminal (`scripts/studio approve …`). Si la config (`config/studio.toml`,
   surchargée par `config/local.toml`) a `[quality] autonomous = true`, c'est `scripts/studio run` qui les valide automatiquement (revues approuvées +
   QA non bloquante) et enchaîne jusqu'au rendu final. Dans les deux cas, un agent ne lance JAMAIS `approve`,
   ne modifie jamais ce réglage lui-même et ne contourne jamais une gate (`--force` = itérations de travail).
3. **Critiques indépendants et en lecture seule** : un critique n'édite que son rapport ; il n'évalue jamais un
   travail qu'il a produit ; il ne « valide » pas par défaut.
4. **Honnêteté d'inspection** : ne jamais affirmer avoir vu une vidéo. On inspecte des IMAGES extraites
   (`studio frames`, planches contact) et on liste dans `inspected` exactement ce qui a été regardé et comment.
   Si aucune image n'a pu être vue, le dire dans `limitations` et demander une inspection humaine.
5. **Les tests techniques verts ne prouvent pas qu'une vidéo est réussie.** Toujours une revue visuelle.
6. **Droits** : personnages, décors, sons et musiques originaux ou sous licence compatible usage commercial,
   licence consignée dans `asset_manifest.json`. Pas de personnage, marque ou style protégé copié.
7. **Secrets** : aucune clé dans les fichiers versionnés ; variables d'environnement uniquement. Toute dépense
   (TTS externe, GPU loué) est journalisée avec `scripts/studio cost`.
8. **Pas de code externe non vérifié** : aucun téléchargement/exécution de script tiers sans le montrer à l'utilisateur.
9. **Budget de corrections** : `quality.max_revision_rounds` (2 par défaut) par revue ; au-delà, escalade humaine.
   Un problème bloquant l'emporte toujours sur une bonne moyenne.
10. **Périmètre en production** : pendant la production d'un épisode (pilote, `scripts/produire.sh`), seuls les
    fichiers de `episodes/<ep>/` sont modifiables. Code, tests, schémas, config et `.codex/` ne se modifient que si
    l'utilisateur le demande explicitement (rôle pipeline-engineer) ; sinon, signaler le problème dans le rapport.
11. **Correction ciblée** : corriger le plus petit artefact responsable ; le cache ne re-rend que les plans changés.
12. **Décisions humaines** : une gate validée par l'utilisateur avec `approve --override --note …` consigne une décision
    (affichée par `studio status`, transmise par le pilote). Elle s'impose à tous, critiques compris : ne plus bloquer
    pour ce motif, seulement vérifier que ses conditions (ex. « aucun visuel copié ») sont respectées.

## Contenu trash / humour noir
Analyse contextuelle (voir `references/platform-policy.md`) : signaler les vrais risques (personnes réelles
identifiables, incitation dangereuse imitable, haine visant un groupe protégé, contenu sexuel, mineurs) avec
une proposition de reformulation, sans stériliser l'humour absurde ou noir.

## Avant de terminer une tâche
- `scripts/studio validate <ep>` sans erreur pour les artefacts touchés ; `python3 -m pytest -q tests` si du code a changé.
- Rapport : ce qui a été fait, ce qui a été réellement vérifié (avec preuves), ce qui ne l'a pas été.
- Nouvelle erreur Blender ou leçon validée → `scripts/studio memory add --category … --title … --tags … --text …`.
