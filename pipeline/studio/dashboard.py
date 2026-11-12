"""Tableau de bord local : `studio dashboard` -> http://127.0.0.1:8765

Suivre les épisodes (étapes, vérifications, revues, vidéos, journal), créer une vidéo à partir d'un script ou
d'une histoire, fournir ses propres fichiers son (voix d'une réplique, musique, bruitage), lancer / arrêter la
production. Bibliothèque standard uniquement (aucune dépendance), écoute sur 127.0.0.1 seulement.

Sécurité : toute action (POST) exige le jeton aléatoire de la session, inclus dans la page servie, et l'en-tête
Host doit être local (protège des sites web qui tenteraient d'appeler le serveur). Les fichiers servis sont
limités au dossier de l'épisode. Aucune validation de gate n'est possible ici : `studio approve` reste une
action humaine dans un terminal.
"""
import json
import mimetypes
import re
import secrets
import shutil
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import hardware, launcher, tts
from .state import DONE, STAGES, State
from .util import episode_dir, episodes_dir, load_config, read_json, set_local_value

UI = Path(__file__).with_name("dashboard_ui.html")
LINE_RE = re.compile(r"^l[0-9]{3}$")
MAX_UPLOAD = 300 * 1024 * 1024
MEDIA = [("image", "lookdev/contact_sheet.png", "Lookdev : personnages et décors"),
         ("image", "checks/shots_contact.png", "Contrôle : une image par plan"),
         ("image", "checks/motion_contact.png", "Motion design (planche)"),
         ("video", "renders/prototype.mp4", "Prototype (début)"),
         ("video", "renders/first_cut.mp4", "Premier montage"),
         ("video", "renders/final.mp4", "VIDÉO FINALE")]
STAGE_LABELS = {
    "brief": "Brief", "script": "Script", "script_review": "Critique du script", "gate_script": "Validation script",
    "design": "Personnages & décors", "storyboard": "Storyboard", "animation": "Animation", "motion": "Motion design",
    "voice": "Voix", "storyboard_review": "Critique storyboard", "compile": "Minutage des plans", "lookdev": "Lookdev",
    "gate_lookdev": "Validation lookdev", "prototype": "Prototype", "gate_prototype": "Validation prototype",
    "shots_check": "Contrôle des plans", "first_cut": "Premier montage", "reviews": "Critiques vidéo",
    "gate_first_cut": "Validation montage", "final": "Rendu final", "delivery": "Livraison"}

_DOCTOR = {"status": "en cours"}


def _doctor_bg():
    try:
        d = hardware.diagnose(load_config())
        d["codex"] = bool(launcher.codex_path())
        _DOCTOR.clear()
        _DOCTOR.update(d)
        _DOCTOR["status"] = "ok"
    except Exception as e:   # diagnostic indicatif seulement
        _DOCTOR.update({"status": "erreur", "error": str(e)})


def _episodes(cfg):
    d = episodes_dir(cfg)
    return sorted([p for p in d.glob("ep_*") if p.is_dir()], key=lambda p: -(p / "state.json").stat().st_mtime if (p / "state.json").exists() else 0)


def _title(p):
    for f, k in (("story_script.json", "title"), ("episode_brief.json", "title")):
        try:
            t = read_json(p / f).get(k)
            if t and not str(t).startswith("À DÉFINIR"):
                return t
        except (OSError, ValueError):
            pass
    return p.name


def _phase(st, running):
    rows = {n: st.st(n) for n in STAGES}
    if rows["delivery"]["status"] == "completed":
        return "terminé", "La vidéo finale est prête."
    blocked = [n for n, s in rows.items() if s["status"] == "needs_review"]
    if blocked:
        return "bloqué", f"Intervention requise : {STAGE_LABELS.get(blocked[0], blocked[0])} ({(rows[blocked[0]].get('note') or '')[:160]})"
    cur = next((n for n, s in rows.items() if s["status"] == "running"), None)
    if running:
        if cur:
            return "en cours", f"En cours : {STAGE_LABELS.get(cur, cur)}"
        ready = st.ready()
        return "en cours", "En cours : " + (STAGE_LABELS.get(ready[0], ready[0]) if ready else "pilote actif")
    failed = [n for n, s in rows.items() if s["status"] == "failed"]
    if failed:
        return "à reprendre", f"Arrêté après un échec : {STAGE_LABELS.get(failed[0], failed[0])}. Relancer pour corriger."
    return "en pause", "Production arrêtée : bouton « Lancer / reprendre »."


def episode_overview(p):
    st = State(p)
    st.refresh()
    done = sum(1 for n in STAGES if st.st(n)["status"] in DONE)
    running = launcher.pilot_running(p.name)
    phase, msg = _phase(st, running)
    return {"id": p.name, "title": _title(p), "progress": round(done / len(STAGES), 3), "done": done, "total": len(STAGES),
            "running": running, "phase": phase, "message": msg, "final": (p / "renders" / "final.mp4").exists()}


def _script_lines(p):
    for f in ("story_script.json",):
        if (p / f).exists():
            try:
                return [{"id": l["id"], "speaker": l["speaker"], "text": l["text"]} for l in read_json(p / f)["lines"]]
            except (KeyError, ValueError):
                pass
    try:
        lock = read_json(p / "episode_brief.json").get("script_lock")
        if lock:
            return [{"id": f"l{i + 1:03d}", "speaker": l["speaker"], "text": l["text"]} for i, l in enumerate(lock["lines"])]
    except (OSError, ValueError, KeyError):
        pass
    return []


def _user_sfx(p):
    f = p / "audio" / "user_sfx" / "sfx.json"
    try:
        return read_json(f) if f.exists() else []
    except ValueError:
        return []


def episode_detail(p):
    from .cli import next_summary
    ov = episode_overview(p)
    st = State(p)
    stages = [{"name": n, "label": STAGE_LABELS.get(n, n), "status": status, "owner": owner, "kind": kind, "attempts": att,
               "note": (note or "")[:400], "rounds": st.st(n).get("revision_rounds", 0)} for n, status, owner, kind, att, note in st.summary()]
    for s_ in stages:
        if s_["status"] == "failed":
            s_["note"] = (st.st(s_["name"]).get("error") or s_["note"] or "")[:600]
    qa = []
    for f in ("qa_prototype.json", "qa_first_cut.json", "qa_report.json"):
        if (p / f).exists():
            try:
                q = read_json(p / f)
            except ValueError:
                continue
            bad = [c for c in q.get("checks", []) if c.get("status") in ("fail", "warn")]
            qa.append({"file": f, "summary": q.get("summary", {}), "issues": [{"id": c["id"], "severity": c.get("severity"), "status": c["status"],
                                                                              "message": c.get("message", "")[:300]} for c in bad[:40]]})
    sc = p / "checks" / "scene_checks.json"
    if sc.exists():
        try:
            checks = read_json(sc).get("checks", [])
            bad = [c for c in checks if c.get("status") == "fail" or c.get("severity") in ("major", "blocker")]
            qa.append({"file": "checks/scene_checks.json", "summary": {"blocking": any(c.get("status") == "fail" for c in bad), "checks": len(checks)},
                       "issues": [{"id": f"{c.get('shot', '')}:{c['id']}", "severity": c.get("severity"), "status": c.get("status"),
                                   "message": c.get("message", "")[:300]} for c in bad[:40]]})
        except ValueError:
            pass
    reviews = []
    for r in sorted((p / "reviews").glob("*.json")) if (p / "reviews").exists() else []:
        try:
            j = read_json(r)
            sc_ = [v.get("score") for v in j.get("scores", {}).values() if isinstance(v, dict)]
            reviews.append({"file": r.name, "reviewer": j.get("reviewer"), "gate": j.get("gate"), "verdict": j.get("verdict"),
                            "score": round(sum(sc_) / len(sc_), 1) if sc_ else None,
                            "findings": [{"severity": f.get("severity"), "issue": (f.get("issue") or f.get("message") or "")[:200]} for f in j.get("findings", [])[:6]]})
        except (ValueError, AttributeError):
            continue
    media = [{"kind": k, "path": rel, "label": lab, "mtime": int((p / rel).stat().st_mtime)} for k, rel, lab in MEDIA if (p / rel).exists()]
    lines = _script_lines(p)
    usfx = _user_sfx(p)
    for l in lines:
        rec = tts.recording_for(p, l["id"])
        l["recording"] = rec.name if rec else None
        l["sfx"] = [u for u in usfx if u["line"] == l["id"]]
    mdir = p / "audio" / "music"
    music = sorted(q.name for q in mdir.glob("*") if q.suffix.lower() in tts.AUDIO_EXT) if mdir.is_dir() else []
    rep = p / "checks" / "codex_rapport_final.md"
    brief = {}
    try:
        b = read_json(p / "episode_brief.json")
        brief = {"duration": b.get("target_duration_s"), "imposed": bool(b.get("script_lock")), "stop_after": b.get("stop_after")}
    except (OSError, ValueError):
        pass
    try:
        nxt = next_summary(p)
    except Exception as e:   # épisode incomplet : le tableau de bord reste utilisable
        nxt = {"error": str(e)}
    return {**ov, "stages": stages, "qa": qa, "reviews": reviews, "media": media, "lines": lines, "music": music, "brief": brief,
            "next": nxt, "report": rep.read_text(encoding="utf-8", errors="replace")[-6000:] if rep.exists() else ""}


def tail(path, n=200):
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 200_000))
        data = f.read().decode("utf-8", errors="replace")
    return "\n".join(data.splitlines()[-n:])


class Handler(BaseHTTPRequestHandler):
    server_version = "StudioDashboard/1"
    token = ""
    port = 0

    def log_message(self, fmt, *args):   # silencieux (pas de bruit dans le terminal)
        pass

    # ------------------------------------------------------------ utilitaires
    def _host_ok(self):
        h = (self.headers.get("Host") or "").lower()
        return h in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _err(self, code, msg):
        self._send(code, {"error": msg})

    def _ep(self, name):
        if not name or not launcher.EP_RE.match(name):
            raise ValueError("épisode invalide")
        p = episode_dir(load_config(), name)
        if not p.is_dir():
            raise FileNotFoundError(f"épisode introuvable : {name}")
        return p

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("requête trop grande")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}

    # ------------------------------------------------------------ GET
    def do_GET(self):
        if not self._host_ok():
            return self._err(403, "hôte refusé")
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                html = UI.read_text(encoding="utf-8").replace("__TOKEN__", self.token)
                return self._send(200, html, "text/html; charset=utf-8",
                                  {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; media-src 'self'; img-src 'self' data:"})
            if u.path == "/api/overview":
                cfg = load_config()
                inbox = episode_dir(cfg, "_inbox")
                return self._send(200, {"autonomous": bool(cfg["quality"].get("autonomous")), "model": cfg.get("codex", {}).get("model", ""),
                                        "final_profile": cfg["render"].get("final_profile"), "codex": bool(launcher.codex_path()),
                                        "doctor": _DOCTOR, "episodes": [episode_overview(p) for p in _episodes(cfg)],
                                        "inbox": sorted(x.name for x in inbox.glob("*.txt")) if inbox.is_dir() else []})
            if u.path == "/api/episode":
                return self._send(200, episode_detail(self._ep(q.get("ep"))))
            if u.path == "/api/log":
                p = self._ep(q.get("ep"))
                return self._send(200, {"log": tail(p / "checks" / "codex_journal.log", int(q.get("n", 300)))})
            if u.path == "/api/inbox":
                f = episode_dir(load_config(), "_inbox") / Path(q.get("name", "")).name
                if f.suffix != ".txt" or not f.exists():
                    return self._err(404, "introuvable")
                return self._send(200, {"text": f.read_text(encoding="utf-8", errors="replace")})
            if u.path == "/file":
                return self._file(self._ep(q.get("ep")), q.get("path", ""))
            return self._err(404, "introuvable")
        except (ValueError, FileNotFoundError) as e:
            return self._err(400, str(e))

    do_HEAD = do_GET

    def _file(self, p, rel):
        f = (p / rel).resolve()
        try:
            f.relative_to(p.resolve())
        except ValueError:
            return self._err(403, "chemin refusé")
        if not f.is_file() or f.suffix.lower() not in (".png", ".jpg", ".mp4", ".wav", ".mp3", ".m4a", ".ogg", ".json", ".md", ".txt", ".ass"):
            return self._err(404, "introuvable")
        size = f.stat().st_size
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else max(0, size - int(b))
                end = min(size - 1, int(b)) if (a and b) else size - 1
                code = 206
            except ValueError:
                pass
        length = max(0, end - start + 1)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(f, "rb") as fh:
            fh.seek(start)
            left = length
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    # ------------------------------------------------------------ POST (actions)
    def do_POST(self):
        if not self._host_ok():
            return self._err(403, "hôte refusé")
        if not secrets.compare_digest(self.headers.get("X-Studio-Token", ""), self.token):
            return self._err(403, "jeton invalide (recharger la page)")
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/upload":
                return self._upload(self._ep(q.get("ep")), q)
            body = self._json_body()
            if u.path == "/api/new":
                return self._new(body)
            if u.path == "/api/launch":
                self._ep(body.get("ep"))
                pid = launcher.start_pilot(body["ep"], load_config().get("codex", {}).get("model", ""))
                return self._send(200, {"ok": True, "pid": pid})
            if u.path == "/api/stop":
                self._ep(body.get("ep"))
                return self._send(200, {"ok": launcher.stop_pilot(body["ep"])})
            if u.path == "/api/retry":
                p = self._ep(body.get("ep"))
                stage = body.get("stage")
                if stage not in STAGES or STAGES[stage][1] == "gate" and STAGES[stage][5] and not load_config()["quality"].get("autonomous"):
                    return self._err(400, "étape invalide (une validation humaine se fait avec `studio approve` dans un terminal)")
                st = State(p)
                s_ = st.st(stage)
                s_["status"] = "pending"
                s_["revision_rounds"] = 0
                st.log("retry", stage=stage, by="human:dashboard")
                st.save()
                return self._send(200, {"ok": True})
            if u.path == "/api/delete":
                return self._delete(self._ep(body.get("ep")), body)
            if u.path == "/api/settings":
                if "autonomous" in body:
                    set_local_value("quality", "autonomous", bool(body["autonomous"]))
                if "model" in body:
                    m = str(body["model"]).strip()
                    if m and not re.match(r"^[A-Za-z0-9._:-]{1,60}$", m):
                        return self._err(400, "nom de modèle invalide")
                    set_local_value("codex", "model", m)
                if body.get("final_profile") in ("draft", "preview", "final"):
                    set_local_value("render", "final_profile", body["final_profile"])
                return self._send(200, {"ok": True})
            return self._err(404, "introuvable")
        except (ValueError, KeyError, FileNotFoundError, FileExistsError, RuntimeError) as e:
            return self._err(400, str(e))

    def _new(self, b):
        text = (b.get("text") or "").strip()
        if len(text) < 10:
            raise ValueError("texte trop court")
        mode = "libre" if b.get("mode") == "libre" else "script"
        ep = launcher.slug(b.get("name") or " ".join(text.split()[:4]))
        ok, out = launcher.create_episode(ep, text + "\n", mode=mode, duration=int(b["duration"]) if b.get("duration") else None)
        if not ok:
            return self._send(400, {"error": out.strip()[-1500:]})
        pid = None
        if b.get("launch"):
            pid = launcher.start_pilot(ep, load_config().get("codex", {}).get("model", ""))
        return self._send(200, {"ok": True, "ep": ep, "output": out.strip()[-1500:], "pid": pid})

    def _upload(self, p, q):
        kind = q.get("kind")
        name = Path(q.get("filename", "son.wav")).name
        ext = Path(name).suffix.lower()
        if ext not in tts.AUDIO_EXT:
            raise ValueError(f"format non pris en charge ({ext}) : {', '.join(tts.AUDIO_EXT)}")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_UPLOAD:
            raise ValueError("fichier vide ou trop volumineux (300 Mo max)")
        data = self.rfile.read(n)
        if kind == "line":
            line = q.get("line", "")
            if not LINE_RE.match(line):
                raise ValueError("réplique invalide")
            d = p / "audio" / "recorded"
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob(f"{line}.*"):
                old.unlink()
            (d / f"{line}{ext}").write_bytes(data)
        elif kind == "music":
            d = p / "audio" / "music"
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            (d / f"musique{ext}").write_bytes(data)
        elif kind == "sfx":
            line, word = q.get("line", ""), int(q.get("word", 0) or 0)
            if not LINE_RE.match(line):
                raise ValueError("réplique invalide")
            d = p / "audio" / "user_sfx"
            d.mkdir(parents=True, exist_ok=True)
            fn = f"{line}_w{word}{ext}"
            (d / fn).write_bytes(data)
            lst = [u for u in _user_sfx(p) if not (u["line"] == line and u.get("word", 0) == word)]
            lst.append({"line": line, "word": word, "file": fn, "original": name})
            (d / "sfx.json").write_text(json.dumps(lst, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise ValueError("type d'envoi inconnu")
        return self._send(200, {"ok": True, "note": "La voix sera recalculée au prochain lancement (les plans concernés seront recalés)."})

    def _delete(self, p, b):
        kind = b.get("kind")
        if kind == "line" and LINE_RE.match(b.get("line", "")):
            for f in (p / "audio" / "recorded").glob(f"{b['line']}.*"):
                f.unlink()
        elif kind == "music":
            shutil.rmtree(p / "audio" / "music", ignore_errors=True)
        elif kind == "sfx" and LINE_RE.match(b.get("line", "")):
            d = p / "audio" / "user_sfx"
            keep = []
            for u in _user_sfx(p):
                if u["line"] == b["line"] and u.get("word", 0) == int(b.get("word", 0)):
                    (d / u["file"]).unlink(missing_ok=True)
                else:
                    keep.append(u)
            (d / "sfx.json").write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise ValueError("suppression invalide")
        return self._send(200, {"ok": True})


def make_server(port=8765, tries=10):
    token = secrets.token_urlsafe(24)
    last = None
    for k in range(tries):
        handler = type("H", (Handler,), {"token": token, "port": port + k})
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port + k), handler)
            srv.daemon_threads = True
            return srv, port + k, token
        except OSError as e:
            last = e
    raise OSError(f"aucun port libre à partir de {port} : {last}")


def serve(port=8765, open_browser=True):
    srv, real_port, _ = make_server(port)
    threading.Thread(target=_doctor_bg, daemon=True).start()
    url = f"http://127.0.0.1:{real_port}/"
    print(f"Tableau de bord : {url}   (Ctrl+C pour fermer ; les productions lancées continuent en arrière-plan)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nTableau de bord fermé.")
    finally:
        srv.server_close()
