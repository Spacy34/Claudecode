# Problèmes récurrents relevés par les critiques

Une entrée par section `## `.

## Prototype utilisateur (chef Basile) : personnages de dos, sourcils flottants, rendu terne
tags: visage, dos, sourcils, couleurs, contours, mise-en-scene
date: 2026-11-11

Retour utilisateur sur un épisode réel. Corrigé dans le moteur : facing vers un personnage limité à ±65° (triche caméra), retour face caméra en fin de walk_to, tête limitée (tangage -20/+16°), sourcils glissant sur la surface de la tête, aplats semi-émissifs + contours 2x plus épais, exposition -0,45 + contraste. Nouveau contrôle face_away et avertissement de plans consécutifs identiques. Reste : décors pauvres (pas de texture/profondeur), acting du corps limité.

## Codex sur VPS : modèle non disponible pour un compte ChatGPT
tags: codex, modele, chatgpt, vps, config
date: 2026-11-12

Premier lancement réel : 'The gpt-5.5 model is not supported when using Codex with a ChatGPT account' + avertissement '[profiles] ignorés en config projet'. Correctifs : [profiles] retirés de .codex/config.toml ; modèle choisi par l'utilisateur dans config/local.toml [codex] model (lu par produire.sh, passé via -c model=...) après vérification avec /model.
