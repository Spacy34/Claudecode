---
name: episode-authoring
description: Règles pour rédiger les contrats créatifs d'un épisode (story_script, cast_bible, asset_manifest, storyboard, animation_plan) compatibles avec le moteur Blender — vocabulaire autorisé, ancrages sur les mots, repères des décors, validation. Pour story-architect, character-artist, environment-artist, director, animator.
---

# episode-authoring

- Schémas : `schemas/<contrat>.schema.json`. Exemple complet et validé : `episodes/ep_demo_grillepain/`.
- Vocabulaire du moteur (actions, expressions, cadrages, mouvements, kits, marks, accessoires, effets) :
  `references/engine-capabilities.md`. Tout ce qui n'y figure pas n'existe pas : demander au pipeline-engineer.
- Enveloppe obligatoire : `contract`, `contract_version` "1.0", `episode_id`, `status`, `provenance`
  (`created_by` = ton rôle, `created_at` ISO, `revision`).
- Temps : jamais de secondes absolues. Ancrages `{"line":"l003","word":2}` (index de mot = découpage sur espaces,
  ponctuation collée) ou `{"shot_t":0.5}`. Les timecodes sont calculés par `scripts/studio compile`.
- Identifiants stables : `ch_*`, `set_*`, `pr_*`, `sh_###`, `l###`, `b##`. Ne jamais renuméroter des identifiants
  publiés : ajouter `sh_004b` plutôt que décaler.
- Après écriture : `scripts/studio validate <ep>` (schéma + cohérence croisée) jusqu'à zéro erreur, puis
  `scripts/studio submit <ep> <étape>`.
- Mémoire utile : `scripts/studio memory search <thème>` (lire seulement les entrées retournées).
