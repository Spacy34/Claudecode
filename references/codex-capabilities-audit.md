# Audit des capacités Codex utilisées par ce studio

## Méthode et limites de l'audit
- **Sources consultées** : le code source officiel `github.com/openai/codex`, commit
  `36e074a2fb365aa788886495c82e6ea612226cd9` (10/11/2026), en particulier :
  `codex-rs/core/config.schema.json` (schéma JSON de `config.toml`, copie épinglée dans `references/codex/`),
  `codex-rs/agent-roles/src/{agent_role_config,loader,discovery}.rs`, `codex-rs/core/src/agent/role.rs`,
  `codex-rs/ext/skills/src/{host_roots.rs,loader/}`, `codex-rs/skills/src/assets/samples/skill-creator/`,
  `codex-rs/exec/src/cli.rs`.
- **Non consultées** : les pages `developers.openai.com/codex/*` et l'article de blog demandé n'étaient pas
  joignables depuis l'environnement de construction (domaine hors liste réseau autorisée). Les `docs/*.md` du
  dépôt ne font que rediriger vers ces pages. **Conséquence** : tout ce qui suit est vérifié dans le code, pas
  dans la documentation ; les noms d'outils internes exacts côté modèle (ex. nom de l'outil de spawn) n'ont pas
  été figés dans les instructions — elles parlent de « déléguer au rôle `agent_type` », formulation que l'outil
  de spawn de Codex documente lui-même au modèle.
- Codex CLI n'a pas pu être exécuté ici (pas d'authentification) : les tests B et C sont statiques (voir tests).

## 1. Sous-agents natifs et agents personnalisés — VÉRIFIÉ
- Rôles intégrés : `default`, `explorer`, `worker` (`awaiter` retiré temporairement) — `core/src/agent/role.rs`.
- Rôles personnalisés : tout fichier `*.toml` sous `<dossier de config>/agents/` (récursif) de chaque couche de
  configuration → `.codex/agents/` du projet et `~/.codex/agents/` — `agent-roles/src/loader.rs` (`config_folder.join("agents")`).
  Aussi déclarables dans `config.toml` : `[agents.<nom>]` avec `description`, `config_file`, `nickname_candidates`.
- Format d'un fichier de rôle (`RawAgentRoleFileToml`, `deny_unknown_fields`) : `name`, `description`,
  `nickname_candidates` + **n'importe quelle clé valide de config.toml**. `developer_instructions` est
  obligatoire et non vide pour un fichier découvert ; `description` non vide ; surnoms ASCII sans doublon.
- **Point important** : seules certaines clés du fichier de rôle sont appliquées à l'enfant —
  `developer_instructions`, `model`, `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`,
  `personality`, `service_tier`, la *désactivation* de certaines features (`shell_tool`, `apps`, `plugins`,
  `memory_tool`, `request_permissions_tool`) et la *désactivation* de skills. « Roles may customize the child or
  reduce its capabilities, but never replace the parent session's authority » (role.rs). Un `sandbox_mode =
  "read-only"` dans un rôle n'est donc PAS appliqué : le caractère « lecture seule » des critiques est imposé
  ici par (a) leurs instructions, (b) la propriété exclusive des fichiers, (c) `studio submit`, qui refuse une
  revue dont la cible a changé (hash) et ne valide que des rapports conformes au schéma.
- Un modèle/effort fixé dans le rôle est verrouillé et annoncé au modèle parent dans la description du rôle.

## 2. Configuration `config.toml` — VÉRIFIÉ (schéma)
`.codex/config.toml` (couche projet, chargée pour un projet de confiance) utilise : `approval_policy`
("on-request"), `sandbox_mode` ("read-only" | "workspace-write" | "danger-full-access"),
`[sandbox_workspace_write] network_access`, `[agents] max_concurrent_threads_per_session` (≥ 1),
`max_depth`, `enabled` (défaut true), `default_subagent_model`, `default_subagent_reasoning_effort`,
`[features] multi_agent` (booléen), `[profiles.<nom>]`. `model_reasoning_effort` est une chaîne « annoncée par le
modèle » : on n'y met que low/medium/high. Le test `tests/test_codex_config.py` valide le fichier contre le schéma.

## 3. AGENTS.md — VÉRIFIÉ partiellement
Clés `project_doc_max_bytes` (défaut 32 768 octets) et `project_doc_fallback_filenames` présentes dans le schéma.
`AGENTS.md` est gardé court (< 8 Ko) ; les détails sont en `references/` (chargés à la demande).

## 4. Skills — VÉRIFIÉ
- Emplacement dépôt : `.agents/skills/<nom>/SKILL.md` (constantes `AGENTS_DIR_NAME=".agents"`,
  `SKILLS_DIR_NAME="skills"`, `host_roots.rs`) ; utilisateur : `$CODEX_HOME/skills` ; profondeur max 6.
- Frontmatter : `name` (≤ 64), `description` (≤ 1024) ; clés admises par le validateur officiel : name,
  description, license, allowed-tools, metadata. Métadonnées UI facultatives : `agents/openai.yaml`
  (`interface.display_name`, `short_description`, `default_prompt`, `policy.allow_implicit_invocation`).
- Invocation explicite `$nom-du-skill` ; invocation implicite par description (activée par défaut).
- `$skill-creator` : skill d'exemple intégré (`skills/src/assets/samples/skill-creator`), utilisable pour faire
  évoluer nos skills.
- Config `[skills]` : `config = [{name|path, enabled}]`, `bundled.enabled`, `include_instructions`,
  `max_context_tokens` (catalogue ≈ 2 % du contexte, plafonné à 10 000 tokens) → descriptions courtes.

## 5. Parallélisme et limites — VÉRIFIÉ
`agents.max_concurrent_threads_per_session` (doit être ≥ 1) ; `max_depth` (V1). Une variante
`features.multi_agent_v2` existe (timeouts d'attente, etc.) : non utilisée (expérimentale).

## 6. Mémoire entre sessions
Un sous-système `memories` existe (`[memories]`, features `memories`/`memory_tool`) mais il est automatique et
non ciblé : on ne s'y fie PAS pour la production. La mémoire de production est faite de fichiers versionnés
(`memory/*.md`) interrogés par `studio memory search` (récupération ciblée).

## 7. MCP
`mcp_servers` configurable. Aucun MCP n'est nécessaire : Blender est piloté par scripts Python déterministes,
plus robustes et testables qu'un pont MCP Blender interactif. Un MCP ne serait utile que pour un service
externe facultatif (non retenu par défaut).

## 8. Exécution non interactive — VÉRIFIÉ (CLI)
`codex exec` accepte `--output-schema <fichier>` (sortie finale structurée validée par schéma), `--json`
(évènements JSONL), `--output-last-message`, `--ephemeral`, `--skip-git-repo-check`, `--image`, et
`codex exec resume [--last | <id>]`. Utilisation retenue : `scripts/codex_batch.sh` lance une étape (ex. une revue)
en mode non interactif ; l'agent écrit son rapport JSON puis `studio submit` le valide contre le VRAI schéma
(`$ref`, motifs, bornes). `--output-schema` n'est pas utilisé pour les contrats : les contraintes exactes qu'il
accepte (mode strict des sorties structurées) n'ont pas pu être vérifiées ici, et nos schémas utilisent
`oneOf`/`$ref`/`pattern`. La validation programmatique côté pipeline reste la garantie.

## 9. Multimodal
Features `view_image` et `image_detail_original` présentes dans le schéma ; `codex exec --image` joint des
images. Les critiques inspectent des PNG extraits (frames, planches contact) — jamais « la vidéo ».

## 10. Sandbox, permissions, reprise
Sandbox `workspace-write` sans réseau par défaut ; approbation « on-request ». Reprise de session Codex :
`codex resume` / `codex exec resume`. Reprise de PRODUCTION : indépendante de Codex, via `state.json`.

## 11. Modèles et effort
Aucun identifiant de modèle n'est figé dans le dépôt (disponibilité variable selon le compte). Les rôles
fixent seulement l'effort (low/medium/high). Pour figer un modèle : `model` dans `.codex/config.toml` ou dans
un rôle, après vérification avec `/model` dans Codex.
