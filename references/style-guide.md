# Guide de style — cartoon 3D low-poly « goofy »

## Intention
Énergie des histoires absurdes racontées en voix off sur TikTok, mais avec un univers 3D PROPRE au studio :
personnages originaux, couleurs franches, facettes low-poly visibles, contours encrés, acting exagéré.
Ne pas reproduire les personnages, décors, polices ou habillages d'une chaîne existante.

## Personnages
- Grosse tête (head_scale 1.0–1.3), grands yeux expressifs, sourcils épais = moteur de l'expression.
- 2 traits signatures minimum (couleur du haut + coiffure/accessoire). Pas deux personnages au même haut.
- Couleurs saturées qui contrastent avec le décor ; peaux variées.
- Réactions toujours plus grandes que nature : choc = saut + yeux ronds ; honte = facepalm ; colère = stomp.

## Décors
- Lisibles en 1 s : un lieu = un kit + 2–4 objets signatures. Palette murs pastel, sol plus clair/foncé que les murs.
- Les objets « héros » de l'histoire sont plus gros que nature (scale 1.2–1.6) et étiquetés si besoin.
- Fond calme derrière les visages (pas d'objet très contrasté derrière la tête).

## Mise en scène 9:16
- Visages dans la moitié haute ; sous-titres vers 68 % de la hauteur : rien d'important derrière.
- Valeurs de plan variées : alterner gros plan / plan moyen / insert. Plan large ≤ 1,5 s sauf action.
- Un plan = une information. Couper sur le mot qui révèle (ancrage `start`).
- Caméra calme par défaut ; mouvements motivés (push_in pour une révélation, shake pour un impact,
  handheld pour un vlog, crash_zoom pour une chute comique). Pas de mouvement permanent.
- Lumière : `interior_warm`/`day_warm` par défaut ; `dramatic` pour l'emphase ironique ; `spooky`/`night` rares.

## Rythme comique
Setup → anticipation (2–4 images) → gag sur le mot → tenue de réaction 0,4–0,8 s → coupe.
Bruitage sur l'impact visuel, pas avant.

## Sous-titres
Majuscules, 2–3 mots, mot courant surligné en jaune et légèrement grossi, contour noir épais.
