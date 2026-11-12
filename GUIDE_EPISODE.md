# Produire un nouvel épisode (processus complet, sur le VPS)

Deux terminaux dans tmux : **panneau gauche = Codex**, **panneau droit = toi** (validations, contrôles).
```bash
tmux new -A -s studio
```
`Ctrl+b` puis `%` : ouvre le panneau droit. `Ctrl+b` + flèche : changer de panneau. `Ctrl+b` puis `d` : détacher.

## 0. Préparer (une fois par VPS)
Dans `config/studio.toml`, petit VPS : `prototype_profile = "draft"` et `first_cut_profile = "draft"`.

## 1. Écrire l'histoire (panneau droit)
```bash
cd /opt/studio && git pull
```
```bash
nano episodes/_inbox/mon_histoire.txt
```
Colle l'histoire brute (quelques lignes suffisent), `Ctrl+O` Entrée, `Ctrl+X`.

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
