---
name: visual-review
description: Procédure d'inspection visuelle honnête d'un rendu (lookdev, prototype, contrôle des plans, first cut) — extraction de frames horodatées, examen image par image, rapport review_report.json avec preuves. Pour visual-critic, continuity-auditor et retention-editor.
---

# visual-review

1. Identifier la cible et son hash : `sha256sum episodes/<ep>/<cible>`.
2. Extraire les images (ne jamais prétendre regarder une vidéo) :
   - par plan : `scripts/studio frames <ep> <vidéo> --per-shot` (ajouter `--relative` pour un extrait comme le prototype) ;
   - moments clés : `--at <t1>,<t2>` (temps des actions : `shot_manifest.json` + mots ancrés dans `animation_plan.json`) ;
   - accroche : `--every 0.5` sur les 3 premières secondes.
3. Regarder chaque PNG avec l'outil d'affichage d'image ; commencer par `contact.png`, puis zoomer sur les
   images suspectes. Lire en parallèle la réplique du plan (`story_script.json`).
4. Confronter aux contrôles automatiques (`checks/scene_checks.json`, `qa_*.json`) : confirmer/infirmer.
5. Écrire `reviews/<rôle>_<gate>_r<N>.json` selon `schemas/review_report.schema.json` et la grille
   `references/review-rubrics.md`. Chaque finding : `time_s`/`shot_id`, preuve (chemin + observation),
   recommandation actionnable, `fix_owner`. `inspected` = liste exacte des fichiers vus (method "view_image").
6. `scripts/studio submit <ep> <étape> --review <fichier>`.

Si l'outil d'image est indisponible : verdict "revise", `limitations` explicite, demander une revue humaine.
Ne jamais modifier autre chose que son rapport.
