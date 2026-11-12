"""Tableau de bord local : API, sécurité (jeton, hôte, chemins), envois de sons, réglages."""
import http.client
import json
import shutil
import threading
from pathlib import Path

import pytest

from studio import dashboard


@pytest.fixture
def server(episode, tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_LOCAL_TOML", str(tmp_path / "local.toml"))
    srv, port, token = dashboard.make_server(port=18765)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield port, token, episode
    srv.shutdown()
    srv.server_close()


def req(port, method, path, body=None, token=None, host=None, headers=None, raw=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = {"Host": host or f"127.0.0.1:{port}"}
    if token:
        h["X-Studio-Token"] = token
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None and raw is None:
        h["Content-Type"] = "application/json"
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    payload = r.read()
    return r.status, payload


def test_page_overview_and_detail(server):
    port, token, ep = server
    st, html = req(port, "GET", "/")
    assert st == 200 and token.encode() in html and b"Studio" in html
    st, ov = req(port, "GET", "/api/overview")
    ov = json.loads(ov)
    assert st == 200 and any(e["id"] == ep.name for e in ov["episodes"])
    st, det = req(port, "GET", f"/api/episode?ep={ep.name}")
    det = json.loads(det)
    assert st == 200 and len(det["stages"]) >= 20 and det["lines"] and det["lines"][0]["id"] == "l001"


def test_security_token_host_and_paths(server):
    port, token, ep = server
    assert req(port, "POST", "/api/settings", {"autonomous": True})[0] == 403, "sans jeton"
    assert req(port, "POST", "/api/settings", {"autonomous": True}, token="faux")[0] == 403
    assert req(port, "GET", "/api/overview", host="evil.example:80")[0] == 403, "en-tête Host étranger (DNS rebinding)"
    assert req(port, "GET", f"/file?ep={ep.name}&path=../../../../etc/passwd")[0] in (403, 404)
    assert req(port, "GET", "/api/episode?ep=../x")[0] == 400


def test_uploads_settings_and_new_episode(server, tmp_path):
    port, token, ep = server
    wav = Path(__file__).resolve().parents[1] / "assets" / "sfx"
    sample = next(wav.glob("*.wav"), None)
    data = sample.read_bytes() if sample else b"RIFF0000WAVE"
    st, _ = req(port, "POST", f"/api/upload?ep={ep.name}&kind=line&line=l003&filename=ma_voix.mp3", raw=data, token=token)
    assert st == 200 and (ep / "audio" / "recorded" / "l003.mp3").exists()
    st, _ = req(port, "POST", f"/api/upload?ep={ep.name}&kind=sfx&line=l002&word=4&filename=porte.wav", raw=data, token=token)
    assert st == 200 and json.loads((ep / "audio" / "user_sfx" / "sfx.json").read_text())[0]["word"] == 4
    assert req(port, "POST", f"/api/upload?ep={ep.name}&kind=line&line=l003&filename=x.exe", raw=data, token=token)[0] == 400
    det = json.loads(req(port, "GET", f"/api/episode?ep={ep.name}")[1])
    l3 = next(l for l in det["lines"] if l["id"] == "l003")
    assert l3["recording"] == "l003.mp3"
    assert req(port, "POST", "/api/delete", {"ep": ep.name, "kind": "line", "line": "l003"}, token=token)[0] == 200
    assert not (ep / "audio" / "recorded" / "l003.mp3").exists()
    assert req(port, "POST", "/api/settings", {"autonomous": True, "model": "gpt-5-codex"}, token=token)[0] == 200
    assert "autonomous = true" in (tmp_path / "local.toml").read_text()
    st, out = req(port, "POST", "/api/new", {"mode": "script", "name": "La Poule", "text": "Une poule devient maire.\nBernadette: Cot cot !", "launch": False}, token=token)
    assert st == 200, out
    assert json.loads(out)["ep"] == "ep_la_poule" and (ep.parent / "ep_la_poule" / "episode_brief.json").exists()
    assert req(port, "POST", "/api/new", {"mode": "script", "name": "La Poule", "text": "Une poule devient maire.\nBernadette: Cot cot !"}, token=token)[0] == 400, "doublon"


def test_recorded_line_replaces_synthesis(episode, cfg):
    """Voix fournie pour une réplique : utilisée telle quelle (durée de la réplique = durée du fichier)."""
    import subprocess
    if shutil.which("espeak-ng") is None:
        pytest.skip("espeak-ng absent")
    from studio import audio
    from studio.util import read_json
    rec = episode / "audio" / "recorded"
    rec.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=2.5", str(rec / "l003.mp3")], check=True)
    res = audio.build_voice(episode, cfg)
    assert res["recorded_lines"] == ["l003"]
    seg = next(s for s in read_json(episode / "audio_timeline.json")["segments"] if s["line_id"] == "l003")
    assert 2.3 < seg["end_s"] - seg["start_s"] < 2.6
