"""Diagnostic matériel et logiciel (`studio doctor`). N'importe pas bpy (lecture de version via métadonnées)."""
import importlib.metadata
import importlib.util
import os
import shutil
import subprocess

from .util import ROOT, which


def _ver(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).splitlines()[0].strip() if r.returncode == 0 else None
    except Exception:
        return None


def _mem_gb():
    try:
        for l in open("/proc/meminfo"):
            if l.startswith("MemTotal"):
                return round(int(l.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return None


def diagnose(cfg):
    res = {"cpu_count": os.cpu_count(), "ram_gb": _mem_gb(), "disk_free_gb": round(shutil.disk_usage(ROOT).free / (1 << 30), 1)}
    gpu = None
    if which("nvidia-smi"):
        g = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
        gpu = g.stdout.strip() if g.returncode == 0 else None
    res["gpu"] = gpu
    res["ffmpeg"] = _ver(["ffmpeg", "-version"])
    if res["ffmpeg"]:
        f = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        e = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        res["ffmpeg_features"] = {k: (f" {k} " in f) for k in ("ass", "loudnorm", "blackdetect", "freezedetect", "sidechaincompress", "ebur128")}
        res["ffmpeg_features"]["libx264"] = "libx264" in e
        res["ffmpeg_features"]["aac"] = " aac " in e
    blender_bin = os.environ.get("BLENDER_BIN") or cfg["blender"].get("binary") or which("blender")
    res["blender_binary"] = _ver([blender_bin, "--version"]) if blender_bin else None
    try:
        res["bpy_module"] = importlib.metadata.version("bpy") if importlib.util.find_spec("bpy") else None
    except importlib.metadata.PackageNotFoundError:
        res["bpy_module"] = None
    res["espeak_ng"] = _ver(["espeak-ng", "--version"])
    res["piper"] = bool(which("piper") or importlib.util.find_spec("piper"))
    pm = cfg["tts"].get("piper_model")
    res["piper_model"] = pm if pm and (ROOT / pm).exists() else None
    res["jsonschema"] = importlib.util.find_spec("jsonschema") is not None
    res["pillow"] = importlib.util.find_spec("PIL") is not None
    fm = subprocess.run(["fc-match", cfg["subtitles"]["font_family"]], capture_output=True, text=True) if which("fc-match") else None
    res["subtitle_font_match"] = fm.stdout.strip() if fm and fm.returncode == 0 else None
    # recommandations
    rec = []
    if not (res["blender_binary"] or res["bpy_module"]):
        rec.append("BLOQUANT : installer Blender (binaire) ou `pip install bpy` (scripts/install.sh).")
    if not res["ffmpeg"] or not res.get("ffmpeg_features", {}).get("libx264"):
        rec.append("BLOQUANT : ffmpeg avec libx264 requis.")
    if not res.get("ffmpeg_features", {}).get("ass"):
        rec.append("BLOQUANT : ffmpeg sans libass : sous-titres impossibles.")
    if not (res["espeak_ng"] or res["piper_model"]):
        rec.append("BLOQUANT (voix) : installer piper + un modèle français, ou espeak-ng pour les tests.")
    elif not res["piper_model"]:
        rec.append("Voix : seul espeak-ng est disponible (robotique). Installer piper + une voix FR pour la production (voir references/voice-options.md).")
    par = 1
    if res["ram_gb"]:
        par = max(1, min((res["cpu_count"] or 2) // 4, int(res["ram_gb"] // 4)))
    res["recommended"] = {"max_parallel_renders": par, "default_profile": "preview" if gpu else "draft",
                          "render_engine": "eevee (binaire Blender + GPU)" if gpu and res["blender_binary"] else "cycles CPU"}
    if res["subtitle_font_match"] and cfg["subtitles"]["font_family"].split()[0].lower() not in res["subtitle_font_match"].lower():
        rec.append(f"Police de sous-titres '{cfg['subtitles']['font_family']}' introuvable (fc-match → {res['subtitle_font_match']}). Placer un .ttf/.otf libre dans assets/fonts/.")
    res["advice"] = rec
    res["blocking"] = any(a.startswith("BLOQUANT") for a in rec)
    return res
