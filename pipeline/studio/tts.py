"""Adaptateurs de synthèse vocale française. Aucun n'est obligatoire ; le pipeline choisit selon la config.

- piper   : TTS neuronal local (recommandé). Modèle .onnx + .onnx.json fournis par l'utilisateur ;
            vérifier la licence de CHAQUE voix (fiche du modèle) avant usage commercial.
- espeak  : espeak-ng (GPL-3.0, local, léger). Voix robotique : développement/tests uniquement.
- command : adaptateur générique vers un TTS externe facultatif (clé dans l'environnement, jamais ici).
- recorded: voix humaine enregistrée (episodes/<id>/audio/recorded/<line_id>.wav).
"""
import os
import shlex
import tempfile
from pathlib import Path

from .util import ROOT, run, which

EMOTION = {  # (multiplicateur de débit, multiplicateur de hauteur)
    "neutral": (1.0, 1.0), "deadpan": (0.92, 0.9), "excited": (1.12, 1.12), "panicked": (1.25, 1.2), "angry": (1.08, 0.95),
    "whisper": (0.9, 1.0), "smug": (0.95, 0.95), "sad": (0.85, 0.88), "disgusted": (0.95, 0.92),
}


def pick_backend(cfg, ep_dir=None):
    b = cfg["tts"]["backend"]
    if b != "auto":
        return b
    if ep_dir and (Path(ep_dir) / "audio" / "recorded").is_dir():
        return "recorded"
    model = cfg["tts"].get("piper_model")
    if model and (ROOT / model).exists() and (which("piper") or _python_has("piper")):
        return "piper"
    if which("espeak-ng"):
        return "espeak"
    raise RuntimeError("Aucun moteur TTS disponible : installer piper (recommandé) ou espeak-ng, ou fournir des enregistrements.")


def _python_has(mod):
    import importlib.util
    return importlib.util.find_spec(mod) is not None


def synth(backend, cfg, text, out_wav, line, voice_cfg=None, ep_dir=None):
    """Produit un WAV brut pour une réplique. Retourne une description de la voix (pour la licence/traçabilité)."""
    voice_cfg = voice_cfg or {}
    d = line.get("delivery", {})
    er, ep = EMOTION.get(d.get("emotion", "neutral"), (1.0, 1.0))
    rate = d.get("rate", 1.0) * er
    pitch = d.get("pitch", 1.0) * ep * voice_cfg.get("pitch", 1.0)
    out_wav = Path(out_wav)
    if backend == "espeak":
        v = voice_cfg.get("espeak_voice", cfg["tts"]["espeak_voice"])
        if d.get("emotion") == "whisper":
            v = v.split("+")[0] + "+whisper"
        speed = int(cfg["tts"]["espeak_speed"] * rate)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(text)
        try:
            run(["espeak-ng", "-v", v, "-s", str(speed), "-p", str(int(max(0, min(99, 50 * pitch)))), "-w", str(out_wav), "-f", tf.name])
        finally:
            os.unlink(tf.name)
        return {"backend": "espeak", "voice": v, "license": "espeak-ng GPL-3.0 (outil) ; audio généré utilisable"}
    if backend == "piper":
        model = ROOT / cfg["tts"]["piper_model"]
        exe = [which("piper")] if which("piper") else ["python3", "-m", "piper"]
        cmd = exe + ["--model", str(model), "--output_file", str(out_wav), "--length_scale", f"{1.0 / rate:.3f}"]
        if "piper_speaker" in voice_cfg:
            cmd += ["--speaker", str(voice_cfg["piper_speaker"])]
        run(cmd, input_text=text)
        return {"backend": "piper", "voice": model.name, "license": "voir la fiche du modèle (MODEL_CARD) avant usage commercial"}
    if backend == "command":
        tpl = cfg["tts"]["command"]
        if not tpl:
            raise RuntimeError("tts.backend=command mais tts.command est vide")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(text)
        try:
            run(shlex.split(tpl.format(text_file=tf.name, out_wav=str(out_wav), rate=rate, pitch=pitch)))
        finally:
            os.unlink(tf.name)
        return {"backend": "command", "voice": "externe", "license": "à vérifier selon le service externe (coût éventuel à journaliser)"}
    if backend == "recorded":
        src = Path(ep_dir) / "audio" / "recorded" / f"{line['id']}.wav"
        if not src.exists():
            raise RuntimeError(f"enregistrement manquant : {src}")
        out_wav.write_bytes(src.read_bytes())
        return {"backend": "recorded", "voice": "humaine", "license": "voix de l'auteur"}
    raise ValueError(backend)
