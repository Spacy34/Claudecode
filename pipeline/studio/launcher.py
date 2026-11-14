"""Lancement d'une production complète, identique sous Windows, macOS et Linux (sans bash ni tmux).

- `create_episode` : crée l'épisode depuis un texte (script imposé ou histoire libre) via `studio new`.
- `start_pilot` : lance scripts/pilote.py en arrière-plan, détaché (survit à la fermeture du tableau de bord),
  sortie ajoutée au journal episodes/<ep>/checks/codex_journal.log.
- `pilot_running` : verrou de fichier tenu par le pilote (fiable même entre espaces de PID différents).
- `stop_pilot` : arrête le pilote ET ses enfants (Blender, ffmpeg, Codex). Les étapes interrompues reprennent
  proprement au prochain lancement (cache des images déjà rendues).
"""
import os
import re
import signal
import subprocess
import sys
import unicodedata
from pathlib import Path

from .util import ROOT, episode_dir, load_config, which

EP_RE = re.compile(r"^ep_[a-z0-9_]{1,60}$")


def slug(name):
    """« La Poule.txt » -> ep_la_poule (même règle que scripts/produire.sh)."""
    base = Path(str(name)).stem if str(name).endswith(".txt") else str(name)
    base = re.sub(r"^ep_", "", base)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")[:40]
    return f"ep_{base or 'sans_nom'}"


def studio_cmd(*args):
    return [sys.executable, "-m", "studio", *args]


def studio_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "pipeline") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def attach_full_voice(ep, src_path=None, data=None, filename=None):
    """Range la voix complète (ElevenLabs…) de l'épisode dans audio/full_voice/ (remplace la précédente)."""
    from . import tts
    name = Path(filename or src_path).name
    ext = Path(name).suffix.lower()
    if ext not in tts.AUDIO_EXT:
        raise ValueError(f"format audio non pris en charge ({ext}) : {', '.join(tts.AUDIO_EXT)}")
    d = episode_dir(load_config(), ep) / "audio" / "full_voice"
    if d.exists():
        import shutil
        shutil.rmtree(d)
    d.mkdir(parents=True)
    dst = d / f"voix{ext}"
    if data is not None:
        dst.write_bytes(data)
    else:
        import shutil
        shutil.copyfile(src_path, dst)
    return dst


def create_episode(ep, text, mode="script", duration=None, inbox_name=None, voice_file=None):
    """mode : 'script' (texte imposé, verrouillé) ou 'libre' (histoire brute, Codex écrit le script).
    -> (ok, sortie texte)."""
    if not EP_RE.match(ep):
        raise ValueError(f"nom d'épisode invalide : {ep} (attendu ep_ + minuscules/chiffres/_)")
    cfg = load_config()
    if episode_dir(cfg, ep).exists():
        raise FileExistsError(f"l'épisode {ep} existe déjà")
    inbox = episode_dir(cfg, "_inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    src = inbox / (inbox_name or f"{ep}.txt")
    src.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
    if voice_file and not duration:
        from .util import media_duration
        try:
            duration = int(media_duration(voice_file)) + 1   # la voix fournie fixe la durée
        except Exception:
            duration = None
    args = ["new", ep, "--script-file" if mode == "script" else "--story-file", str(src), "--stop-after", "final"]
    if duration:
        args += ["--duration", str(int(duration))]
    elif mode != "script":
        args += ["--duration", "60"]
    r = subprocess.run(studio_cmd(*args), cwd=ROOT, env=studio_env(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0 and voice_file:
        attach_full_voice(ep, src_path=voice_file)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def _lock_path(ep):
    return episode_dir(load_config(), ep) / "checks" / "pilote.lock"


def pilot_running(ep):
    from .state import _lock, _unlock
    lp = _lock_path(ep)
    if not lp.exists():
        return False
    try:
        with open(lp, "a+b") as h:
            try:
                _lock(h)
            except OSError:
                return True
            _unlock(h)
            return False
    except OSError:
        return False


def journal(ep):
    return episode_dir(load_config(), ep) / "checks" / "codex_journal.log"


def start_pilot(ep, model=""):
    """Lance le pilote détaché. -> pid. Refuse si une production de cet épisode tourne déjà."""
    if pilot_running(ep):
        raise RuntimeError(f"une production de {ep} tourne déjà")
    p = episode_dir(load_config(), ep)
    if not p.exists():
        raise FileNotFoundError(f"épisode introuvable : {ep}")
    (p / "checks").mkdir(parents=True, exist_ok=True)
    model = model or os.environ.get("CODEX_MODEL", "") or load_config().get("codex", {}).get("model", "")
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "pilote.py"), ep]
    if model:
        cmd += ["--modele", model]
    log = open(journal(ep), "a", encoding="utf-8")
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000   # CREATE_NO_WINDOW : pas de fenêtres Blender/ffmpeg
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, cwd=ROOT, env=studio_env(), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kw)
    log.close()
    (p / "checks" / "pilote.pid").write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def stop_pilot(ep):
    """Arrête le pilote et tous ses processus enfants. -> True si un processus a été arrêté."""
    pidf = episode_dir(load_config(), ep) / "checks" / "pilote.pid"
    if not pidf.exists():
        return False
    try:
        pid = int(pidf.read_text().strip())
    except ValueError:
        return False
    if not pilot_running(ep):
        return False
    if os.name == "nt":
        r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
        ok = r.returncode == 0
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
            ok = True
        except ProcessLookupError:
            ok = False
    with open(journal(ep), "a", encoding="utf-8") as f:
        f.write("\n[pilote] ARRÊT demandé par l'utilisateur (tableau de bord ou `studio arreter`).\n")
    return ok


def codex_path():
    return which("codex")
