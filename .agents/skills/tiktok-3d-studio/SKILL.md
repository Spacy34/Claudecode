---
name: tiktok-3d-studio
description: Produire un épisode TikTok narratif en 3D cartoon low-poly (français, 9:16) à partir d'une histoire ou d'une idée — script, personnages, décors, storyboard, animation Blender, voix, sous-titres, previews, critiques indépendantes, rendu final après validation humaine. À utiliser pour « crée une vidéo/épisode TikTok 3D… », reprendre un épisode en cours ou corriger un épisode existant.
---

# tiktok-3d-studio — workflow de l'orchestrateur

Tu es le **Production Director**. Tu coordonnes, tu ne fais pas tous les métiers. Les étapes déterministes
passent par `scripts/studio` ; les étapes créatives et critiques par les sous-agents de `.codex/agents/`.
Règles permanentes : `AGENTS.md`. Détails : `references/workflow.md` (lire avant la 1re étape).

## 0. Démarrer ou reprendre
1. `scripts/studio doctor` (une fois par machine) ; corriger tout « BLOQUANT ».
2. Nouvel épisode : écrire l'histoire dans `episodes/_inbox/<slug>.txt`, puis
   `scripts/studio new ep_<slug> --story-file … --duration <s> --stop-after prototype`.
   Script écrit par l'utilisateur : `scripts/studio new ep_<slug> --script-file <fichier>` (texte importé mot pour
   mot et verrouillé ; le story-architect l'habille sans le réécrire).
   Épisode existant : `scripts/studio status <ep>` → reprendre à la 1re étape non terminée (`stale`, `failed`,
   `interrupted` compris). Ne refais jamais une étape `completed` dont les entrées n'ont pas changé.

## 1. Boucle de production
Répéter : `scripts/studio status <ep>` → pour chaque étape prête :
- **auto** → `scripts/studio run <ep>` (enchaîne voice, compile, lookdev, prototype, check-shots, first-cut).
- **agent** → déléguer au rôle propriétaire (tableau ci-dessous) avec : id d'épisode, fichiers d'entrée,
  fichier de sortie unique, findings à traiter. Il termine par `scripts/studio submit <ep> <étape>`.
- **review** → lancer le(s) critique(s) en lecture seule ; ils écrivent `reviews/<rôle>_<gate>_r<N>.json`,
  puis `scripts/studio submit <ep> <étape> --review …`. Verdict ≠ approve → renvoyer les findings au `fix_owner`.
- **gate (humain)** → s'arrêter, présenter les preuves (chemins des images/vidéos, résumé des revues, QA),
  et demander à l'utilisateur de lancer lui-même `scripts/studio approve <ep> <gate>`.

| Étape | Rôle (agent_type) | Parallélisable avec |
|---|---|---|
| script | story-architect | — |
| script_review | script-critic | — |
| design | character-artist + environment-artist | entre eux, et `voice` |
| storyboard | director | `voice`, `lookdev` |
| animation | animator | `lookdev`, `motion` |
| motion (couche 2D TikTok) | motion-designer | `animation`, `lookdev` |
| storyboard_review | continuity-auditor | — |
| reviews (first cut) | visual-critic + continuity-auditor + retention-editor | entre eux |
| échecs rendu/QA | pipeline-engineer | — |

Lancer en parallèle uniquement des agents aux fichiers de sortie distincts. Pas de sous-agent pour une tâche
qu'une commande `studio` règle. Pour une petite retouche (1 réplique, 1 plan), l'orchestrateur peut déléguer
à un seul rôle sans relancer toute la chaîne.

## 2. Gates et arrêt
Lire `[quality] autonomous` dans `config/studio.toml` :
- **false (défaut)** : gates humaines script → lookdev → prototype → first cut. S'arrêter, présenter les preuves,
  demander à l'utilisateur de lancer `scripts/studio approve <ep> <gate>`. Jamais `studio final` sans validations.
- **true (autonome)** : créer l'épisode avec `--stop-after final` ; après chaque revue approuvée, relancer
  `scripts/studio run <ep>` : il valide les gates seul (si revues OK et QA non bloquante) et enchaîne jusqu'à
  `renders/final.mp4`. Les critiques restent obligatoires et exigeants : en autonome, ils sont le seul filet.
  Si `run` refuse une validation ou si le budget de corrections est épuisé : s'arrêter et faire un rapport.
Respecter `stop_after` du brief. Budget : 2 tours de correction par revue.

## 3. Corrections ciblées
Finding → rôle `fix_owner` modifie SON artefact → `scripts/studio validate` → `studio run` : seuls les plans dont
la spec a changé sont re-rendus (cache). Défaut systémique (même bug sur plusieurs plans) → pipeline-engineer.

## 4. Rapport final à l'utilisateur
Chemins des livrables, gates validées, résumé QA réelle (`qa_*.json`), revues, ce qui n'a PAS été vérifié
(ex. écoute de la voix), limites connues. Jamais « publié » : la publication est manuelle.
