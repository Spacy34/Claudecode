# Problèmes récurrents relevés par les critiques

Une entrée par section `## `.

## Prototype utilisateur (chef Basile) : personnages de dos, sourcils flottants, rendu terne
tags: visage, dos, sourcils, couleurs, contours, mise-en-scene
date: 2026-11-11

Retour utilisateur sur un épisode réel. Corrigé dans le moteur : facing vers un personnage limité à ±65° (triche caméra), retour face caméra en fin de walk_to, tête limitée (tangage -20/+16°), sourcils glissant sur la surface de la tête, aplats semi-émissifs + contours 2x plus épais, exposition -0,45 + contraste. Nouveau contrôle face_away et avertissement de plans consécutifs identiques. Reste : décors pauvres (pas de texture/profondeur), acting du corps limité.
