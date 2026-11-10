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
