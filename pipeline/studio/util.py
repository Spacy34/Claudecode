"""Utilitaires : chemins, configuration, hachage, écriture atomique, sous-processus."""
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_json(obj):
    return sha256_bytes(canonical(obj).encode("utf-8"))


def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, obj):
    """Écriture atomique : un crash ne laisse jamais un JSON à moitié écrit."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)


def _env_override(cfg, prefix="STUDIO"):
    for sec, vals in cfg.items():
        if not isinstance(vals, dict):
            continue
        for k, v in vals.items():
            ev = os.environ.get(f"{prefix}_{sec}_{k}".upper())
            if ev is None:
                continue
            if isinstance(v, bool):
                vals[k] = ev.lower() in ("1", "true", "yes")
            elif isinstance(v, int):
                vals[k] = int(ev)
            elif isinstance(v, float):
                vals[k] = float(ev)
            else:
                vals[k] = ev
    return cfg


def _deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config():
    """config/studio.toml (versionné) puis config/local.toml (TES réglages, ignoré par git : jamais de conflit au pull)."""
    with open(ROOT / "config" / "studio.toml", "rb") as f:
        cfg = tomllib.load(f)
    local = ROOT / "config" / "local.toml"
    if local.exists():
        with open(local, "rb") as f:
            _deep_merge(cfg, tomllib.load(f))
    with open(ROOT / "config" / "profiles.toml", "rb") as f:
        cfg["profiles"] = tomllib.load(f)
    return _env_override(cfg)


def episodes_dir(cfg):
    return ROOT / cfg["paths"]["episodes_dir"]


def episode_dir(cfg, ep):
    return episodes_dir(cfg) / ep


def cache_dir(cfg):
    p = ROOT / cfg["paths"]["cache_dir"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def run(cmd, check=True, capture=True, timeout=None, input_text=None, env=None, cwd=None):
    r = subprocess.run(cmd, capture_output=capture, text=True, timeout=timeout, input=input_text, env=env, cwd=cwd,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"commande échouée ({r.returncode}) : {' '.join(map(str, cmd))}\n{(r.stderr or '')[-3000:]}")
    return r


IS_WINDOWS = os.name == "nt"

# Emplacements d'installation Windows usuels (winget / installeurs officiels), hors PATH par défaut.
_WIN_CANDIDATES = {
    "blender": [r"C:\Program Files\Blender Foundation\Blender*\blender.exe"],
    "espeak-ng": [r"C:\Program Files\eSpeak NG\espeak-ng.exe", r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"],
}


def which(name):
    p = shutil.which(name)
    if p or not IS_WINDOWS:
        return p
    import glob
    for pat in _WIN_CANDIDATES.get(name, []):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]   # version la plus récente
    return None


def ffprobe_json(path):
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(r.stdout)


def media_duration(path):
    return float(ffprobe_json(path)["format"]["duration"])
