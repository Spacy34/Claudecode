# Modèles 3D externes (bibliothèque)

Ajout UNIQUEMENT via la commande (contrôle de licence + inspection + vignette) :

```
scripts/studio asset-add chemin/vers/modele.glb --name tracteur --license CC0-1.0 --source-url https://... --target-height 2.2
```

- Formats : `.glb` (recommandé), `.gltf` (+ .bin/textures voisins), `.obj`. FBX : convertir d'abord en .glb dans Blender.
- Licences acceptées d'office : CC0-1.0, CC-BY-4.0/3.0 (attribution obligatoire, reportée dans le manifeste
  de l'épisode), MIT, Apache-2.0. Toute autre licence : vérifier soi-même puis `--commercial-confirmed`.
  Jamais de NC (non commercial), jamais de modèle « trouvé » sans licence claire.
- Refus automatique : import impossible, > `limits.max_external_faces` faces, textures manquantes. Les modèles
  avec armature sont acceptés comme objets STATIQUES seulement (le moteur ne joue pas leurs animations).
- Sources de modèles low-poly CC0 cohérents avec le style du studio (à télécharger vous-même, licence à
  vérifier sur la page de chaque modèle) : Kenney (kenney.nl), Quaternius (quaternius.com), Poly Haven
  (polyhaven.com, plutôt réaliste).
- Chaque modèle ajouté a son dossier : `model.<ext>`, `asset.json` (licence, empreinte, inspection), `thumbnail.png`.
