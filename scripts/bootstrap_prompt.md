# Prompt initial à lancer dans Codex (compléter / vérifier l'environnement)

À coller dans Codex ouvert à la racine du dépôt :

```
Tu travailles dans le studio TikTok 3D de ce dépôt. Lis AGENTS.md, puis references/limitations.md.

Objectif de cette session : vérifier et compléter l'environnement sur CETTE machine, sans rien publier.
1. Lance `scripts/studio doctor` et résume les points bloquants ; ne lance pas d'installation réseau
   toi-même : donne-moi les commandes exactes à exécuter (scripts/install.sh).
2. Vérifie que tu vois le skill `tiktok-3d-studio` et les 11 rôles de `.codex/agents/` ; liste-les.
3. Lance `python3 -m pytest -q -m "not blender"` puis `python3 -m pytest -q -m blender` et rapporte les résultats
   bruts (nombre de tests passés/échoués, erreurs).
4. Si un GPU est disponible avec le binaire Blender : passe `render.engine = "eevee"` dans une copie de
   config, lance `scripts/studio check-shots ep_demo_grillepain --force`, REGARDE
   episodes/ep_demo_grillepain/checks/shots_contact.png et compare avec le rendu Cycles. Signale les écarts
   (contours, transparence, exposition) au rôle pipeline-engineer.
5. Délègue à `visual-critic` la revue du prototype de l'épisode de démonstration (skill $visual-review),
   puis montre-moi son rapport. Ne valide aucune gate : c'est mon rôle.
6. Termine par la liste de ce qui a été réellement vérifié, avec preuves, et de ce qui reste à faire
   (references/limitations.md, priorités P1 d'abord).
```

Pour démarrer une production : voir README §2.
