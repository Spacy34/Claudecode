# Recettes de mise en scène éprouvées

But : **réussir du premier coup**. Ces montages passent la pré-vérification (`scripts/studio preflight <ep>`) et
lisent bien en 9:16. Partir d'une recette et l'adapter vaut mieux qu'improviser des positions.
Conventions : caméra côté **-Y** (devant), fond = **+Y**, unités en mètres, `facing` = `"camera"`, un id de
personnage, ou un angle en degrés (0 = face caméra, + = vers +X).

## 1. Dialogue à deux, décor lisible (plan d'installation)
```json
"characters": [{"id": "A", "mark": [-0.6, 1.0], "facing": "B"}, {"id": "B", "mark": [0.6, 1.0], "facing": "A"}],
"camera": {"framing": "two_shot", "subject": "A", "secondary_subject": "B", "angle": "eye", "move": "static",
           "motivation": "On installe la relation et le lieu."}
```
- Écart 1,0–1,4 m : assez pour que les deux visages tiennent dans le 9:16 sans se toucher.
- Les corps se « trichent » seuls vers la caméra (±65° max) ; celui qui écoute tourne la tête vers celui qui
  parle et hoche la tête sur les longues répliques **automatiquement** : ne rien ajouter dans animation_plan.
- Garder 1 m de libre derrière eux si le décor a des meubles (sinon le plan paraît collé au mur).

## 2. Champ / contrechamp sans « personnage jamais visible »
```json
"characters": [{"id": "A", "mark": [0.0, 1.0], "facing": "camera"}, {"id": "B", "mark": [0.9, 0.2], "facing": "A", "offscreen": true}],
"camera": {"framing": "over_shoulder", "subject": "A", "secondary_subject": "B", "angle": "eye", "move": "static", "motivation": "…"}
```
- Celui qui est de dos/hors champ est marqué `"offscreen": true` (voix hors champ voulue, pas de bloquant).
- Alterner `over_shoulder` et `medium_close`, jamais deux `close_up` de suite.

## 3. Entrée dans le plan (marche)
- storyboard : le personnage commence **dans le décor** mais au bord du cadre (`mark` à ±1,8 m du centre) ;
  `move: "track_subject"` ou `static` en `full`/`wide`.
- animation_plan : `{"char": "A", "action": "walk_to", "at": {"line": "l00X", "word": 0}, "target": [0.3, 1.0], "duration_s": 1.2}`
  — 1 m/s environ ; la cible est un point **libre** (≥ 0,6 m des autres personnages et accessoires au sol).

## 4. Gag + réaction (le cœur du rythme TikTok)
1. Plan large/full où l'action est lisible (`subject` = celui qui agit, accessoire visible).
2. Coupe sur le mot fort (`"start": {"line": "l00X", "word": N}`) vers un plan de **réaction** court
   (0,5–0,8 s, `medium_close` ou `close_up`) avec une expression forte (`shocked`, `deadpan`, `crying`…).
3. Retour à un plan ouvert ensuite (le compilateur interdit deux plans serrés d'affilée).

## 5. Insert sur un objet posé
```json
"props": [{"id": "pr_x", "mark": [0.3, 2.45], "height": 0.92}],
"camera": {"framing": "insert", "subject": "pr_x", "angle": "high", "move": "static", "motivation": "…"}
```
- `height` = hauteur du meuble (comptoir 0,92 ; table/bureau 0,76) : sinon objet flottant.
- Si l'histoire fait LIRE un écran de téléphone, pas d'insert 3D : le motion designer l'affiche en 2D et le plan
  montre la réaction du personnage.

## 6. Portage d'un gros objet
- `held_by` + objet ≥ 30 % de la taille du personnage = portage automatique **à deux mains**, devant le ventre.
- Petits objets (téléphone, tasse, assiette) : une main (`"hand": "R"`). Jamais d'objet posé au sol sur le repère
  d'un personnage (≥ 0,6 m d'écart).

## 7. Lieu public vivant (rue, restaurant, bureau, soirée, classe, magasin)
```json
"extras": {"count": 3, "activity": "chat", "zone": "back"}
```
- Les figurants se placent seuls **derrière** l'action, hors des repères, en duos qui discutent (`chat`), seuls
  (`idle`) ou qui traversent (`walk`). `zone: "sides"` dans un décor peu profond.
- 2 à 5 par plan ; aucun dans une scène intime. Ils ne parlent pas et ne sont pas contrôlés par les critiques.
- Si le décor n'a pas de place derrière, le moteur les omet et le signale (conseil de la pré-vérification).

## 8. Répartition des cadrages sur un épisode
≈ 40 % ouverts (wide / full / two_shot), ≈ 35 % medium / medium_close / over_shoulder, ≤ 25 % close_up + insert,
≤ 2 extreme_close_up. Chaque changement de lieu commence par un plan d'installation. La pré-vérification affiche
`decor_visible` (plans ouverts / total) : viser au moins 4/10.
