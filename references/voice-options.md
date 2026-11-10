# Options de voix françaises (comparatif honnête)

| Option | Local | Qualité FR | Matériel | Licence / coût | Statut dans le pipeline |
|---|---|---|---|---|---|
| **Piper** (OHF-Voice/piper1-gpl, `pip install piper-tts`) | oui | bonne, naturelle pour de la narration ; expressivité limitée | CPU suffit (temps réel) | moteur GPL-3.0 ; **chaque voix a sa propre licence** (voir sa fiche MODEL_CARD : certaines voix FR sont utilisables commercialement, d'autres non) | backend `piper` implémenté, **non testé dans l'environnement de développement** (modèles non téléchargeables ici) |
| **espeak-ng** | oui | robotique | négligeable | GPL-3.0 (outil) | backend `espeak` implémenté et **testé** — développement/tests uniquement |
| **Voix humaine enregistrée** | oui | la meilleure expressivité | micro | vous | backend `recorded` : `episodes/<ep>/audio/recorded/l001.wav`… |
| TTS neuronaux plus expressifs (ex. modèles de clonage/expressifs open source) | oui (GPU conseillé) | variable, souvent meilleure prosodie | GPU 6–12 Go | licences de poids souvent NON commerciales : vérifier une par une | via backend `command` (adaptateur) |
| Services cloud (ElevenLabs, Azure, Google…) | non | très bonne | — | **payant** (crédits/abonnement) | backend `command` facultatif ; clé dans l'environnement ; journaliser `studio cost` |

## Recommandation
1. Production : Piper avec une voix FR dont la fiche autorise l'usage commercial, ou votre propre voix.
2. Dialogues de personnages : une voix/locuteur ou un `pitch` différent par personnage (`cast_bible[*].voice`).
3. Les nuances (`delivery.emotion/rate/pitch/pause_after_ms`) sont mappées sur débit/hauteur : Piper et
   espeak ne jouent pas réellement les émotions. Une écoute humaine reste nécessaire.

## Alignement mot à mot
Par défaut : bornes de réplique exactes (silences retirés) + répartition proportionnelle aux syllabes estimées
(±0,1 s par mot). Suffisant pour sous-titres et lip-flap cartoon. Amélioration possible : aligneur forcé
local (ex. WhisperX/faster-whisper avec timestamps de mots) qui remplacerait `audio.word_timings` sans
changer le contrat (`tts.alignment`).

## Configuration Piper
```toml
[tts]
backend = "piper"
piper_model = "assets/voices/<voix>.onnx"   # + <voix>.onnx.json à côté
```
`scripts/studio voice <ep>` : seules les répliques modifiées sont resynthétisées (cache par contenu).
