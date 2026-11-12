# Leçons créatives et techniques validées

Une entrée par section `## `. Ajouter via `scripts/studio memory add`. Ne jamais lire ce fichier en entier :
`scripts/studio memory search <mots>`.

Les entrées marquées [make-short] sont adaptées des leçons publiées par nocodehack/make-short (licence MIT,
© 2026 NoCodeHack), reformulées pour ce pipeline.

## Les chiffres verts ne prouvent pas une bonne image
tags: qa, visuel, critique
date: 2026-11-10

[make-short] Une QA numérique entièrement verte peut accompagner une image ratée. Toujours regarder les images.
Constaté ici aussi au 1er rendu : QA technique 18/19, mais personnages presque noirs (bug de contours).

## Ne jamais s'auto-noter
tags: critique, revue
date: 2026-11-10

[make-short] Un constructeur surestime son travail d'environ 2 points. Seul un critique qui n'a pas produit le
plan note ; et on vérifie aussi ses affirmations à pleine résolution avant d'agir.

## Une réplique, un beat, une image lisible
tags: storyboard, rythme, mise-en-scene
date: 2026-11-10

[make-short] Construire la liste de plans À PARTIR des beats : sur le mot clé, le sujet de l'action est dans le
cadre, gros et net. Tenir la réaction 0,4–0,8 s après chaque gag ; pas d'effet qui masque l'image du gag.

## L'objet du gag dans les mains, près du visage
tags: animation, accessoire, mise-en-scene
date: 2026-11-10

[make-short] Un accessoire posé au sol à côté du personnage se lit comme sans rapport. L'objet héros est tenu,
ou cadré en insert lisible (3/4 en légère plongée).

## Un défaut présent dans plusieurs plans est un bug de moteur
tags: moteur, rig, systemique
date: 2026-11-10

[make-short] Si le même problème apparaît sur 3 plans ou plus, le corriger une fois dans le moteur
(pipeline-engineer), pas plan par plan.

## Rendre à la résolution de livraison pour juger la netteté
tags: rendu, qualite
date: 2026-11-10

[make-short] L'upscale plafonne le détail. Juger la netteté finale sur le profil `final`, pas sur la preview.

## Figer les identifiants publiés
tags: contrats, storyboard
date: 2026-11-10

[make-short] Renuméroter des plans fait référencer des plans différents par des agents différents. Ajouter
`sh_004b` plutôt que décaler ; le timing ne dépend jamais des identifiants (ancrages sur les mots).

## Sous-titres : police TTF/OTF système
tags: sous-titres, ffmpeg, libass
date: 2026-11-10

[make-short] libass ne charge pas les woff2. Utiliser une police OTF/TTF libre (Inter ExtraBold ici) ou en
déposer une dans assets/fonts/.

## Zoom punch : viser le visage, pas le centre du cadre
tags: camera, punch, zoom, montage, saut
date: 2026-11-12

Un zoom vers le centre du cadre coupe la tête si le personnage saute (célébration). add_punch vise le point le plus haut des yeux du sujet pendant la tenue du zoom et réduit l'amplitude en plan large/two_shot.

## Désigner une cible derrière soi : tricher vers la caméra
tags: animation, point, visage, profil, camera
date: 2026-11-12

Rendu VPS de la démo : en pointant le grille-pain derrière lui, Kevin montrait sa nuque (rotation 50°, non détectée car face_away se déclenche à ~80°). Correctif : corps limité à 35°, tête ramenée vers la caméra (60 % de la rotation) pendant le geste ; nouveau contrôle face_profile (sujet trop de profil en plan rapproché).

## Ne jamais faire surveiller un long rendu par Codex
tags: codex, rendu, timeout, pilote, vps
date: 2026-11-12

Premier épisode autonome réel (ep_chloe) : toutes les étapes créatives réussies, mais prototype 'interrupted' : le rendu lancé depuis une commande Codex dépasse sa durée max (et Codex + Blender sur 3 Go de RAM). Correctif : scripts/pilote.py exécute les rendus hors Codex et n'appelle Codex que pour les étapes agent/revue (sessions courtes).
