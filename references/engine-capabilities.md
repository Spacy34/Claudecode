# Capacités du moteur Blender (vocabulaire autorisé dans les contrats)

Source de vérité : `blender/engine/registry.py` (le test `test_capabilities` vérifie l'égalité avec les schémas).
Version moteur : voir `ENGINE_VERSION`. Tout ce qui n'est pas listé n'existe pas.

## Conventions spatiales
Mètres. Sol z=0. Caméra côté -Y (« quatrième mur » ouvert). y+ = vers le fond. Mur du fond à y=+3
(décor 8×6 par défaut). Personnage regardant la caméra : `facing: "camera"` (0°). `facing: 45` = 3/4 vers +X.
`facing: "<ch_id|pr_id|mark>"` = regarder cette cible. Taille d'un personnage ≈ 1,5 m × `height`.

## Décors (`kit`) et repères par défaut
Tous : center (0,0), left (-1.3,0), right (1.3,0), back (0,1.5), front (0,-1.2), far_left (-2.4,0.6),
far_right (2.4,0.6), offscreen_left (-6,0), offscreen_right (6,0).
- living_room : couch (0,1.85) [assis], tv (-2.4,0.9), door (3.4,2.3), window (1.9,2.3)
- kitchen : counter (-0.4,1.9) [plan de travail h=0.92 à y≈2.55], stove (-2.3,1.9), fridge (2.5,1.8), table (2.0,-0.3)
- bedroom : bed (-1.9,0.6), door (3.3,2.3), window (1.4,2.3)
- bathroom : toilet (-1.6,2.0), sink (1.4,2.0)
- office : desk_left (-1.7,0.7), desk_right (1.7,0.7), shelf (0,2.2)
- street : sidewalk_left (-1.5,0), sidewalk_right (1.5,0), road (0,3.8), bench (-1.5,0.9)
- park : bench (0.2,1.8), tree (-2.6,2.0), path (0,0.5)
- supermarket : aisle (0,1.6), cart (1.5,0)
- studio_void : fond uni (lookdev, plans « abstraits »)
Personnalisation : `palette`, `dressing` (accessoires supplémentaires), `marks`, `use_kit_dressing:false`
(désactive aussi l'habillage d'ambiance), `seed` (variante d'habillage reproductible).
Habillage automatique v2 : sols et murs texturés procéduralement (parquet, carrelage, papier peint rayé,
briques, herbe, asphalte), soubassement + moulures, objets muraux (affiches, horloge, étagères garnies,
placards, rideaux, suspensions), petits objets posés (bocaux, bouteilles, assiettes, livres, fruits) qui
évitent les accessoires du plan, fenêtres avec vue (ciel, collines, immeuble). Extérieurs en couches :
rue = trottoirs pavés, façades avec enseignes, skyline, nuages ; parc = herbe, collines, rangée de sapins,
fleurs, barrière, nuages ; ciel en dégradé. Galerie de contrôle : `scripts/studio kits`.
Hauteurs de surfaces : table/desk 0.76, counter/stove 0.92, bed 0.55, sofa 0.45, chair 0.47.

## Accessoires (`type`)
sofa, table, chair, tv, fridge, stove, counter, toaster, plant, lamp, door, window, car, tree, bush, bench,
desk, computer, phone, mug, bed, toilet, box (avec `label`), trash_can, cake, sign (avec `label`), pigeon, cat,
frying_pan, fire_extinguisher, shopping_cart, shelf, rug, streetlight, building, painting.
`scale` 0.2–5, `color`. Un objet sans type dédié = `box`/`sign` + `label` (ex : enceinte « BASS »).

## Personnages (cast_bible.design)
Corps : height, girth, head_scale, leg_length, arm_length, belly. Coiffures : none, short, spiky, bowl, mohawk,
bun, long, curly. Hauts : tshirt, shirt, hoodie, suit, dress, tank. Bas : pants, shorts, skirt.
Accessoires : cap, glasses, sunglasses, tie, bowtie, mustache, beard, chef_hat, headband, earrings, crown.
Nez : round, long, pointy, potato. Rig : hiérarchie d'articulations rigides (low-poly segmenté), pas de skinning.

## Expressions
neutral, happy, laugh, sad, angry, shocked, scared, smug, disgusted, confused, deadpan, crying (larmes),
evil_grin, love (joues roses). Transition 3 images. Clignements automatiques. Lip-flap automatique sur les
mots des répliques du personnage présent dans le plan (approximation syllabique, pas de phonèmes).

## Actions (animation_plan.actions)
| action | effet | durée typique | `target` |
|---|---|---|---|
| idle | respiration/balancement (automatique si auto_idle) | — | — |
| walk_to / run_to | déplacement, cycle de pas lié à la distance (pas de glissement) | auto selon distance | mark ou [x,y] (obligatoire) |
| turn_to | pivot avec petit saut | 0,2 s | cible |
| look_at | tourne la tête (le corps si > 70°) | — | cible |
| wave, point, shrug, facepalm, arms_crossed, hands_on_hips, lean_in | poses tenues avec dépassement | duration_s | point : cible |
| talk_gesture | gestes de bras pendant la parole | duration_s | — |
| nod, shake_head | oui / non | 0,5–1 s | — |
| jump, shocked_jump | anticipation, saut, réception | 1 s | — |
| stomp, flail, dance, celebrate, cower | boucles comiques | duration_s | — |
| take_hit | recul + secousse | 0,7 s | — |
| fall_back, slip_fall, faint | chute au sol (reste couché) | 0,6 s | — |
| sit / stand_up | s'asseoir (hauteur 0,45) / se relever | 0,4 s | — |
| throw | élan + lancer (combiner avec prop throw) | 0,9 s | cible |
`intensity` 0.2–2 amplifie la pose.

## Accessoires animés (animation_plan.props)
attach (dans la main `hand` L/R de `char`), detach, appear, disappear, throw (trajectoire balistique vers
`target`), fall (tombe sur le support), shake, explode (+ explosion), spin.
Un accessoire tenu dès le début : `held_by` dans le storyboard.

## Effets (animation_plan.fx)
smoke_puff, explosion, sparkles, impact_star, sweat_drops, question_marks, hearts. `target` = personnage
(tête), accessoire (dessus) ou mark ; `scale`.

## Caméra (storyboard.camera)
Cadrages : wide, full, medium, medium_close, close_up, extreme_close_up, two_shot (sujet + secondary_subject),
over_shoulder, insert (accessoire). Angles : eye, low, high, dutch, top_down. `side_deg` : azimut autour du
sujet. `lens_mm` optionnel. Mouvements : static, push_in, pull_out, pan_left, pan_right, orbit_left,
orbit_right, track_subject, shake (sur l'impact), crash_zoom, handheld.
Cadrage AUTOMATIQUE sur les positions réelles évaluées ; azimut figé au début du plan ; anti-occlusion par
lancer de rayons (la caméra MONTE d'abord pour regarder par-dessus un obstacle, puis se rapproche en dernier
recours) ; un objet posé sur un meuble n'est jamais filmé en contre-plongée.

## Ambiances (`mood`)
day_warm, day_cool, night, interior_warm, office_flat, dramatic, spooky, sunset.

## Transitions (`transition_out`)
cut, whip (flou + whoosh), smash_cut (thud), fade_black, flash_white (pop).

## Contrôles automatiques dans Blender (scene_report)
char_never_visible, char_offscreen, subject_too_small, head_cropped, face_under_subtitles, face_away,
foreground_occluder (meuble qui bouche le premier plan), out_of_set, inside_furniture, char_overlap, floating_prop. Ils ne jugent pas l'esthétique.
