# Grilles de critique (appréciations indicatives, pas des mesures)

## Sévérités
- **blocker** : empêche la validation quelles que soient les notes (illisible, faux raccord majeur, plan noir,
  personnage cassé au premier plan, risque juridique/plateforme sérieux, réplique non illustrée au climax).
- **major** : dégrade nettement la compréhension ou la qualité perçue ; à corriger avant le rendu final.
- **minor** : amélioration souhaitable. **info** : remarque.
Règle : un seul blocker ⇒ verdict ≠ approve. Une bonne moyenne ne compense jamais un blocker.
Mécanique (studio submit) : SEULS les findings `blocker` déclenchent un tour de correction ; les `major`/`minor` sont des
notes. Un blocker `fix_owner: human` arrête tout de suite pour décision de l'utilisateur (pas de tour d'agents). Après
`max_revision_rounds` tours, les blockers restants sont acceptés AVEC RÉSERVES (`quality.on_budget_exhausted = "continue"`,
défaut) et listés dans `episode_manifest.json`. Contrôles de rendu : seuls les défauts qui rendent la vidéo inutilisable
(sévérité blocker, rendu en échec, personnage principal jamais visible) bloquent ; les autres deviennent des réserves.

## §script (script-critic) — dimensions `scores`
hook, clarte, escalade, comique, payoff, rythme_oral, faisabilite_visuelle, conformite, originalite.
Questions : comprend-on l'enjeu en 2 s ? chaque palier est-il pire ET visible ? y a-t-il une réplique
« ventre mou » sans information ? la chute est-elle préparée ? quelles lignes couper ?

## §storyboard (continuity-auditor)
couverture (chaque intention visuelle filmée), lisibilite_action, continuite, variete_plans, faisabilite.

## §visuel (visual-critic)
lisibilite_mobile, composition_9x16, eclairage, personnages (anatomie, expressions), decors, animation,
correspondance_recit, bugs (flottants, collisions, hors champ, noirs, maillages).
Checklist par image : sujet identifiable en 0,5 s ? visage dans la moitié haute ? quelque chose d'important
sous les sous-titres ? contours lisibles ? exposition correcte (ni gris, ni brûlé) ? objet héros reconnaissable ?
la réplique du plan est-elle illustrée ?

## §continuité (continuity-auditor)
identite_personnages, accessoires, positions, regards_180, chronologie, synchro_narration_action.

## §rétention (retention-editor)
accroche_3s, densite, longueur_plans, variete_visuelle, silences, sous_titres, payoff.

## Format des findings
`F01`… ; `shot_id`, `time_s` quand applicable ; `evidence` = chemin d'image + observation factuelle ;
`recommendation` = action précise (quel champ de quel artefact changer) ; `fix_owner` = rôle propriétaire.
