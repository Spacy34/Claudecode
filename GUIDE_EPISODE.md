# Produire un nouvel épisode (processus complet, sur le VPS)

## Méthode rapide (recommandée) : une seule commande
```bash
scripts/produire.sh episodes/_inbox/mon_script.txt
```
Importe ton script (verrouillé ; `--libre` pour une histoire brute que Codex réécrit), puis lance le PILOTE en arrière-plan (tmux) : il exécute lui-même les rendus
(sans limite de temps) et n'appelle Codex (`codex exec`, sessions courtes) que pour l'écriture et les critiques, jusqu'à la vidéo finale si `autonomous = true`. Suivi : `tmux attach -t <ep>`,
`scripts/studio status <ep>`, journal `episodes/<ep>/checks/codex_journal.log`, rapport `checks/codex_rapport_final.md`.
Relancer la même commande reprend un épisode interrompu. Prérequis : avoir ouvert `codex` une fois
dans le dossier pour le marquer « trusted ».

La méthode détaillée ci-dessous reste utile pour piloter Codex à la main.

Deux terminaux dans tmux : **panneau gauche = Codex**, **panneau droit = toi** (validations, contrôles).
```bash
tmux new -A -s studio
```
`Ctrl+b` puis `%` : ouvre le panneau droit. `Ctrl+b` + flèche : changer de panneau. `Ctrl+b` puis `d` : détacher.

## 0. Préparer (une fois par VPS)
Tes réglages vont dans `config/local.toml` (créé par `setup_vps.sh`, ignoré par git → aucun conflit au `git pull`).
Petit VPS : `prototype_profile = "draft"` et `first_cut_profile = "draft"` dans `[render]`.

### Mode autonome (aucune validation humaine)
Dans `config/local.toml` : `[quality] autonomous = true`. Petit VPS : `[render] final_profile = "preview"`.
Codex enchaîne alors tout seul jusqu'à `renders/final.mp4` ; l'étape 3 ci-dessous disparaît. Les critiques
indépendants et la QA technique décident à ta place : si l'un d'eux bloque, Codex s'arrête et te fait un rapport.
Message à Codex : « … Mode autonome : va jusqu'à la vidéo finale sans m'attendre. »

## 1. Écrire l'histoire (panneau droit)
```bash
cd /opt/studio && git pull
```
```bash
nano episodes/_inbox/mon_histoire.txt
```
Colle l'histoire brute (quelques lignes suffisent), `Ctrl+O` Entrée, `Ctrl+X`.

### Variante : ton propre script, mot pour mot
Écris le fichier `episodes/_inbox/mon_script.txt` : une réplique par ligne ; `Prénom: texte` (deux-points collé)
quand un personnage parle ; sans préfixe = narrateur ; lignes `#` = commentaires. Puis :
```bash
studio new ep_mon_script --script-file episodes/_inbox/mon_script.txt
```
Le texte est importé et VERROUILLÉ (durée estimée et personnages affichés). Message à Codex :
« Utilise $tiktok-3d-studio. L'épisode ep_mon_script existe avec MON script verrouillé : habille-le sans changer
le texte, puis enchaîne toute la production. »

## 2. Lancer Codex (panneau gauche)
```bash
cd /opt/studio && codex
```
Message à envoyer (adapter la durée) :
> Utilise $tiktok-3d-studio. Crée l'épisode ep_mon_histoire de 45 secondes à partir de episodes/_inbox/mon_histoire.txt.
> Style cartoon low-poly goofy, humour absurde, personnages originaux, mise en scène dynamique.
> Va jusqu'au prototype et arrête-toi à chaque validation humaine.

## 3. Les 4 validations (panneau droit)
Codex s'arrête et te dit quoi regarder. Tu regardes, puis soit tu valides, soit tu lui écris tes remarques.

| Quand Codex dit… | Tu regardes | Tu valides avec |
|---|---|---|
| script prêt | `episodes/ep_mon_histoire/story_script.json` (+ revue du critique dans `reviews/`) | `studio approve ep_mon_histoire gate_script` |
| lookdev prêt | `episodes/ep_mon_histoire/lookdev/contact_sheet.png` | `studio approve ep_mon_histoire gate_lookdev` |
| prototype prêt | `episodes/ep_mon_histoire/renders/prototype.mp4` | `studio approve ep_mon_histoire gate_prototype` |
| first cut prêt | `episodes/ep_mon_histoire/renders/first_cut.mp4` + `reviews/` | `studio approve ep_mon_histoire gate_first_cut` |

Pour regarder une image ou une vidéo, depuis ton PC (PowerShell) :
```powershell
scp ubuntu@IP_DU_VPS:/opt/studio/episodes/ep_mon_histoire/lookdev/contact_sheet.png .
```
Pour lire le script lisiblement sur le VPS :
```bash
python3 -c "import json;[print(l['id'],l['text']) for l in json.load(open('episodes/ep_mon_histoire/story_script.json'))['lines']]"
```
Pour demander une correction, écris-la simplement à Codex (« la chute est faible, rends le proprio plus ridicule »).
Une validation est liée à la version validée : si un fichier change ensuite, il faudra re-valider.

## 4. Suivre et contrôler (panneau droit, à tout moment)
```bash
studio status ep_mon_histoire
```
```bash
studio check-shots ep_mon_histoire --force
```
(→ `checks/shots_contact.png` : 1 image par plan + défauts détectés)

## 5. Rendu final
Après la 4e validation, sur une machine assez puissante (le VPS 2 cœurs mettrait ~1 journée pour 60 s en 1080p) :
```bash
studio final ep_mon_histoire
```
Sortie : `episodes/ep_mon_histoire/renders/final.mp4` (1080×1920) + `episode_manifest.json`.
Machine plus puissante : copier l'épisode (`rsync -av episodes/ep_mon_histoire/ autre_machine:/opt/studio/episodes/ep_mon_histoire/`),
y lancer `studio final`, puis rapatrier `renders/final.mp4`.

## 6. Publier (toi, à la main)
Le pipeline ne publie jamais. Vérifie `episode_manifest.json` (licences, crédits CC-BY éventuels) avant de poster.
