# Limitations connues et priorités

| # | Limitation | Impact | Priorité | Piste |
|---|---|---|---|---|
| 1 | Rendu CPU lent : preview 540×960 ≈ 7,5 s/image sur 4 cœurs (Cycles, module bpy) ; un épisode de 60 s en preview ≈ 3–4 h | itérations lentes sans GPU | **P1** | binaire Blender + GPU (EEVEE, `render.engine="eevee"`), `draft` pour itérer, `max_parallel_renders` |
| 2 | EEVEE non testé ici (pas de GPU/affichage) ; le code le sélectionne en mode binaire + GPU | risque de différences de rendu EEVEE/Cycles (contours, transparence) | P1 | lancer `check-shots` en EEVEE une fois sur votre machine et comparer |
| 3 | Voix : seul espeak-ng testé (robotique) ; adaptateur Piper écrit mais non testé (modèles non téléchargeables ici) | qualité audio insuffisante tant que Piper n'est pas configuré | **P1** | installer Piper + voix FR à licence commerciale ; test `test_tts_piper` à ajouter |
| 4 | Lip-sync = lip-flap syllabique, pas de visèmes ; alignement mot à mot proportionnel (±0,1 s) | suffisant en cartoon, imparfait en gros plan long | P2 | aligneur forcé local |
| 5 | Personnages = rig rigide segmenté (pas de déformation, pas de doigts) ; bibliothèque de ~30 actions | acting limité (pas de manipulation fine, pas de course sur chemin courbe) | P2 | nouvelles actions dans `animation.py` (+ registre + schéma) |
| 5b | Décors : textures procédurales simples (pas d'images peintes), habillage fixe par kit (seed pour varier) ; pas encore de « kit » utilisateur composé librement hors des 9 kits | rendu moins riche qu'un décor fait main | P2 | kits supplémentaires (restaurant, salle de classe, plage…), habillage par thème |
| 6 | Pas d'évitement automatique d'obstacles pour walk_to (trajet rectiligne) ; seul un avertissement `inside_furniture` est produit | traversées de meubles possibles | P2 | planification sur grille simple |
| 7 | Assets externes (`source: external`, glTF/FBX) déclarables mais non chargés par le moteur | dépendance au procédural | P2 | importeur glTF + inspection (maillage, échelle, polycount, licence) |
| 8 | Génération 3D par IA locale (image→mesh) non intégrée : les modèles produisent des maillages non riggés de qualité variable | — | P3 | uniquement pour accessoires statiques, après inspection |
| 9 | Critiques multimodaux : dépendent de l'outil d'image de Codex ; non exécutés dans l'environnement de construction | la qualité visuelle doit être jugée par l'humain en attendant | P1 | exécuter le workflow dans Codex et calibrer la grille |
| 10 | La gate humaine repose sur un terminal interactif (TTY) ; un agent disposant d'un PTY pourrait techniquement saisir la confirmation | contournement possible mais visible dans l'historique (`state.json`) | P2 | approbation signée (clé locale) |
| 11 | Musique : boucle procédurale simple | ambiance basique | P3 | bibliothèque CC0 vérifiée |
| 12 | Tests B/C (découverte du skill et des agents par Codex) vérifiés statiquement, pas en exécution | à confirmer sur votre machine | P1 | `codex` puis `/skills` et une délégation de test (README §Vérifier Codex) |
