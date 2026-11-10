# Studio TikTok 3D pour Codex

Environnement Codex qui fabrique des vidéos TikTok narratives **françaises** en **3D cartoon low-poly**
(9:16, 1080×1920, H.264/AAC) : script, personnages et décors procéduraux Blender, animation pilotée par la
voix, sous-titres, previews, critiques indépendantes et validations humaines avant tout rendu final.
Rien n'est jamais publié automatiquement.

- Workflow et DAG : [`references/workflow.md`](references/workflow.md)
- Architecture : [`references/architecture.md`](references/architecture.md)
- Audit Codex (sourcé) : [`references/codex-capabilities-audit.md`](references/codex-capabilities-audit.md)
- Audit make-short + choix : [`references/make-short-audit.md`](references/make-short-audit.md)
- Limites et priorités : [`references/limitations.md`](references/limitations.md)

## 1. Installation
```bash
scripts/install.sh
```
Prérequis : Python ≥ 3.11, FFmpeg (libass + libx264), Blender ≥ 4.2 (binaire, idéalement avec GPU) **ou**
le module `bpy` (headless, CPU), espeak-ng (tests) et de préférence Piper + une voix FR à licence commerciale.
Diagnostic à tout moment :
```bash
scripts/studio doctor
```

## 2. Utilisation avec Codex
Ouvrir Codex à la racine du dépôt (le marquer « trusted » pour charger `.codex/config.toml`), puis :

> Crée un épisode TikTok 3D de 90 secondes à partir de cette histoire : [TEXTE]. Style cartoon low-poly goofy,
> humour absurde, personnages originaux, mises en scène dynamiques. Génère le script, les personnages, les
> décors et une preview de validation.

Le skill `tiktok-3d-studio` s'active (ou `$tiktok-3d-studio …`). L'orchestrateur crée l'épisode, délègue aux
sous-agents (`.codex/agents/`), fait tourner `scripts/studio`, et **s'arrête à chaque gate humaine** :

| Gate | Ce que vous regardez | Commande (dans VOTRE terminal) |
|---|---|---|
| script | `episodes/<ep>/story_script.json` + revue du script-critic | `scripts/studio approve <ep> gate_script` |
| lookdev | `episodes/<ep>/lookdev/contact_sheet.png` | `scripts/studio approve <ep> gate_lookdev` |
| prototype | `episodes/<ep>/renders/prototype.mp4` (5–10 s animées, voix, sous-titres) | `scripts/studio approve <ep> gate_prototype` |
| first cut | `episodes/<ep>/renders/first_cut.mp4` + `reviews/` + `qa_first_cut.json` | `scripts/studio approve <ep> gate_first_cut` |

Ensuite seulement : `scripts/studio final <ep>` → `renders/final.mp4` + `episode_manifest.json` (rapport des
vérifications réellement effectuées). Publication : manuelle.

## 3. Utilisation sans agent (pipeline seul)
```bash
scripts/studio new ep_mon_histoire --story-file episodes/_inbox/mon_histoire.txt --duration 90
scripts/studio status ep_mon_histoire
scripts/studio validate ep_mon_histoire
scripts/studio run ep_mon_histoire            # étapes automatiques prêtes
scripts/studio check-shots ep_mon_histoire    # 1 image de contrôle par plan + contrôles de scène
scripts/studio frames ep_mon_histoire renders/prototype.mp4 --per-shot
scripts/studio memory search camera insert
```
Itérations de travail hors DAG : `--force` sur `voice`, `compile`, `lookdev`, `prototype`, `check-shots`,
`first-cut`, ou `scripts/studio render <ep> --shots sh_003,sh_004 --profile draft`.

## 4. Exemple complet
`episodes/ep_demo_grillepain/` : histoire originale (« Toasty, le grille-pain influenceur », ~35 s),
tous les contrats validés, 10 plans, 3 personnages, planche de contrôle et prototype rendus.

## 5. Profils et coûts
`config/profiles.toml` : `draft` (360×640, 1 image/2), `preview` (540×960), `final` (1080×1920).
Limites : `config/studio.toml [limits]` (rendus parallèles, timeout par plan, taille de cache).
Mesures réelles (CPU 4 cœurs, Cycles) : draft ≈ 1,2 s/image, preview ≈ 7,5 s/image → utilisez un GPU
(binaire Blender, EEVEE) pour des previews d'épisodes complets. Logiciels : gratuits ; inférence Codex :
votre offre ; services externes facultatifs : à journaliser (`scripts/studio cost`).

## 6. Tests
```bash
python3 -m pytest -q -m "not blender"     # rapide : contrats, état, voix, compilation, QA vidéo, config Codex
python3 -m pytest -q -m blender           # rendus Blender réels (quelques minutes)
```
Correspondance avec les critères d'acceptation : A `doctor`/install ; B,C `test_codex_config.py` (statique) +
vérification en exécution ci-dessous ; D `test_contracts.py` ; E,F,G,H,I,J `test_blender_e2e.py`,
`test_qa_video.py`, `test_state.py`, `test_pipeline_audio_compile.py`.

### Vérifier Codex en exécution (B, C)
Dans Codex : taper `/skills` (le skill `tiktok-3d-studio` doit apparaître), puis demander
« Délègue à un sous-agent `script-critic` la relecture de episodes/ep_demo_grillepain/story_script.json » :
le rôle doit être proposé et lancé. Non interactif : `scripts/codex_batch.sh ep_demo_grillepain visual-critic prototype`.

## 7. Faire évoluer
- Nouvelle capacité (action, accessoire, décor) : `blender/engine/` + `registry.py` + schéma + doc
  `references/engine-capabilities.md` (le test `test_schema_vocab_matches_engine` garde la cohérence).
- Nouveau skill : `$skill-creator` dans Codex, à placer dans `.agents/skills/`.
- Construire/compléter l'environnement avec Codex : [`scripts/bootstrap_prompt.md`](scripts/bootstrap_prompt.md).
