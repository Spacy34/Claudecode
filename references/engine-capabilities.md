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
- restaurant : table_left (-2.3,0.4), table_right (2.3,0.4), kitchen_pass (1.4,1.9), entrance (3.3,0.6) [tables nappées, bar, ardoise menu]
- classroom : teacher (0,1.9) [devant le tableau], blackboard (0,2.4), desk_left (-2.2,0.6), desk_right (2.2,0.6)
- beach : towel (-1.6,1.0), parasol (1.4,0.8), sandcastle (-0.9,0), water_edge (0,5.5) [mer, île, palmiers, poste de secours]
- car_interior : driver (-0.42,0.25), passenger (0.42,0.25), back_left (-0.42,1.15), back_right (0.42,1.15) —
  personnages en `start_pose: "sit"`, cadrages medium_close/close_up/two_shot conseillés (vue depuis le pare-brise)
- generic_interior / generic_exterior : lieu À COMPOSER (voir « Improviser »)
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
frying_pan, fire_extinguisher, shopping_cart, shelf, rug, streetlight, building, painting,
restaurant_table, wine_glass, plate_food, menu_board (label), cooking_pot, school_desk, blackboard (label = texte à la craie),
backpack, globe, parasol, beach_towel, sandcastle, palm_tree, beach_ball, surfboard, cooler, lifeguard_tower (label),
guitar, pizza, burger, trophy, money_stack, skateboard, bucket.
Animaux (rebond automatique, jamais figés) : pigeon, cat, dog, chicken, duck, rat, fish, cow.

## Improviser ce qui n'existe pas (sans écrire de code)
- **Objet inconnu → `type: "composite"` + `parts`** : l'agent décrit l'objet comme un assemblage de formes
  simples (box, ball, cyl, cone, torus, text) avec `size`, `pos` (centre, sol = z 0, avant = -Y), `rot_deg`,
  `color`, `glow` (écran, néon, flamme), `text`. 40 pièces max. Ex. sous-marin = cyl allongé couché + box
  (kiosque) + cyl fin (périscope) + ball (hublots, glow). Utilisable comme accessoire d'histoire ou dans `dressing`.
- **Lieu inconnu → `kit: "generic_interior"` ou `"generic_exterior"`** + `surfaces` {floor, wall : planks, tiles,
  noise, grass, bricks, wood, stripes ; wainscot} + `palette` + `dressing` (types existants et composites) +
  `backdrop` pour l'extérieur (skyline, hills, trees, sea, clouds) + `marks`. Ex. hôpital = generic_interior
  carrelage blanc/vert + lits (bed) + composites (moniteur, perfusion).
- **Modèle 3D libre → `type: "custom"`, `source: "external"`, `external_path`** (via `scripts/studio asset-add`,
  licence vérifiée) + `target_height` + `rot_offset_deg`. Fichier manquant → caisse rose « MODELE ? » visible
  + avertissement (jamais un trou silencieux).
`scale` 0.2–5, `color`. Un objet sans type dédié = `box`/`sign` + `label` (ex : enceinte « BASS »).

## Personnages (cast_bible.design)
Corps : height, girth, head_scale, leg_length, arm_length, belly. Coiffures : none, short, spiky, bowl, mohawk,
bun, long, curly. Hauts : tshirt, shirt, hoodie, suit, dress, tank, polo, sweater, jersey. Bas : pants, jeans, shorts, skirt.
Garde-robe : `top.pattern` / `bottom.pattern` / `layer.pattern` (plain, stripes, pinstripes, dots, plaid, checker,
denim) + `pattern_color` ; `top.print` (inscription ≤ 12 caractères) + `print_color` ; `top.sleeves` (none/short/long),
`top.collar`, `top.pocket` ; `outfit.layer` {type : jacket, blazer, leather_jacket, lab_coat, apron, vest, puffer,
cardigan ; color, accent} ; `bottom.belt` (couleur) ; `outfit.shoes` = couleur ou {type : sneakers, boots, heels,
sandals, slippers, dress_shoes ; color, sole}.
Accessoires : cap, glasses, sunglasses, tie, bowtie, mustache, beard, chef_hat, headband, earrings, crown, scarf,
necklace, gold_chain, watch, backpack, shoulder_bag, beanie, top_hat, headphones, bandana, badge, flower_pin
(`accessory_colors` : couleur par accessoire). Un chapeau couvrant (beanie, top_hat, chef_hat) aplatit les
coiffures en volume (spiky, curly, mohawk, bun).
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

## Couche « cartoon » automatique (rien à écrire dans les contrats)
- Écrasement-étirement (pivot aux pieds) : sauts (anticipation, décollage, réception), take_hit, stomp,
  célébration, et sursaut du corps sur les expressions shocked/scared (étirement), angry/evil_grin, laugh (rebonds).
- Cheveux et chapeaux en retard sur la tête et le corps (follow-through) ; repos avec rebond.
- Gestes automatiques (talk_gesture) quand un personnage parle ≥ 0,8 s sans action prévue.
- Montage nerveux : zoom « punch » vers le VISAGE du sujet sur les mots forts (`emphasis_words` du script +
  détection auto des chiffres, mots en « ! » et MAJUSCULES ; 2 max par plan, espacés de 1,5 s) ;
  secousse caméra automatique sur chaque impact (take_hit, chutes, stomp, réception de shocked_jump,
  explosion, impact_star) ; sous-titres qui « pop » et mots forts en rouge agrandis ; avertissement de
  compilation au-delà de 4 s par plan.

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
Personnage volontairement hors champ (voix hors champ, entrée plus tard) : `"offscreen": true` dans
`storyboard.shots[].characters[]`. Un personnage jamais visible (`char_never_visible`) est BLOQUANT s'il est sujet /
secondary_subject ou en wide/full/two_shot ; en plan serré sur quelqu'un d'autre (contrechamp, réaction), simple avertissement.
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

## Motion design 2D (couche TikTok)
Téléphone (conversation, notification, appel, post, recherche), textes, stickers, étiquettes, compteurs, flèches :
voir references/motion-design.md (`motion_design.json`, rôle motion-designer).
