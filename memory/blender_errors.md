# Erreurs Blender/rendu et correctifs

## Contours « inverted hull » : image presque noire en Cycles
tags: blender, cycles, contour, outline, shader, ombre
date: 2026-11-10

Symptômes : 1) tout objet encré rendu en noir ; 2) après inversion du mélange, objets très sombres.
Causes : 1) facteurs du Mix Shader inversés (avec normales retournées, la coque côté caméra est « backfacing ») ;
2) la coque émissive noire bloquait les rayons d'ombre → auto-ombrage. Correctif (core.outline_mat) :
fac = max(Backfacing, 1 − IsCameraRay) ; entrée 1 = émission noire, entrée 2 = transparent.

## Insert d'objet : caméra collée à l'objet
tags: blender, camera, insert, occlusion
date: 2026-11-10

Le rayon anti-occlusion partait du centre de l'objet filmé et touchait l'objet lui-même. Correctif : ignorer
les maillages des accessoires du plan et des personnages ; contraindre la largeur de cadre à la largeur de
l'objet ; jamais de contre-plongée sur un objet posé sur un meuble.

## Caméra qui dérive quand le personnage pivote
tags: blender, camera, push_in
date: 2026-11-10

L'azimut était recalculé à chaque clé à partir de l'orientation du sujet (qui pointe un objet). Correctif :
azimut figé à la 1re évaluation du plan (CameraRig.base_az).

## Geste vers une cible : le personnage tournait le dos à la caméra
tags: animation, point, throw, camera, dos
date: 2026-11-10

Constaté au prototype (QA 20/20 mais personnage de dos pendant 1,5 s). point/throw faisaient pivoter tout le corps vers la cible. Correctif : face_to(max_turn) limite la rotation (50° pour point, 70° pour throw) ; le bras fait le reste.
