"""Validation des contrats : schémas JSON (structure) + règles croisées (cohérence entre artefacts).

La validation structurelle seule ne suffit pas : un storyboard peut être valide et référencer une
réplique supprimée. Les règles croisées empêchent ces désynchronisations silencieuses.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .util import ROOT, read_json, sha256_file

SCHEMAS = ROOT / "schemas"
sys.path.insert(0, str(ROOT / "blender"))
from engine import registry as engine_registry  # noqa: E402  (n'importe pas bpy)

ARTIFACTS = {
    "episode_brief": "episode_brief.json",
    "story_script": "story_script.json",
    "cast_bible": "cast_bible.json",
    "asset_manifest": "asset_manifest.json",
    "storyboard": "storyboard.json",
    "animation_plan": "animation_plan.json",
    "audio_timeline": "audio_timeline.json",
    "shot_manifest": "shot_manifest.json",
    "render_manifest": "render_manifest.json",
    "qa_report": "qa_report.json",
    "episode_manifest": "episode_manifest.json",
}
CONTRACT_VERSION = "1.0"


def _registry():
    reg = Registry()
    for p in SCHEMAS.glob("*.schema.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        res = Resource.from_contents(s)
        reg = reg.with_resource(s["$id"], res).with_resource(p.name, res)
    return reg


_REG = None


def validator(contract):
    global _REG
    if _REG is None:
        _REG = _registry()
    schema = json.loads((SCHEMAS / f"{contract}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=_REG)


def schema_errors(contract, data):
    v = validator(contract)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<racine>'}: {e.message}" for e in sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))]


def load_episode(ep_dir):
    ep_dir = Path(ep_dir)
    out = {}
    for name, fn in ARTIFACTS.items():
        p = ep_dir / fn
        if p.exists():
            out[name] = read_json(p)
    return out


def cross_errors(arts):
    """Règles de cohérence inter-artefacts. Retourne une liste d'erreurs lisibles."""
    errs = []
    ep_ids = {a.get("episode_id") for a in arts.values() if isinstance(a, dict) and "episode_id" in a}
    if len(ep_ids) > 1:
        errs.append(f"episode_id incohérents entre artefacts : {sorted(ep_ids)}")
    script = arts.get("story_script")
    cast = arts.get("cast_bible")
    assets = arts.get("asset_manifest")
    sb = arts.get("storyboard")
    ap = arts.get("animation_plan")
    line_ids, beat_ids, words = set(), set(), {}
    if script:
        line_ids = [l["id"] for l in script["lines"]]
        if len(set(line_ids)) != len(line_ids):
            errs.append("story_script : identifiants de répliques dupliqués")
        if line_ids != sorted(line_ids):
            errs.append("story_script : les répliques doivent être listées dans l'ordre de leurs identifiants")
        beat_ids = {b["id"] for b in script["beats"]}
        for l in script["lines"]:
            if l["beat_id"] not in beat_ids:
                errs.append(f"story_script : {l['id']} référence un beat inconnu {l['beat_id']}")
            words[l["id"]] = len(l["text"].split())
            for wi in l.get("emphasis_words", []):
                if wi >= words[l["id"]]:
                    errs.append(f"story_script : emphasis_words {wi} hors de {l['id']}")
            for s in l.get("sfx", []):
                if "word" in s and s["word"] >= words[l["id"]]:
                    errs.append(f"story_script : sfx {s['name']} sur mot {s['word']} hors de {l['id']}")
        if script["hook"]["line_id"] != script["lines"][0]["id"]:
            errs.append("story_script : le hook doit être la première réplique")
        line_ids = set(line_ids)
    char_ids = {c["id"] for c in cast["characters"]} if cast else set()
    set_ids = {s["id"] for s in assets["sets"]} if assets else set()
    prop_ids = {p["id"] for p in assets["props"]} if assets else set()
    if assets:
        for pr in assets["props"]:
            if pr["type"] == "composite" and not pr.get("parts"):
                errs.append(f"asset_manifest : {pr['id']} est 'composite' mais n'a pas de 'parts'")
            if pr["type"] == "custom" or pr.get("source") == "external":
                if not pr.get("external_path"):
                    errs.append(f"asset_manifest : {pr['id']} externe sans 'external_path'")
                elif not (ROOT / "assets" / pr["external_path"]).exists():
                    errs.append(f"asset_manifest : modèle introuvable assets/{pr['external_path']} ({pr['id']})")
                if not pr["license"].get("commercial_use"):
                    errs.append(f"asset_manifest : {pr['id']} : licence sans usage commercial, refusé")
        for st_ in assets["sets"]:
            if st_["kit"].startswith("generic_") and not st_.get("surfaces"):
                errs.append(f"asset_manifest : {st_['id']} ({st_['kit']}) doit définir 'surfaces'")
            for it in st_.get("dressing", []):
                if it["type"] == "composite" and not it.get("parts"):
                    errs.append(f"asset_manifest : habillage composite sans 'parts' dans {st_['id']}")
    if script and cast:
        for l in script["lines"]:
            if l["speaker"] != "narrator" and l["speaker"] not in char_ids:
                errs.append(f"story_script : speaker {l['speaker']} absent de cast_bible")
    shot_chars = {}
    if sb:
        seen_lines = []
        ids = [s["id"] for s in sb["shots"]]
        if len(set(ids)) != len(ids):
            errs.append("storyboard : identifiants de plans dupliqués")
        for s in sb["shots"]:
            shot_chars[s["id"]] = {c["id"] for c in s["characters"]}
            for l in s["line_ids"]:
                if script and l not in line_ids:
                    errs.append(f"storyboard {s['id']} : réplique inconnue {l}")
            seen_lines += s["line_ids"]
            if assets and s["set_id"] not in set_ids:
                errs.append(f"storyboard {s['id']} : décor inconnu {s['set_id']}")
            for c in s["characters"]:
                if cast and c["id"] not in char_ids:
                    errs.append(f"storyboard {s['id']} : personnage inconnu {c['id']}")
            for p in s.get("props", []):
                if assets and p["id"] not in prop_ids:
                    errs.append(f"storyboard {s['id']} : accessoire inconnu {p['id']}")
                if p.get("held_by") and p["held_by"] not in shot_chars[s["id"]]:
                    errs.append(f"storyboard {s['id']} : {p['id']} tenu par {p['held_by']} absent du plan")
            st = s.get("start")
            if st and "line" in st:
                if st["line"] not in s["line_ids"]:
                    errs.append(f"storyboard {s['id']} : 'start' doit viser une réplique du plan")
                elif script and st.get("word", 0) >= words.get(st["line"], 0):
                    errs.append(f"storyboard {s['id']} : 'start.word' hors de la réplique {st['line']}")
            subj = s["camera"]["subject"]
            if isinstance(subj, str) and subj.startswith("ch_") and subj not in shot_chars[s["id"]]:
                errs.append(f"storyboard {s['id']} : sujet caméra {subj} absent du plan")
            if isinstance(subj, str) and subj.startswith("pr_") and subj not in {p["id"] for p in s.get("props", [])}:
                errs.append(f"storyboard {s['id']} : sujet caméra {subj} n'est pas placé dans le plan")
        if script:
            missing = sorted(line_ids - set(seen_lines))
            if missing:
                errs.append(f"storyboard : répliques non couvertes par un plan {missing}")
            order = [l for l in seen_lines]
            dedup = []
            for l in order:
                if not dedup or dedup[-1] != l:
                    dedup.append(l)
            if dedup != sorted(dedup):
                errs.append("storyboard : les plans doivent suivre l'ordre des répliques")
    if ap and sb:
        for sid, block in ap["shots"].items():
            if sid not in shot_chars:
                errs.append(f"animation_plan : plan inconnu {sid}")
                continue
            for key in ("actions", "expressions"):
                for a in block.get(key, []):
                    if a["char"] not in shot_chars[sid]:
                        errs.append(f"animation_plan {sid} : {a['char']} n'est pas dans le plan")
                    at = a["at"]
                    if "line" in at:
                        shot = next(s for s in sb["shots"] if s["id"] == sid)
                        if at["line"] not in shot["line_ids"]:
                            errs.append(f"animation_plan {sid} : ancrage sur {at['line']} qui n'appartient pas au plan")
                        elif script and at.get("word", 0) >= words.get(at["line"], 0):
                            errs.append(f"animation_plan {sid} : mot {at.get('word')} hors de {at['line']}")
            shot = next(s for s in sb["shots"] if s["id"] == sid)
            placed = {p["id"] for p in shot.get("props", [])}
            for p in block.get("props", []):
                if p["prop"] not in placed:
                    errs.append(f"animation_plan {sid} : accessoire {p['prop']} non placé dans le storyboard du plan")
    return errs


def capability_errors():
    """Les enums des schémas doivent correspondre exactement aux capacités du moteur."""
    errs = []
    ap = read_json(SCHEMAS / "animation_plan.schema.json")
    cb = read_json(SCHEMAS / "cast_bible.schema.json")
    am = read_json(SCHEMAS / "asset_manifest.schema.json")
    sb = read_json(SCHEMAS / "storyboard.schema.json")
    R = engine_registry
    pairs = [
        ("actions", ap["$defs"]["action_name"]["enum"], R.ACTIONS),
        ("expressions(animation)", ap["$defs"]["expression"]["enum"], R.EXPRESSIONS),
        ("expressions(cast)", cb["properties"]["characters"]["items"]["properties"]["expressions"]["items"]["enum"], R.EXPRESSIONS),
        ("prop_actions", ap["properties"]["shots"]["additionalProperties"]["properties"]["props"]["items"]["properties"]["action"]["enum"], R.PROP_ACTIONS),
        ("fx", ap["properties"]["shots"]["additionalProperties"]["properties"]["fx"]["items"]["properties"]["type"]["enum"], R.FX),
        ("prop_types", am["$defs"]["prop_type"]["enum"], R.PROP_TYPES),
        ("kits", am["properties"]["sets"]["items"]["properties"]["kit"]["enum"], R.KITS),
        ("moods", sb["properties"]["shots"]["items"]["properties"]["mood"]["enum"], R.MOODS),
        ("framings", sb["properties"]["shots"]["items"]["properties"]["camera"]["properties"]["framing"]["enum"], R.FRAMINGS),
        ("moves", sb["properties"]["shots"]["items"]["properties"]["camera"]["properties"]["move"]["enum"], R.MOVES),
        ("transitions", sb["properties"]["shots"]["items"]["properties"]["transition_out"]["enum"], R.TRANSITIONS),
        ("hair", cb["properties"]["characters"]["items"]["properties"]["design"]["properties"]["hair"]["properties"]["style"]["enum"], R.HAIR_STYLES),
        ("accessories", cb["properties"]["characters"]["items"]["properties"]["design"]["properties"]["accessories"]["items"]["enum"], R.ACCESSORIES),
    ]
    for name, a, b in pairs:
        if list(a) != list(b):
            errs.append(f"vocabulaire '{name}' : schéma {sorted(set(a) ^ set(b))} diffère du moteur")
    return errs


def validate_episode(ep_dir, only=None):
    """-> dict {artefact: [erreurs]} ; clé '_cross' pour les règles croisées."""
    arts = load_episode(ep_dir)
    report = {}
    for name, data in arts.items():
        if only and name not in only:
            continue
        report[name] = schema_errors(name, data)
    report["_cross"] = cross_errors(arts)
    return report


def provenance_deps(ep_dir, names):
    deps = []
    for n in names:
        p = Path(ep_dir) / ARTIFACTS[n]
        if p.exists():
            deps.append({"path": ARTIFACTS[n], "sha256": sha256_file(p)})
    return deps
