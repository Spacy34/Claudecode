# Réglages qui fonctionnent

## Expositions par ambiance (Cycles, vue Standard)
tags: lumiere, exposition, interior_warm
date: 2026-11-10

interior_warm : monde 0,55, soleil 2,4 ; day_warm : monde 0,7, soleil 3,0. Avec des forces supérieures, les murs
pastel deviennent blancs à l'écran.

## Temps de rendu mesurés (CPU 4 cœurs, module bpy 5.2.3, Cycles)
tags: rendu, performance, cpu
date: 2026-11-10

draft 360×640, 4 échantillons, 1 image sur 2 : ≈ 1,2 s/image. preview 540×960, 8 échantillons : ≈ 7,5 s/image.
Construction d'une scène : 5–15 s.

## Décors v2 : textures procédurales et surfaces claires
tags: decor, texture, exposition, kits
date: 2026-11-12

Les surfaces claires texturées brûlent si elles sont auto-illuminées : pattern_mat réduit l'émission selon la luminance (1 - 1,3 L). Lumières de jour abaissées (day_warm soleil 2,2 monde 0,45 ; office_flat 1,6/0,5). Vérifier tout changement de décor avec 'scripts/studio kits'.
