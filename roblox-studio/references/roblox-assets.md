# Avatars, objets et maisons Roblox : export, import, droits

Le studio rend les vidéos dans **Blender**. Les contenus Roblox y entrent par **deux commandes**, toujours lancées
par l'utilisateur, jamais par téléchargement automatique : `studio avatar-add` (avatars) et `studio asset-add`
(objets, meubles, maisons, décors). Sans import, le studio fabrique tout seul des avatars et des décors en blocs
originaux (fiche `cast_bible.design`, kits de décor) : rien d'importé n'est obligatoire.

## 1. Droits (à lire avant tout import)
- Vérifier les **conditions d'utilisation actuelles de Roblox** avant de publier des vidéos monétisées contenant
  des avatars ou objets exportés de Roblox (filmer Roblox est courant ; exporter des modèles pour un rendu hors
  de Roblox est une zone à vérifier). Le studio ne tranche pas cette question à votre place.
- Le plus sûr : **vos propres créations** (avatars et objets que vous avez faits) ou des modèles dont la licence
  autorise explicitement l'usage hors Roblox et commercial.
- Les accessoires du catalogue appartiennent à leurs créateurs : ne pas les importer sans droit.
- Jamais de logo ou de marque Roblox dans les vidéos, jamais de personnage d'un jeu existant.
- Chaque import exige `--license` et `--commercial-confirmed` ; la licence est consignée dans la bibliothèque.

## 2. Exporter un avatar depuis Roblox Studio (sur PC)
1. Ouvrir Roblox Studio, un lieu vide (Baseplate).
2. Insérer l'avatar en R15 (onglet Avatar : outil de création de rig, ou votre avatar chargé dans le lieu).
3. **Retirer le visage** (le décalque `face` de la tête) : le studio dessine son propre visage (expressions et
   bouche synchronisée). Garder les accessoires (cheveux, chapeaux, sacs…).
4. Sélectionner le modèle entier dans l'Explorateur, puis exporter la sélection en **.obj** (menu Fichier ou clic
   droit, selon la version de Studio). Studio écrit le `.obj`, le `.mtl` et les textures `.png` côte à côte.
5. Copier ce dossier sur le serveur (ex. `scp -r MonAvatar/ studio@IP:roblox-studio/episodes/_inbox/`).

## 3. Importer l'avatar
```bash
rstudio avatar-add episodes/_inbox/MonAvatar/MonAvatar.obj --id kevin_rbx --license "création personnelle" --source "mon compte" --commercial-confirmed
```
Le studio vérifie les pièces R15 (Head, UpperTorso, LowerTorso, Left/RightUpperArm, LowerArm, Hand, UpperLeg,
LowerLeg, Foot ; R6 accepté), range tout dans `assets/roblox/avatars/kevin_rbx/` et répond avec la ligne à mettre
dans la fiche du personnage :
```json
"design": {"roblox_avatar": "kevin_rbx", "body": {"height": 1.0}, "skin": "#F2B880", "hair": {"style": "none"}, "outfit": {...}}
```
Au rendu : squelette déduit des pièces, accessoires accrochés à la bonne pièce, visage du moteur posé sur la tête,
toutes les animations et emotes disponibles. Lister : `rstudio avatar-list`.
Contrôle visuel obligatoire : `rstudio lookdev <ep>` puis regarder la planche (pièces bien placées, textures).

## 4. Objets, meubles, maisons (Creator Store ou vos créations)
Même export .obj depuis Studio, puis :
```bash
rstudio asset-add episodes/_inbox/Canape/Canape.obj --name canape_rouge --license "création personnelle" --commercial-confirmed --target-height 0.9
```
La réponse donne le bloc à ajouter dans `asset_manifest.json` (prop `source: external`). Une maison entière se
place de la même façon (grand `target_height`, posée au fond du décor par l'environment-artist).

## 5. Sans import : ce que le studio fabrique seul
- Avatars en blocs depuis la fiche : tenues (motifs, inscription, vestes), coiffures en blocs, 23 accessoires,
  postures par personnalité.
- Décors : maison de banlieue `suburb` (étage, toit, porche, volets, garage, clôture, haies), intérieurs (salon,
  cuisine, chambre, salle de bain, bureau, classe, restaurant, supermarché), rue, parc, plage.
