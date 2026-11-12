# Motion design « TikTok » (motion_design.json)

Couche 2D dessinée par `pipeline/studio/motion.py` (Pillow, formes originales, aucune ressource externe), incrustée
par-dessus la 3D **sous les sous-titres**, dans `first_cut` et `final`. Tout est ancré sur la narration
(`{"line","word","edge","offset_s"}`), jamais en secondes absolues : changer la voix recale tout.

## Éléments (`type`)
| type | usage | champs |
|---|---|---|
| phone | écran de smartphone qui glisse du bord | `screen` (voir ci-dessous), `contact`, `contact_color`, `app`, `messages[]`, `query`, `likes_from/to`, `text` |
| text_pop | carton texte qui « pop » (hook, ellipse « 3 ANS PLUS TARD », punchline) | `text` (≤ 60), `style` impact/label/typewriter, `color` |
| sticker | autocollant animé (oscille) | `icon` : heart, broken_heart, skull, fire, question, exclamation, money, clock, check, cross, star, lightning, laugh, sweat |
| name_tag | étiquette de présentation d'un personnage | `text` (nom), `subtitle` (trait comique), `color` |
| counter | nombre qui défile (argent, vues, jours) | `value_from`, `value_to`, `prefix`, `suffix` (« € », « vues »), `decimals`, `label` |
| arrow | cercle rouge + flèche « regarde ici » | `target` [x, y] en fraction de l'image (origine en haut à gauche), `label` |

Écrans de téléphone (`screen`) :
- `chat` : conversation ; `messages[]` = {from me/them, text, at, typing} ; bulles qui apparaissent sur leur mot,
  indicateur « … » avant les messages reçus.
- `notification` : écran verrouillé + bannières (`messages[].title/text`, `app`).
- `call` : appel entrant de `contact` (avatar, ondes, boutons qui pulsent).
- `post` : publication (`text` = légende de l'image), compteur de « j'aime » `likes_from`→`likes_to`, commentaires = `messages`.
- `search` : `query` tapée lettre par lettre, puis résultats (`messages[].text`).

Timing : `at` (apparition) ; `until` (ancrage) ou `duration_s` (défauts : phone 3,5 s, text_pop 1,6 s, sticker 1,4 s,
name_tag 2,2 s, counter 2 s, arrow 1,6 s). Le téléphone reste au moins jusqu'au dernier message + 1,2 s.
Positions : top, center, left, right, top_left, top_right (zones choisies hors sous-titres et hors boutons TikTok).
`scale` 0.5–1.6. `globals.progress_bar` (défaut true) : barre de progression en haut de l'image.

## Bonnes pratiques
- Un élément = une information que la voix donne au même instant. Sans le son, la vidéo doit rester compréhensible.
- 1 élément toutes les 3–8 s, 2 simultanés au maximum ; un élément fort sur le hook.
- Téléphone du côté opposé au sujet du plan ; pas de `center` sur un gros plan de visage.
- Pas d'émoji dans les textes (police) : utiliser les stickers. Pas de marque réelle (noms d'apps génériques).

## Commandes
`scripts/studio motion-suggest <ep>` (moments repérés dans le script), `scripts/studio motion-preview <ep>`
(planche `checks/motion_contact.png` sans rendu 3D), `scripts/studio validate <ep>`, `scripts/studio submit <ep> motion`.
