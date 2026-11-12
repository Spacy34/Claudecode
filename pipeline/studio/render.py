"""Rendu des plans via Blender (binaire ou module bpy), avec cache par contenu et reprise.

Clé de cache d'un plan = sha256(spec du plan + profil + code du moteur + moteur de rendu). Conséquences :
- corriger 3 plans ne re-rend que ces 3 plans (test H) ;
- un rendu interrompu reprend à la dernière frame écrite (les PNG existants sont conservés) ;
- toute modification du moteur invalide proprement les rendus concernés.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import ROOT, cache_dir, read_json, sha256_bytes, sha256_json, which, write_json

ENGINE_DIR = ROOT / "blender" / "engine"


def engine_hash():
    h = b""
    for p in sorted(ENGINE_DIR.glob("*.py")):
        h += p.name.encode() + p.read_bytes()
    return sha256_bytes(h)


def blender_invocation(cfg):
    mode = cfg["blender"]["mode"]
    binary = os.environ.get("BLENDER_BIN") or cfg["blender"].get("binary") or which("blender")
    if mode in ("auto", "binary") and binary:
        return "binary", [binary, "-b", "--factory-startup", "-noaudio", "--python", str(ENGINE_DIR / "run_shot.py"), "--"]
    if mode == "binary":
        raise RuntimeError("blender.mode=binary mais aucun binaire Blender trouvé (BLENDER_BIN ou PATH)")
    if importlib.util.find_spec("bpy") is None:
        raise RuntimeError("Ni binaire Blender ni module bpy : lancer scripts/install.sh")
    return "module", [sys.executable, str(ENGINE_DIR / "run_shot.py")]


def blender_script_cmd(cfg, script_name):
    """Commande pour exécuter un autre script du moteur (ex. inspect_model.py) avec le même Blender."""
    mode, cmd = blender_invocation(cfg)
    script = str(ENGINE_DIR / script_name)
    if mode == "binary":
        return cmd[:cmd.index("--python") + 1] + [script, "--"]
    return [cmd[0], script]


def has_gpu():
    if which("nvidia-smi"):
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
        return r.returncode == 0 and "GPU" in r.stdout
    return False


def pick_engine(cfg, mode):
    e = cfg["render"]["engine"]
    if e != "auto":
        return e
    return "eevee" if (mode == "binary" and has_gpu()) else "cycles"


def profile_dict(cfg, name):
    p = dict(cfg["profiles"][name])
    p["name"] = name
    p["fps"] = int(cfg["render"]["fps"])
    return p


def shot_cache_key(spec_sha, profile, eng_hash, render_engine, mode="render", frames=""):
    return sha256_json({"spec": spec_sha, "profile": profile, "engine": eng_hash, "render_engine": render_engine, "mode": mode, "frames": frames})


def _run_until_done(command, output, done_path, timeout_s, exit_grace_s=5):
    """Laisse Blender se terminer, mais le ferme s'il reste vivant après son marqueur de succès (done.json).
    Constaté sur VPS avec le binaire Blender : processus encore actif plusieurs minutes après STUDIO_SHOT_OK
    (diagnostic et correctif proposés par Codex). Timeout normal conservé sans marqueur."""
    proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    started = time.monotonic()
    done_at = None
    try:
        while True:
            code = proc.poll()
            if code is not None:
                return code
            t = time.monotonic()
            if done_path.exists():
                done_at = done_at or t
                if t - done_at >= exit_grace_s:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    return 0
            elif t - started >= timeout_s:
                proc.kill()
                proc.wait()
                return -999
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def render_shot(cfg, ep_dir, shot, profile_name, mode="render", frames="", log=print):
    ep_dir = Path(ep_dir)
    prof = profile_dict(cfg, profile_name)
    inv_mode, cmd = blender_invocation(cfg)
    reng = pick_engine(cfg, inv_mode)
    key = shot_cache_key(shot["spec_sha256"], prof, engine_hash(), reng, mode, frames)
    out = cache_dir(cfg) / "shots" / key
    rec = {"id": shot["id"], "cache_key": key, "frames_dir": str(out), "render_engine": reng}
    if (out / "done.json").exists():
        rec["status"] = "cached"
        rec["scene_report"] = _report(out)
        _touch(out)
        return rec
    out.mkdir(parents=True, exist_ok=True)
    prof_path = out / "profile.json"
    write_json(prof_path, prof)
    full = cmd + ["--spec", str(ep_dir / shot["spec_path"]), "--out", str(out), "--profile", str(prof_path), "--mode", mode, "--engine", reng]
    if frames:
        full += ["--frames", frames]
    threads = int(cfg["limits"].get("max_threads") or 0)
    if threads:
        full += ["--threads", str(threads)]
    t0 = time.time()
    log(f"  rendu {shot['id']} ({shot['frames']} frames, {profile_name}, {reng}, {inv_mode})…")
    with open(out / "blender.log", "w") as lf:
        code = _run_until_done(full, lf, out / "done.json", int(cfg["limits"]["shot_timeout_s"]))
    rec["render_seconds"] = round(time.time() - t0, 1)
    if code != 0 or not (out / "done.json").exists():
        rec["status"] = "failed"
        rep = _report(out)
        rec["error"] = (rep or {}).get("error") or f"code {code} (voir {out / 'blender.log'})"
        rec["scene_report"] = rep
        return rec
    rec["status"] = "rendered"
    rec["scene_report"] = _report(out)
    return rec


def _report(out):
    p = Path(out) / "scene_report.json"
    return read_json(p) if p.exists() else None


def _touch(p):
    try:
        os.utime(p, None)
    except OSError:
        pass


def render_shots(cfg, ep_dir, shots, profile_name, mode="render", frames="", log=print):
    par = max(1, int(cfg["limits"]["max_parallel_renders"]))
    if par == 1:
        return [render_shot(cfg, ep_dir, s, profile_name, mode, frames, log) for s in shots]
    with ThreadPoolExecutor(max_workers=par) as ex:
        return list(ex.map(lambda s: render_shot(cfg, ep_dir, s, profile_name, mode, frames, log), shots))


def cache_stats(cfg):
    root = cache_dir(cfg)
    total, entries = 0, []
    for d in root.glob("*/*"):
        if d.is_dir() or d.is_file():
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else d.stat().st_size
            total += size
            entries.append((d.stat().st_mtime, size, d))
    return total, entries


def prune_cache(cfg):
    limit = float(cfg["limits"]["max_cache_gb"]) * (1 << 30)
    total, entries = cache_stats(cfg)
    removed = 0
    for mtime, size, d in sorted(entries):
        if total <= limit:
            break
        shutil.rmtree(d) if d.is_dir() else d.unlink()
        total -= size
        removed += 1
    return removed, total
