"""CLI `studio` : toutes les opérations déterministes du pipeline. Les agents Codex appellent ces commandes ;
ils ne réimplémentent jamais rendu, timing, mixage ou contrôles techniques à la main.

Usage : scripts/studio <commande> [options]   (ou PYTHONPATH=pipeline python3 -m studio ...)
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import audio, compose, contracts, hardware, memory, render
from .compile import CompileError, compile_episode
from .qa import frames as qframes
from .qa import tech
from .state import STAGES, State
from .util import ROOT, cache_dir, episode_dir, load_config, now, read_json, run, sha256_file, sha256_json, write_json

CFG = None


def cfg():
    global CFG
    if CFG is None:
        CFG = load_config()
    return CFG


def human_gates():
    q = cfg()["quality"]
    if q.get("autonomous"):
        return []
    return q.get("human_gates", ["gate_script", "gate_lookdev", "gate_prototype", "gate_first_cut"])


FIX_OWNER = {"char_never_visible": "director", "char_offscreen": "director", "subject_too_small": "director", "head_cropped": "director",
             "face_under_subtitles": "director", "face_away": "director/animator", "face_profile": "director/animator",
             "foreground_occluder": "director", "out_of_set": "director/animator", "inside_furniture": "animator",
             "char_overlap": "director/animator", "floating_prop": "environment-artist/animator", "render_failed": "pipeline-engineer",
             "prop_in_character": "director/animator", "subject_too_close": "director"}


# Seuls ces défauts BLOQUENT une validation automatique : vidéo inutilisable (sévérité blocker : conteneur, codec,
# résolution, piste audio, désynchro, écran noir, rendu en échec) ou personnage principal jamais visible.
# Les autres défauts « major » deviennent des RÉSERVES (listées, non bloquantes) : ils ne relancent pas Codex.
HARD_SCENE = ("char_never_visible", "render_failed")


def _check_key(cid):
    parts = cid.split(":")
    return parts[1] if len(parts) > 1 and parts[0].startswith("sh_") else parts[0]


def _is_hard(c):
    if c.get("status") != "fail":
        return False
    return c.get("severity") == "blocker" or (c.get("severity") == "major" and _check_key(c["id"]) in HARD_SCENE)


def _owner(c):
    key = _check_key(c["id"])
    return FIX_OWNER.get(key, "pipeline-engineer" if c.get("category") in ("technical", "audio", "sync", "subtitles") else "director")


def _qa_blockers(q, checks=None):
    """Défauts bloquants (durs) d'un rapport QA, avec le rôle chargé de la correction."""
    checks = checks if checks is not None else read_json(q)["checks"]
    return [f"[{_owner(c)}] {c['id']} : {c['message']}" for c in checks if _is_hard(c)]


def _qa_reserves(checks):
    return [f"{c['id']} : {c['message']}" for c in checks
            if c.get("status") == "fail" and c.get("severity") in ("blocker", "major") and not _is_hard(c)]


def auto_gate_ok(p, gate):
    """Mode autonome : conditions objectives pour valider une gate sans humain. -> (ok, raison détaillée)"""
    qa = {"gate_prototype": "qa_prototype.json", "gate_first_cut": "qa_first_cut.json"}.get(gate)
    if qa is None:
        return True, ""   # gate_script / gate_lookdev : la revue indépendante (dépendance) a déjà approuvé
    q = p / qa
    if not q.exists():
        return False, f"{qa} absent"
    blockers = _qa_blockers(q)
    if blockers:
        return False, f"QA bloquante ({qa}) : " + " | ".join(blockers[:8])
    return True, ""


def ep_path(ep):
    p = episode_dir(cfg(), ep)
    if not p.exists():
        sys.exit(f"épisode introuvable : {p}")
    return p


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ------------------------------------------------------------------ commandes de base
def cmd_doctor(a):
    res = hardware.diagnose(cfg())
    write_json(cache_dir(cfg()) / "hardware.json", res)
    out(res)
    return 1 if res["blocking"] else 0


def cmd_new(a):
    ep = a.episode
    p = episode_dir(cfg(), ep)
    if p.exists() and any(p.iterdir()):
        sys.exit(f"{p} existe déjà")
    locked = chars = None
    if a.script_file:
        from . import script_import
        raw = Path(a.script_file).read_text(encoding="utf-8")
        try:
            locked, chars = script_import.parse(raw)
        except ValueError as e:
            sys.exit(str(e))
        story = raw
        a.kind = "user_script"
        if a.duration is None:
            a.duration = max(8, min(180, script_import.estimate_duration(locked)))
    else:
        story = Path(a.story_file).read_text(encoding="utf-8") if a.story_file else a.story
    if not story:
        sys.exit("--story, --story-file ou --script-file requis")
    if a.duration is None:
        a.duration = 90
    for d in ("reviews", "renders", "checks", "lookdev", "shots", "audio"):
        (p / d).mkdir(parents=True, exist_ok=True)
    brief = {"contract": "episode_brief", "contract_version": contracts.CONTRACT_VERSION, "episode_id": ep, "status": "approved",
             "provenance": {"created_by": "human", "created_at": now()}, "source_story": story.strip(), "source_kind": a.kind,
             "target_duration_s": a.duration, "duration_tolerance_s": 10, "language": "fr-FR",
             "style": {"visual": "cartoon 3D low-poly goofy, couleurs saturées, contours encrés, expressions exagérées",
                       "tone": ["absurde", "WTF", "humour noir"], "references_to_avoid_copying": ["personnages/assets de chaînes existantes"]},
             "voice": {"narrator_gender": "any", "energy": "lively"}, "stop_after": a.stop_after}
    if locked:
        from . import script_import
        brief["script_lock"] = script_import.lock(locked)
        brief["title_hint"] = "script imposé par l'utilisateur"
    errs = contracts.schema_errors("episode_brief", brief)
    if errs:
        sys.exit("\n".join(errs))
    write_json(p / "episode_brief.json", brief)
    st = State(p, ep)
    st.finish("brief")
    if locked:
        write_json(p / "story_script.json", script_import.skeleton(ep, locked, now()))
        print(f"Script imposé importé et VERROUILLÉ : {len(locked)} répliques, durée estimée {a.duration:.0f} s.")
        print("Personnages détectés : " + (", ".join(f"{k} ({v})" for k, v in chars.items()) or "aucun (narration seule)"))
        for i, l in enumerate(locked, 1):
            print(f"  l{i:03d} [{l['speaker']}] {l['text']}")
        print(f"Étape suivante : story-architect HABILLE le script (sans changer le texte), puis `studio submit {ep} script`.")
        return
    print(f"Épisode créé : {p}\nÉtape suivante : story-architect écrit story_script.json, puis `studio submit {ep} script`.")


def cmd_validate(a):
    rep = contracts.validate_episode(ep_path(a.episode), only=set(a.only.split(",")) if a.only else None)
    rep["_capabilities"] = contracts.capability_errors()
    bad = {k: v for k, v in rep.items() if v}
    out(bad or {"ok": True, "checked": sorted(k for k in rep if not k.startswith("_"))})
    return 1 if bad else 0


def cmd_status(a):
    p = ep_path(a.episode)
    st = State(p)
    ch = st.refresh()
    print(f"Épisode {a.episode}" + (f"  (changements détectés : {ch})" if ch else ""))
    for name, status, owner, kind, att, note in st.summary():
        mark = {"completed": "✔", "approved": "✔", "running": "…", "failed": "✘", "stale": "↺", "interrupted": "⚠", "needs_review": "?"}.get(status, " ")
        print(f" {mark} {name:<18} {status:<12} {kind:<7} {owner:<45} {note[:60]}")
    print("Prêtes :", ", ".join(st.ready()) or "aucune")
    for d in st.data.get("human_decisions", []):
        print(f"Décision humaine ({d['gate']}, {d['at'][:16]}) : {d['note']}")
    return 0


# ------------------------------------------------------------------ soumission des étapes agents / revues
def cmd_submit(a):
    p = ep_path(a.episode)
    st = State(p)
    stage = a.stage
    if stage not in STAGES:
        sys.exit(f"étape inconnue {stage}")
    owner, kind, ins, outs, deps, _ = STAGES[stage]
    if kind == "gate":
        sys.exit("une gate se valide avec `studio approve` (humain)")
    missing = [d for d in deps if st.st(d)["status"] not in ("completed", "approved")]
    if missing and not a.force:
        sys.exit(f"dépendances non satisfaites : {missing} (voir `studio status`)")
    if kind == "agent":
        rep = contracts.validate_episode(p)
        names = [n for n, f in contracts.ARTIFACTS.items() if f in outs]
        errs = {k: v for k, v in rep.items() if v and (k in names or k == "_cross")}
        if errs:
            st.fail(stage, json.dumps(errs, ensure_ascii=False)[:1500])
            out({"stage": stage, "status": "failed", "errors": errs})
            return 1
        st.finish(stage)
        out({"stage": stage, "status": "completed"})
        return 0
    if kind == "review":
        if not a.review:
            sys.exit("--review <fichier> requis (un par critique)")
        verdicts, blockers = [], []
        for rp in a.review:
            rpath = (p / rp) if not Path(rp).is_absolute() else Path(rp)
            r = read_json(rpath)
            errs = contracts.schema_errors("review_report", r)
            if errs:
                sys.exit(f"{rp} invalide :\n" + "\n".join(errs))
            tgt = p / r["target"]["path"] if not Path(r["target"]["path"]).is_absolute() else Path(r["target"]["path"])
            if not tgt.exists() or sha256_file(tgt) != r["target"]["sha256"]:
                sys.exit(f"{rp} : la cible a changé depuis la revue (hash différent) : revue périmée, relancer le critique.")
            verdicts.append(r["verdict"])
            blockers += [f for f in r["findings"] if f["severity"] == "blocker"]
            low = [k for k, v in r["scores"].items() if v["score"] < cfg()["quality"]["min_dimension_score"]]
            if low and r["verdict"] == "approve":
                print(f"attention : {rp} approuve malgré des scores bas {low}")
        s = st.st(stage)
        if not blockers:
            # seuls les findings « blocker » bloquent ; major/minor = notes (pas de nouveau tour de revue)
            st.finish(stage, note=f"revues: {a.review} (verdicts {verdicts}, notes non bloquantes)")
            out({"stage": stage, "status": "completed", "verdicts": verdicts})
            return 0
        human = [f for f in blockers if f.get("fix_owner") == "human"]
        if human:
            # seul l'utilisateur peut trancher (droits, choix créatif) : inutile de faire tourner les agents
            st.finish(stage, "needs_review", note="DÉCISION HUMAINE requise : " + " | ".join(f"{f['id']} {f['description'][:160]}" for f in human))
            out({"stage": stage, "status": "needs_review", "human_decision": [f["id"] for f in human]})
            return 2
        s["revision_rounds"] = s.get("revision_rounds", 0) + 1
        if s["revision_rounds"] > int(cfg()["quality"]["max_revision_rounds"]):
            if cfg()["quality"].get("on_budget_exhausted", "continue") == "continue":
                note = "accepté AVEC RÉSERVES après corrections : " + " | ".join(f"{f['id']} {f['description'][:120]}" for f in blockers)
                st.data.setdefault("reserves", []).append({"stage": stage, "at": now(), "items": [f"{f['id']} {f['description'][:200]}" for f in blockers]})
                st.finish(stage, note=note[:400])
                out({"stage": stage, "status": "completed", "with_reserves": [f["id"] for f in blockers]})
                return 0
            st.finish(stage, "needs_review", note=f"budget de corrections épuisé ({s['revision_rounds'] - 1}) : ESCALADE HUMAINE")
            out({"stage": stage, "status": "needs_review", "escalation": True, "blockers": blockers})
            return 2
        st.fail(stage, f"verdicts {verdicts}, {len(blockers)} bloquant(s) : corriger puis re-soumettre (tour {s['revision_rounds']})")
        out({"stage": stage, "status": "failed", "revision_round": s["revision_rounds"], "blockers": blockers})
        return 1
    sys.exit(f"{stage} est une étape automatique : utiliser `studio run {a.episode}`")


def cmd_approve(a):
    p = ep_path(a.episode)
    st = State(p)
    gate = a.gate
    if gate not in STAGES or STAGES[gate][1] != "gate":
        sys.exit(f"{gate} n'est pas une gate")
    human = human_gates()
    if a.by != "human" and gate in human:
        sys.exit(f"{gate} exige une validation HUMAINE (config quality.human_gates)")
    if a.by == "human":
        if not sys.stdin.isatty():
            sys.exit("validation humaine : commande à lancer dans un terminal interactif par l'utilisateur (pas par un agent)")
        typed = input(f"Validation humaine de {gate} pour {a.episode}. Tapez l'identifiant de l'épisode pour confirmer : ").strip()
        if typed != a.episode:
            sys.exit("confirmation incorrecte : rien n'a été validé")
    deps = [d for d in STAGES[gate][4] if st.st(d)["status"] not in ("completed", "approved")]
    if deps and not a.override:
        sys.exit(f"pré-requis non satisfaits {deps} ; `--override` (humain) possible avec une note")
    if deps:
        # décision humaine qui lève un blocage (ex. risque de droits assumé) : consignée, transmise aux agents
        if a.by != "human" or not (a.note or "").strip():
            sys.exit("--override exige une validation humaine et une note expliquant la décision (--note \"...\")")
        for d in deps:
            if st.st(d)["status"] in ("needs_review", "failed"):
                st.st(d).update(status="completed", note=f"levé par décision humaine : {a.note}"[:300])
        st.data.setdefault("human_decisions", []).append({"gate": gate, "waived": deps, "note": a.note, "at": now()})
        st.log("human_override", gate=gate, waived=deps, note=a.note[:300])
    st.approve(gate, a.by, a.note or "")
    print(f"{gate} approuvée par {a.by} (liée aux hashes actuels des artefacts).")


# ------------------------------------------------------------------ étapes automatiques
def _manifest(p):
    return read_json(p / "shot_manifest.json")


def _render_and_assemble(p, shots, profile, out_rel, kind):
    c = cfg()
    man = _manifest(p)
    tl = read_json(p / "audio_timeline.json")
    sel = [s for s in man["shots"] if s["id"] in shots] if shots else man["shots"]
    recs = render.render_shots(c, p, sel, profile)
    stats = {"rendered": sum(r["status"] == "rendered" for r in recs), "cached": sum(r["status"] == "cached" for r in recs),
             "failed": [r["id"] for r in recs if r["status"] == "failed"]}
    rm = {"contract": "render_manifest", "contract_version": contracts.CONTRACT_VERSION, "episode_id": man["episode_id"], "status": "generated",
          "provenance": {"created_by": "studio render", "created_at": now(), "depends_on": contracts.provenance_deps(p, ["shot_manifest"])},
          "profile": profile, "engine_version": render.engine_hash()[:12], "shots": recs, "output": None}
    if stats["failed"]:
        write_json(p / f"render_manifest_{profile}.json", rm)
        raise RuntimeError(f"plans en échec : {stats['failed']} (voir render_manifest_{profile}.json / blender.log)")
    prof = render.profile_dict(c, profile)
    res = compose.assemble(c, p, man, tl, recs, prof, p / out_rel, fps=man["fps"])
    rm["output"] = out_rel
    write_json(p / f"render_manifest_{profile}.json", rm)
    W, H = res["resolution"]
    allowed_black = [s["end_s"] - res["start_s"] for s in man["shots"] if s.get("transition_out") == "fade_black"]
    checks, dur = tech.check_video(p / out_rel, expected_duration=res["end_s"] - res["start_s"], expected_frames=res["expected_frames"],
                                   spec={"width": W, "height": H}, subs_path=(p / out_rel).with_suffix(".ass"), allowed_black=allowed_black, cfg=c)
    checks += tech.scene_checks_to_qa(recs)
    qa = tech.report(p / out_rel, checks, man["episode_id"], kind)
    write_json(p / f"qa_{Path(out_rel).stem}.json", qa)
    if kind == "final":
        write_json(p / "qa_report.json", qa)
    return {"output": str(p / out_rel), **stats, "qa_summary": qa["summary"], "duration_s": round(dur, 2)}


def stage_voice(p, st):
    return audio.build_voice(p, cfg())


def stage_compile(p, st):
    try:
        man = compile_episode(p, cfg())
    except CompileError as e:
        raise RuntimeError(str(e))
    return {"shots": len(man["shots"]), "frames": man["total_frames"], "warnings": man["warnings"]}


def stage_lookdev(p, st, profile="preview"):
    c = cfg()
    cast = read_json(p / "cast_bible.json")["characters"]
    assets = read_json(p / "asset_manifest.json")
    sdir = p / "lookdev" / "specs"
    sdir.mkdir(parents=True, exist_ok=True)
    void = {"id": "set_lookdev", "kit": "studio_void", "source": "procedural", "license": {"spdx": "original", "commercial_use": True}, "use_kit_dressing": False}
    shots, captions = [], {}
    for ch in cast:
        for kind, framing, acts, exprs in (("face", "medium_close", [], [("neutral", 1), ("happy", 11), ("shocked", 21), ("angry", 31)]),
                                           ("body", "full", [{"char": ch["id"], "action": "wave", "frame": 5, "duration_frames": 30, "intensity": 1.0, "target": None, "prop": None}], [("happy", 1)])):
            sid = f"ld_{ch['id']}_{kind}"
            spec = {"shot_id": "sh_900", "episode_id": read_json(p / "episode_brief.json")["episode_id"], "fps": 30, "frames": 40, "engine_version": "lookdev",
                    "set": void, "mood": "day_warm", "characters": [{"id": ch["id"], "design": ch["design"], "pos": [0, 0], "facing_deg": 0.0, "facing_target": None, "start_pose": "stand"}],
                    "props": [], "camera": {"framing": framing, "subject": {"kind": "char", "id": ch["id"]}, "angle": "eye", "move": "static", "motivation": "lookdev"},
                    "actions": acts, "expressions": [{"char": ch["id"], "expr": e, "frame": f, "intensity": 1.0} for e, f in exprs],
                    "prop_actions": [], "fx": [], "talk": [], "auto_idle": True, "transition_out": "cut"}
            sp = sdir / f"{sid}.json"
            write_json(sp, spec)
            frames = "8,18,28,38" if kind == "face" else "20"
            shots.append(({"id": sid, "spec_path": str(sp.relative_to(p)), "spec_sha256": sha256_json(spec), "frames": 40}, frames))
            captions[sid] = (ch["name"], ["neutre", "content", "choqué", "énervé"] if kind == "face" else ["corps entier"])
    for s in assets["sets"]:
        sid = f"ld_{s['id']}"
        spec = {"shot_id": "sh_901", "episode_id": assets["episode_id"], "fps": 30, "frames": 2, "engine_version": "lookdev", "set": s, "mood": "day_warm",
                "characters": [], "props": [], "camera": {"framing": "wide", "subject": {"kind": "point", "pos": [0, 0.5, 1.0]}, "angle": "eye", "move": "static", "motivation": "lookdev"},
                "actions": [], "expressions": [], "prop_actions": [], "fx": [], "talk": [], "auto_idle": False, "transition_out": "cut"}
        sp = sdir / f"{sid}.json"
        write_json(sp, spec)
        shots.append(({"id": sid, "spec_path": str(sp.relative_to(p)), "spec_sha256": sha256_json(spec), "frames": 2}, "1"))
        captions[sid] = (s["id"], [s["kit"]])
    items, failed = [], []
    for shot, fr in shots:
        rec = render.render_shot(c, p, shot, profile, mode="stills", frames=fr)
        if rec["status"] == "failed":
            failed.append((shot["id"], rec.get("error")))
            continue
        name, labels = captions[shot["id"]]
        for k, f in enumerate(fr.split(",")):
            src = Path(rec["frames_dir"]) / f"f{int(f):04d}.png"
            dst = p / "lookdev" / f"{shot['id']}_{f}.png"
            shutil.copy(src, dst)
            items.append((dst, f"{name}\n{labels[min(k, len(labels) - 1)]}"))
    if failed:
        raise RuntimeError(f"lookdev en échec : {failed}")
    sheet = qframes.contact_sheet(items, p / "lookdev" / "contact_sheet.png", cols=4, title="LOOKDEV — personnages, expressions, décors")
    return {"contact_sheet": str(sheet), "images": len(items)}


def _prototype_shots(man, seconds):
    sel, t = [], 0.0
    for s in man["shots"]:
        sel.append(s["id"])
        t = s["end_s"]
        if t >= seconds:
            break
    return sel


def stage_prototype(p, st, shots=None, seconds=8.0, profile=None):
    profile = profile or cfg()["render"].get("prototype_profile", "preview")
    man = _manifest(p)
    sel = shots or _prototype_shots(man, seconds)
    return _render_and_assemble(p, sel, profile, "renders/prototype.mp4", "prototype")


def stage_shots_check(p, st, profile="draft"):
    c = cfg()
    man = _manifest(p)
    script = {l["id"]: l for l in read_json(p / "story_script.json")["lines"]}
    recs = render.render_shots(c, p, man["shots"], profile, mode="stills")
    items, all_checks = [], []
    for s, r in zip(man["shots"], recs):
        if r["status"] == "failed":
            all_checks.append({"shot": s["id"], "id": "render_failed", "severity": "blocker", "status": "fail", "message": r.get("error")})
            continue
        rep = r["scene_report"] or {}
        for ck in rep.get("checks", []):
            all_checks.append({"shot": s["id"], **ck})
        frs = rep.get("rendered_frames") or rep.get("sample_frames") or [1]
        mid = sorted(frs, key=lambda f: abs(f - s["frames"] // 2))[0]
        dst = p / "checks" / f"{s['id']}_f{mid:04d}.png"
        shutil.copy(Path(r["frames_dir"]) / f"f{mid:04d}.png", dst)
        n_issue = sum(1 for ck in rep.get("checks", []) if ck["status"] != "pass")
        items.append((dst, f"{s['id']}  {s['start_s']:.1f}-{s['end_s']:.1f}s  ⚠{n_issue}\n{script[s['line_ids'][0]]['text'][:70]}"))
    sheet = qframes.contact_sheet(items, p / "checks" / "shots_contact.png", cols=4, title=f"{man['episode_id']} — 1 image de contrôle par plan")
    write_json(p / "checks" / "scene_checks.json", {"generated_at": now(), "profile": profile, "checks": all_checks})
    blockers = [x for x in all_checks if _is_hard(x)]
    if blockers:
        lines = [f"[{FIX_OWNER.get(b['id'].split(':')[0], 'director')}] {b['shot']}:{b['id']} : {b['message']}" for b in blockers]
        if all(b["id"].startswith("render_failed") for b in blockers):
            st.finish("shots_check", "needs_review", note="rendu en échec (problème technique, pas de tour Codex) : " + " | ".join(lines[:5]))
            return {"contact_sheet": str(sheet), "blocking": lines, "status": "needs_review"}
        if cfg()["quality"].get("autonomous"):
            # mode autonome : tour de correction (le pilote confie les défauts à leur propriétaire), puis escalade
            s_ = st.st("shots_check")
            s_["revision_rounds"] = s_.get("revision_rounds", 0) + 1
            if s_["revision_rounds"] <= int(cfg()["quality"]["max_revision_rounds"]):
                st.fail("shots_check", f"tour {s_['revision_rounds']} : corriger (sans rendu) puis le pilote revérifie. " + " | ".join(lines[:10]))
                return {"contact_sheet": str(sheet), "blocking": lines, "status": "failed", "revision_round": s_["revision_rounds"]}
        st.finish("shots_check", "needs_review", note=f"{len(blockers)} défaut(s) majeur(s) : voir checks/scene_checks.json")
        return {"contact_sheet": str(sheet), "blocking": lines, "status": "needs_review"}
    return {"contact_sheet": str(sheet), "issues": len(all_checks)}


def stage_first_cut(p, st, profile=None):
    profile = profile or cfg()["render"].get("first_cut_profile", "preview")
    return _render_and_assemble(p, None, profile, "renders/first_cut.mp4", "first_cut")


def _require_gates(st, gates):
    bad = [g for g in gates if not st.approval_valid(g)]
    if bad:
        raise RuntimeError(f"rendu final refusé : validations humaines manquantes ou périmées {bad}")


def stage_final(p, st):
    _require_gates(st, ["gate_script", "gate_prototype", "gate_first_cut"])
    return _render_and_assemble(p, None, cfg()["render"].get("final_profile", "final"), "renders/final.mp4", "final")


def stage_delivery(p, st):
    qa = read_json(p / "qa_report.json")
    hard = _qa_blockers(None, qa["checks"])
    if hard:
        raise RuntimeError("QA finale : vidéo inutilisable, livraison refusée : " + " | ".join(hard[:5]))
    reserves = _qa_reserves(qa["checks"]) + [f"{r['stage']} : {x}" for r in st.data.get("reserves", []) for x in r["items"]]
    fin = p / "renders" / "final.mp4"
    tl = read_json(p / "audio_timeline.json")
    assets = read_json(p / "asset_manifest.json")
    licenses = [{"asset": s["id"], **s["license"]} for s in assets["sets"]] + [{"asset": x["id"], **x["license"]} for x in assets["props"]]
    licenses.append({"asset": "voice", "spdx": tl["tts"]["backend"], "note": tl["tts"].get("license")})
    licenses.append({"asset": "music", "spdx": "original", "note": (tl.get("music") or {}).get("license")})
    man = {"contract": "episode_manifest", "contract_version": contracts.CONTRACT_VERSION, "episode_id": qa["episode_id"], "status": "generated",
           "provenance": {"created_by": "studio delivery", "created_at": now()},
           "deliverables": [{"path": "renders/final.mp4", "sha256": sha256_file(fin), "kind": "video", "spec": {"res": "1080x1920", "fps": 30, "codec": "h264/aac"}},
                            {"path": "renders/final.ass", "sha256": sha256_file(fin.with_suffix(".ass")), "kind": "subtitles"}],
           "gates": [{"gate": a["gate"], "status": "approved" if st.approval_valid(a["gate"]) else "périmée", "approved_by": a["by"], "at": a["at"], "note": a.get("note", "")} for a in st.data["approvals"]],
           "qa_summary": qa["summary"], "reviews": sorted(str(x.relative_to(p)) for x in (p / "reviews").glob("*.json")),
           "licenses": licenses, "cost_log": st.data.get("cost_log", []),
           "limitations": ["Les scores des critiques sont des appréciations, pas des mesures.",
                           "La QA technique ne garantit pas la qualité visuelle ni l'intérêt narratif.",
                           "Conformité plateforme évaluée par analyse contextuelle, pas par l'outil de modération de la plateforme."],
           "reserves": reserves,
           "publication": "NOT_PUBLISHED"}
    write_json(p / "episode_manifest.json", man)
    return {"manifest": str(p / "episode_manifest.json")}


AUTO = {"voice": stage_voice, "compile": stage_compile, "lookdev": stage_lookdev, "prototype": stage_prototype, "shots_check": stage_shots_check,
        "first_cut": stage_first_cut, "final": stage_final, "delivery": stage_delivery}

NEXT_HINT = {
    "agent": "agent `{owner}` : produire {outs}, puis `studio submit {ep} {stage}`",
    "review": "critique(s) `{owner}` (lecture seule) : écrire reviews/<role>_<gate>_rN.json, puis `studio submit {ep} {stage} --review <fichiers>`",
    "gate": "HUMAIN : inspecter puis lancer soi-même `studio approve {ep} {stage}` dans un terminal (ou activer quality.autonomous)",
}


def run_stage(p, st, name, **kw):
    for d in ("reviews", "renders", "checks", "lookdev", "shots", "audio"):
        (p / d).mkdir(parents=True, exist_ok=True)
    st.start(name)
    try:
        res = AUTO[name](p, st, **kw) if kw else AUTO[name](p, st)
    except Exception as e:
        st.fail(name, e)
        raise
    if st.st(name)["status"] == "running":
        st.finish(name)
    return res


def cmd_run(a):
    p = ep_path(a.episode)
    st = State(p)
    st.refresh()
    stop_after = read_json(p / "episode_brief.json").get("stop_after")
    executed = []
    autonomous = bool(cfg()["quality"].get("autonomous"))
    while True:
        ready = st.ready()
        # gates non humaines (mode autonome) : validées automatiquement si les conditions objectives sont réunies
        auto_gates = [r for r in ready if STAGES[r][1] == "gate" and r not in human_gates()]
        if auto_gates:
            g = auto_gates[0]
            ok, why = auto_gate_ok(p, g)
            if not ok:
                gs = st.st(g)
                gs["revision_rounds"] = gs.get("revision_rounds", 0) + 1
                if "[pipeline-engineer]" in why and "[director" not in why and "[animator" not in why:
                    # problème technique du pipeline : un agent de production ne peut pas le corriger (règle 10)
                    st.finish(g, "needs_review", note=f"problème technique du pipeline (à signaler, pas de tour Codex) : {why}")
                    print(f"⚠ {g} : problème technique du pipeline — arrêt sans relancer Codex ({why})")
                elif gs["revision_rounds"] > int(cfg()["quality"]["max_revision_rounds"]):
                    st.finish(g, "needs_review", note=f"budget de corrections épuisé : {why}")
                    print(f"⚠ {g} : toujours refusée après {gs['revision_rounds'] - 1} correction(s) — arrêt ({why})")
                else:
                    # tour de correction : l'agent fix_owner corrige ses artefacts ; les plans touchés seront re-rendus
                    st.fail(g, f"tour {gs['revision_rounds']} : corriger puis re-rendre. {why}")
                    print(f"⚠ {g} : refusée, tour de correction {gs['revision_rounds']} ({why})")
                break
            st.approve(g, "auto:studio", "mode autonome : revues approuvées et QA non bloquante")
            print(f"✔ {g} validée automatiquement")
            executed.append((g, {"auto_approved": True}))
            if stop_after and g == f"gate_{stop_after}":
                break
            continue
        auto = [r for r in ready if STAGES[r][1] == "auto" and (r != "final" or autonomous)
                and st.st(r)["status"] != "needs_review" and r not in [e for e, _ in executed]]
        if a.until and a.until in [e for e, _ in executed]:
            break
        if not auto:
            break
        name = auto[0]
        print(f"→ {name}")
        try:
            res = run_stage(p, st, name)
        except Exception as e:
            print(f"✘ {name} : {e}")
            return 1
        executed.append((name, res))
        print(json.dumps(res, ensure_ascii=False)[:800])
        if st.st(name)["status"] not in ("completed", "approved"):
            # défauts à corriger (needs_review / tour de correction) : ne JAMAIS relancer en boucle la même étape
            print(f"⚠ {name} : {st.st(name)['status']} — corrections nécessaires avant de continuer")
            break
        if stop_after and name == stop_after:
            break
    pending = []
    for r in st.ready():
        owner, kind, _, outs, _, _ = STAGES[r]
        if st.st(r)["status"] in ("needs_review", "failed") and kind == "auto":
            pending.append(f"{r} : {st.st(r)['status']} — corriger les défauts ({(st.st(r).get('note') or st.st(r).get('error') or '')[:300]})")
        elif kind == "auto":
            pending.append(f"{r} : `studio final {a.episode}` (exige les validations)" if r == "final" else f"{r} : automatique")
        else:
            pending.append(f"{r} : " + NEXT_HINT[kind].format(owner=owner, outs=outs, ep=a.episode, stage=r))
    print("\nÀ faire ensuite :\n  " + "\n  ".join(pending or ["rien : épisode terminé ou bloqué (voir `studio status`)"]))
    return 0


def _single(a, name, **kw):
    p = ep_path(a.episode)
    st = State(p)
    st.refresh()
    deps = [d for d in STAGES[name][4] if st.st(d)["status"] not in ("completed", "approved")]
    if deps and not getattr(a, "force", False):
        sys.exit(f"{name} : dépendances non satisfaites {deps} (option --force pour une itération de travail hors DAG)")
    out(run_stage(p, st, name, **kw))


def cmd_voice(a):
    _single(a, "voice")


def cmd_compile(a):
    _single(a, "compile")


def cmd_lookdev(a):
    _single(a, "lookdev", profile=a.profile)


def cmd_prototype(a):
    _single(a, "prototype", shots=a.shots.split(",") if a.shots else None, seconds=a.seconds, profile=a.profile)


def cmd_check_shots(a):
    _single(a, "shots_check", profile=a.profile)


def cmd_first_cut(a):
    _single(a, "first_cut", profile=a.profile)


def cmd_final(a):
    _single(a, "final")
    p = ep_path(a.episode)
    st = State(p)
    out(run_stage(p, st, "delivery"))


def cmd_render(a):
    """Rendu libre (itération de travail, hors DAG) d'un sous-ensemble de plans."""
    p = ep_path(a.episode)
    out(_render_and_assemble(p, a.shots.split(",") if a.shots else None, a.profile, a.out, "work"))


def cmd_qa(a):
    p = ep_path(a.episode)
    v = Path(a.video)
    checks, dur = tech.check_video(v, spec={"width": a.width, "height": a.height}, subs_path=v.with_suffix(".ass") if v.with_suffix(".ass").exists() else None, cfg=cfg())
    rep = tech.report(v, checks, read_json(p / "episode_brief.json")["episode_id"], "adhoc")
    if a.write:
        write_json(Path(a.write), rep)
    out(rep["summary"] | {"failed": [c for c in checks if c["status"] != "pass"]})
    return 1 if rep["summary"]["blocking"] else 0


def cmd_frames(a):
    p = ep_path(a.episode)
    v = Path(a.video) if Path(a.video).is_absolute() else p / a.video
    dur = float(json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(v)]).stdout)["format"]["duration"])
    if a.at:
        times = [float(x) for x in a.at.split(",")]
    else:
        man = _manifest(p)
        times = [min(dur - 0.05, (s["start_s"] + s["end_s"]) / 2 - (man["shots"][0]["start_s"] if a.relative else 0)) for s in man["shots"] if s["start_s"] < dur + 0.01] if a.per_shot else \
            [round(t * a.every, 2) for t in range(int(dur / a.every) + 1)]
    od = p / "checks" / f"frames_{v.stem}"
    paths = qframes.extract(v, times, od)
    sheet = qframes.contact_sheet([(pth, f"{t:.2f}s") for pth, t in zip(paths, times)], od / "contact.png", cols=4, title=f"{v.name} — frames horodatées")
    out({"frames": [str(x) for x in paths], "contact_sheet": str(sheet)})


def cmd_inject(a):
    """Injection volontaire d'un défaut pour vérifier que la QA le détecte (test G)."""
    p = ep_path(a.episode)
    src = p / a.video
    dst = p / "renders" / f"injected_{a.defect}.mp4"
    man = _manifest(p)
    if a.defect == "black_shot":
        s = next(x for x in man["shots"] if x["id"] == a.shot)
        t0 = s["start_s"] - man["shots"][0]["start_s"]
        t1 = t0 + (s["end_s"] - s["start_s"])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,{t0:.3f},{t1:.3f})'",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)])
        expect = ("black_frames", (round(t0, 2), round(t1, 2)))
    elif a.defect == "audio_offset":
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-itsoffset", "0.5", "-i", str(src), "-map", "0:v", "-map", "1:a", "-c", "copy", str(dst)])
        expect = ("av_start_sync", 0.5)
    elif a.defect == "offscreen_character":
        s = next(x for x in man["shots"] if x["id"] == a.shot)
        spec = read_json(p / s["spec_path"])
        subj = spec["camera"]["subject"]
        victim = subj["id"] if subj.get("kind") == "char" else spec["characters"][0]["id"]
        # défaut réaliste : la caméra vise un point vide, le personnage du plan n'est jamais visible
        spec["camera"]["subject"] = {"kind": "point", "pos": [-5.0, 0.5, 1.2]}
        spec["camera"]["framing"] = "close_up"
        spec["camera"]["move"] = "static"
        sp = p / "checks" / f"injected_{a.shot}.json"
        write_json(sp, spec)
        rec = render.render_shot(cfg(), p, {"id": a.shot, "spec_path": str(sp.relative_to(p)), "spec_sha256": sha256_json(spec), "frames": spec["frames"]}, "draft", mode="stills")
        found = [c for c in (rec.get("scene_report") or {}).get("checks", []) if c["id"].startswith(("char_never_visible", "char_offscreen")) and victim in c["id"]]
        res = {"defect": a.defect, "shot": a.shot, "victim": victim, "detected": bool(found), "evidence": found, "render_status": rec["status"]}
        write_json(p / "checks" / "injection_offscreen_character.json", res)
        out(res)
        return 0 if found else 1
    else:
        sys.exit("défauts : black_shot, audio_offset, offscreen_character")
    checks, _ = tech.check_video(dst, spec={"width": 1080, "height": 1920}, cfg=cfg())
    hit = [c for c in checks if c["id"] == expect[0] and c["status"] == "fail"]
    res = {"defect": a.defect, "injected_file": str(dst), "expected_check": expect[0], "expected_value": expect[1], "detected": bool(hit), "evidence": hit}
    write_json(p / "checks" / f"injection_{a.defect}.json", res)
    out(res)
    return 0 if hit else 1


def cmd_cache(a):
    if a.prune:
        n, total = render.prune_cache(cfg())
        out({"removed": n, "total_gb": round(total / (1 << 30), 2)})
    else:
        total, entries = render.cache_stats(cfg())
        out({"entries": len(entries), "total_gb": round(total / (1 << 30), 3), "limit_gb": cfg()["limits"]["max_cache_gb"]})


def cmd_memory(a):
    if a.action == "merge":
        for f in a.terms:
            target, added = memory.merge_file(cfg(), f)
            print(f"{f} -> {target} : {len(added)} entrée(s) récupérée(s)")
            for t in added:
                print("  +", t)
        return
    if a.action == "search":
        for e in memory.search(cfg(), a.terms, a.limit):
            print(f"## {e['title']}  [{e['file']}]\n{e['body']}\n")
    else:
        print(memory.add(cfg(), a.category, a.title, a.text, [t.strip() for t in a.tags.split(",")], a.episode))


def cmd_cost(a):
    p = ep_path(a.episode)
    st = State(p)
    st.add_cost(a.kind, a.amount, a.unit, a.note or "")
    out(st.data["cost_log"][-1])


def cmd_motion_suggest(a):
    """Indices de motion design repérés dans le script (téléphone, chiffres, ellipses, amour…). Le motion-designer décide."""
    from . import motion
    p = ep_path(a.episode)
    sug = motion.suggest(read_json(p / "story_script.json"))
    write_json(p / "checks" / "motion_suggestions.json", {"generated_at": now(), "suggestions": sug})
    out({"suggestions": sug, "fichier": str(p / "checks" / "motion_suggestions.json")})


def cmd_motion_preview(a):
    """Planche de contrôle du motion design (sans rendu 3D) : un instant par élément, zones TikTok en gris."""
    from . import motion
    p = ep_path(a.episode)
    rep = contracts.validate_episode(p)
    errs = {k: v for k, v in rep.items() if v and k in ("motion_design", "_cross")}
    if errs:
        out({"status": "invalide", "errors": errs})
        return 1
    tl = read_json(p / "audio_timeline.json") if (p / "audio_timeline.json").exists() else None
    if tl is None:
        sys.exit("audio_timeline.json absent : l'étape voice doit avoir tourné (les éléments sont ancrés sur la voix)")
    sheet = motion.preview(p, tl, p / "checks" / "motion_contact.png")
    out({"contact_sheet": str(sheet) if sheet else None, "elements": len((motion.load(p) or {}).get("elements", []))})


def cmd_kits(a):
    """Galerie des décors : un plan large par kit avec un personnage témoin (échelle). Aucun épisode requis."""
    import sys as _s
    _s.path.insert(0, str(ROOT / "blender"))
    from engine import registry as _reg
    c = cfg()
    kits = a.kits.split(",") if a.kits else [k for k in _reg.KITS if k != "studio_void"]
    out_dir = cache_dir(c) / "kits_gallery"
    out_dir.mkdir(parents=True, exist_ok=True)
    demo = read_json(ROOT / "assets" / "library" / "characters.json")["characters"][0]
    items = []
    for k in kits:
        spec = {"shot_id": "sh_950", "episode_id": "ep_kits_gallery", "fps": 30, "frames": 2, "engine_version": "kits",
                "set": {"id": f"set_{k}", "kit": k, "source": "procedural", "license": {"spdx": "original", "commercial_use": True}, "seed": 3},
                "mood": "interior_warm" if k in ("living_room", "kitchen", "bedroom", "bathroom", "restaurant", "classroom", "generic_interior", "car_interior")
                else ("office_flat" if k in ("office", "supermarket") else "day_warm"),
                "characters": [{"id": "ch_scale", "design": demo["design"], "pos": [-0.42, 0.25] if k == "car_interior" else [0.6, 0.9],
                                "facing_deg": 0.0 if k == "car_interior" else -20.0, "facing_target": None, "start_pose": "sit" if k == "car_interior" else "stand"}],
                "props": [], "camera": ({"framing": "medium", "subject": {"kind": "char", "id": "ch_scale"}, "angle": "eye", "side_deg": 15, "move": "static", "motivation": "galerie"}
                                        if k == "car_interior" else {"framing": "wide", "subject": {"kind": "point", "pos": [0.0, 1.2, 1.1]}, "angle": "eye", "move": "static", "motivation": "galerie"}),
                "actions": [], "expressions": [{"char": "ch_scale", "expr": "happy", "frame": 1, "intensity": 1.0}], "prop_actions": [], "fx": [], "talk": [],
                "auto_idle": False, "transition_out": "cut"}
        sp = out_dir / f"{k}.json"
        write_json(sp, spec)
        rec = render.render_shot(c, out_dir, {"id": k, "spec_path": sp.name, "spec_sha256": sha256_json(spec), "frames": 2}, a.profile, mode="stills", frames="1")
        if rec["status"] == "failed":
            print(f"✘ {k} : {rec.get('error')}")
            continue
        items.append((Path(rec["frames_dir"]) / "f0001.png", k))
    sheet = qframes.contact_sheet(items, out_dir / "kits_contact.png", cols=4, title="Décors disponibles (galerie des kits)")
    out({"contact_sheet": str(sheet), "kits": [k for _, k in items]})


LICENSE_OK = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "MIT", "Apache-2.0", "original"}


def _inspect(path, target_height=0.0):
    import subprocess
    c = cfg()
    out_dir = cache_dir(c) / "inspect" / sha256_file(path)[:16]
    cmd = render.blender_script_cmd(c, "inspect_model.py") + ["--model", str(path), "--out", str(out_dir)]
    if target_height:
        cmd += ["--target-height", str(target_height)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    rp = out_dir / "inspection.json"
    return read_json(rp) if rp.exists() else {"import_ok": False, "error": "inspection impossible (voir Blender)"}


def _verdict(rep, c):
    issues = []
    if not rep.get("import_ok"):
        issues.append("import impossible")
    if rep.get("faces", 0) > int(c["limits"].get("max_external_faces", 150000)):
        issues.append(f"trop lourd : {rep['faces']} faces")
    if rep.get("missing_textures"):
        issues.append(f"textures manquantes : {rep['missing_textures'][:3]}")
    if rep.get("armatures"):
        issues.append("contient une armature : le moteur ne l'anime pas (objet statique uniquement)")
    return issues


def cmd_asset_inspect(a):
    rep = _inspect(Path(a.file).resolve(), a.target_height)
    rep["issues"] = _verdict(rep, cfg())
    out(rep)
    return 0 if rep.get("import_ok") else 1


def cmd_asset_add(a):
    """Ajoute un modèle 3D externe à la bibliothèque après contrôle de licence et inspection. Ne télécharge rien."""
    import shutil as _sh
    src = Path(a.file).resolve()
    if src.suffix.lower() not in (".glb", ".gltf", ".obj"):
        sys.exit("formats acceptés : .glb (recommandé), .gltf, .obj")
    if a.license not in LICENSE_OK and not a.commercial_confirmed:
        sys.exit(f"licence {a.license} non reconnue comme compatible usage commercial ({sorted(LICENSE_OK)}). "
                 "Vérifiez la licence puis relancez avec --commercial-confirmed si elle l'autorise.")
    if a.license.startswith("CC-BY") and not a.attribution:
        sys.exit("licence CC-BY : --attribution obligatoire (crédit à afficher)")
    name = a.name.strip().lower().replace(" ", "_")
    dst_dir = ROOT / "assets" / "library" / "external" / name
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"model{src.suffix.lower()}"
    _sh.copy2(src, dst)
    if src.suffix.lower() == ".gltf":   # fichiers .bin / textures voisins
        for f in src.parent.iterdir():
            if f.suffix.lower() in (".bin", ".png", ".jpg", ".jpeg", ".webp", ".ktx2"):
                _sh.copy2(f, dst_dir / f.name)
    rep = _inspect(dst, a.target_height)
    issues = _verdict(rep, cfg())
    meta = {"name": name, "file": str(dst.relative_to(ROOT / "assets")), "sha256": sha256_file(dst), "added_at": now(),
            "license": {"spdx": a.license, "commercial_use": True, "attribution": a.attribution or "", "source_url": a.source_url or ""},
            "target_height": a.target_height or None, "inspection": rep, "issues": issues, "status": "rejected" if issues and not a.force else "ok"}
    write_json(dst_dir / "asset.json", meta)
    if rep.get("thumbnail") and Path(rep["thumbnail"]).exists():
        _sh.copy2(rep["thumbnail"], dst_dir / "thumbnail.png")
    snippet = {"id": f"pr_{name}"[:35], "type": "custom", "source": "external", "external_path": meta["file"],
               "target_height": a.target_height or rep.get("dimensions_m", [0, 0, 1])[2], "license": meta["license"]}
    out({"status": meta["status"], "issues": issues, "inspection": {k: rep.get(k) for k in ("faces", "materials", "textures", "dimensions_m", "armatures")},
         "thumbnail": str(dst_dir / "thumbnail.png"), "asset_manifest_prop": snippet})
    return 1 if meta["status"] == "rejected" else 0


def cmd_tts_test(a):
    """Synthétise une phrase avec le moteur de voix configuré (pour écouter avant de produire un épisode)."""
    from . import tts as _tts
    c = cfg()
    backend = a.backend or _tts.pick_backend(c)
    out_p = Path(a.out).resolve()
    vcfg = {"piper_model": a.model} if a.model else {}
    if a.speaker is not None:
        vcfg["piper_speaker"] = a.speaker
    desc = _tts.synth(backend, c, a.text, out_p, {"id": "l000", "delivery": {"emotion": a.emotion}}, vcfg)
    out({"backend": backend, "voice": desc.get("voice"), "fichier": str(out_p), "licence": desc.get("license")})


def next_summary(p):
    """Ce qu'il reste à faire pour un épisode (pilote, tableau de bord)."""
    st = State(p)
    st.refresh()
    ready = st.ready()
    blocked = [n for n in STAGES if st.st(n)["status"] == "needs_review"]
    failed = {n: st.st(n).get("error") for n in ready if st.st(n)["status"] == "failed"}
    res = {"done": st.st("delivery")["status"] == "completed",
           "auto": [r for r in ready if STAGES[r][1] == "auto"],
           "agent": [{"stage": r, "owner": STAGES[r][0], "outputs": STAGES[r][3]} for r in ready if STAGES[r][1] == "agent"],
           "review": [{"stage": r, "owner": STAGES[r][0]} for r in ready if STAGES[r][1] == "review"],
           "gates_human": [r for r in ready if STAGES[r][1] == "gate" and r in human_gates()],
           "gates_auto": [r for r in ready if STAGES[r][1] == "gate" and r not in human_gates()],
           "failed": failed, "needs_review": blocked,
           "fingerprint": sha256_json({n: (st.st(n)["status"], st.st(n).get("attempts", 0)) for n in STAGES})}
    return res


def cmd_next(a):
    """Résumé machine de ce qu'il reste à faire (utilisé par scripts/pilote.py)."""
    print(json.dumps(next_summary(ep_path(a.episode)), ensure_ascii=False))


def cmd_produire(a):
    """Production complète en arrière-plan (Windows, macOS, Linux) : crée l'épisode si besoin puis lance le pilote."""
    from . import launcher
    src = Path(a.source)
    if src.is_file():
        ep = a.nom or launcher.slug(src.name)
        if episode_dir(cfg(), ep).exists():
            print(f"L'épisode {ep} existe déjà : reprise là où il s'est arrêté.")
        else:
            ok, txt = launcher.create_episode(ep, src.read_text(encoding="utf-8"), mode="libre" if a.libre else "script",
                                              duration=a.duree, inbox_name=src.name if src.parent != episode_dir(cfg(), "_inbox") else None,
                                              voice_file=a.voix)
            print(txt.strip())
            if not ok:
                return 1
    else:
        ep = src.name
        if not episode_dir(cfg(), ep).exists():
            sys.exit(f"ni fichier, ni épisode existant : {a.source}")
        if a.voix:
            launcher.attach_full_voice(ep, src_path=a.voix)
            print(f"Voix complète remplacée : {a.voix} (la voix et les plans seront recalés)")
    if not cfg()["quality"].get("autonomous"):
        print("ATTENTION : mode autonome désactivé -> la production s'arrêtera à chaque validation humaine.")
    if not launcher.codex_path():
        print("ATTENTION : Codex introuvable -> seules les étapes automatiques tourneront (installer Codex puis `codex login`).")
    try:
        pid = launcher.start_pilot(ep, a.modele or "")
    except RuntimeError as e:
        sys.exit(str(e))
    print(f"Production lancée en arrière-plan : {ep} (pid {pid})")
    print(f"  Suivre      : scripts/studio dashboard   (ou le journal {launcher.journal(ep)})")
    print(f"  Avancement  : scripts/studio status {ep}")
    print(f"  Arrêter     : scripts/studio arreter {ep}")
    return 0


def cmd_arreter(a):
    from . import launcher
    ep_path(a.episode)
    print("arrêté" if launcher.stop_pilot(a.episode) else "aucune production en cours pour cet épisode")


def cmd_dashboard(a):
    from . import dashboard
    dashboard.serve(port=a.port, open_browser=not a.no_browser)


def cmd_retry(a):
    """Remet une étape arrêtée (needs_review/failed/interrupted) en attente. Action HUMAINE (reprise après escalade)."""
    p = ep_path(a.episode)
    st = State(p)
    s_ = st.st(a.stage)
    s_["status"] = "pending"
    if a.reset_rounds:
        s_["revision_rounds"] = 0
    st.log("retry", stage=a.stage, by="human")
    st.save()
    print(f"{a.stage} remise en attente (tours de correction : {s_.get('revision_rounds', 0)}).")


def build_parser():
    ap = argparse.ArgumentParser(prog="studio", description="Studio TikTok 3D : pipeline déterministe")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor", help="diagnostic matériel/logiciel").set_defaults(fn=cmd_doctor)
    x = sp.add_parser("new", help="créer un épisode")
    x.add_argument("episode")
    x.add_argument("--story")
    x.add_argument("--story-file")
    x.add_argument("--script-file", help="script IMPOSÉ (texte verrouillé, une réplique par ligne, 'Prénom: texte')")
    x.add_argument("--duration", type=float, default=None, help="défaut : 90 s, ou estimée depuis le script imposé")
    x.add_argument("--kind", default="original_user_story", choices=["original_user_story", "idea", "reddit_style_paraphrase", "other"])
    x.add_argument("--stop-after", default="prototype", choices=["script", "storyboard", "lookdev", "prototype", "first_cut", "final"])
    x.set_defaults(fn=cmd_new)
    for name, fn in (("validate", cmd_validate), ("status", cmd_status), ("voice", cmd_voice), ("compile", cmd_compile), ("final", cmd_final)):
        x = sp.add_parser(name)
        x.add_argument("episode")
        if name == "validate":
            x.add_argument("--only", default="")
        if name in ("voice", "compile"):
            x.add_argument("--force", action="store_true")
        x.set_defaults(fn=fn)
    x = sp.add_parser("run", help="exécute les étapes automatiques prêtes jusqu'à une étape agent/revue/gate")
    x.add_argument("episode")
    x.add_argument("--until", default="")
    x.set_defaults(fn=cmd_run)
    x = sp.add_parser("submit", help="valider et enregistrer le livrable d'un agent ou d'un critique")
    x.add_argument("episode")
    x.add_argument("stage")
    x.add_argument("--review", action="append")
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=cmd_submit)
    x = sp.add_parser("approve", help="validation d'une gate (HUMAIN, terminal interactif)")
    x.add_argument("episode")
    x.add_argument("gate")
    x.add_argument("--by", default="human")
    x.add_argument("--note", default="")
    x.add_argument("--override", action="store_true")
    x.set_defaults(fn=cmd_approve)
    for name, fn, prof in (("lookdev", cmd_lookdev, "preview"), ("check-shots", cmd_check_shots, "draft"), ("first-cut", cmd_first_cut, None)):
        x = sp.add_parser(name)
        x.add_argument("episode")
        x.add_argument("--profile", default=prof)
        x.add_argument("--force", action="store_true")
        x.set_defaults(fn=fn)
    x = sp.add_parser("prototype")
    x.add_argument("episode")
    x.add_argument("--shots", default="")
    x.add_argument("--seconds", type=float, default=8.0)
    x.add_argument("--profile", default=None)
    x.add_argument("--force", action="store_true")
    x.set_defaults(fn=cmd_prototype)
    x = sp.add_parser("render", help="rendu de travail hors DAG")
    x.add_argument("episode")
    x.add_argument("--shots", default="")
    x.add_argument("--profile", default="draft")
    x.add_argument("--out", default="renders/work.mp4")
    x.set_defaults(fn=cmd_render)
    x = sp.add_parser("qa")
    x.add_argument("episode")
    x.add_argument("video")
    x.add_argument("--width", type=int, default=1080)
    x.add_argument("--height", type=int, default=1920)
    x.add_argument("--write", default="")
    x.set_defaults(fn=cmd_qa)
    x = sp.add_parser("frames", help="frames horodatées + planche contact pour inspection visuelle")
    x.add_argument("episode")
    x.add_argument("video")
    x.add_argument("--at", default="")
    x.add_argument("--every", type=float, default=1.0)
    x.add_argument("--per-shot", action="store_true")
    x.add_argument("--relative", action="store_true", help="vidéo partielle commençant au premier plan")
    x.set_defaults(fn=cmd_frames)
    x = sp.add_parser("inject", help="injecter un défaut pour tester la détection")
    x.add_argument("episode")
    x.add_argument("--defect", required=True)
    x.add_argument("--video", default="renders/prototype.mp4")
    x.add_argument("--shot", default="sh_002")
    x.set_defaults(fn=cmd_inject)
    x = sp.add_parser("produire", help="production complète en arrière-plan (fichier .txt ou épisode existant)")
    x.add_argument("source", help="fichier .txt (script imposé, ou histoire avec --libre) ou nom d'épisode à reprendre")
    x.add_argument("--libre", action="store_true", help="le fichier est une histoire brute : Codex écrit le script")
    x.add_argument("--nom")
    x.add_argument("--duree", type=int)
    x.add_argument("--modele", default="")
    x.add_argument("--voix", help="voix COMPLÈTE déjà enregistrée (ElevenLabs, .mp3/.wav…) : tout se cale dessus")
    x.set_defaults(fn=cmd_produire)
    x = sp.add_parser("arreter", help="arrêter la production en cours d'un épisode (pilote + rendus)")
    x.add_argument("episode")
    x.set_defaults(fn=cmd_arreter)
    x = sp.add_parser("dashboard", help="tableau de bord local dans le navigateur (http://127.0.0.1:8765)")
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--no-browser", action="store_true")
    x.set_defaults(fn=cmd_dashboard)
    x = sp.add_parser("motion-suggest", help="moments propices au motion design repérés dans le script")
    x.add_argument("episode")
    x.set_defaults(fn=cmd_motion_suggest)
    x = sp.add_parser("motion-preview", help="planche de contrôle du motion design (sans rendu 3D)")
    x.add_argument("episode")
    x.set_defaults(fn=cmd_motion_preview)
    x = sp.add_parser("kits", help="galerie de rendu de tous les décors (contrôle visuel)")
    x.add_argument("--kits", default="")
    x.add_argument("--profile", default="draft")
    x.set_defaults(fn=cmd_kits)
    x = sp.add_parser("asset-inspect", help="inspecter un modèle 3D externe (géométrie, textures, vignette)")
    x.add_argument("file")
    x.add_argument("--target-height", type=float, default=0.0)
    x.set_defaults(fn=cmd_asset_inspect)
    x = sp.add_parser("asset-add", help="ajouter un modèle 3D externe à la bibliothèque (licence + inspection)")
    x.add_argument("file")
    x.add_argument("--name", required=True)
    x.add_argument("--license", required=True, help="identifiant SPDX : CC0-1.0, CC-BY-4.0, MIT…")
    x.add_argument("--attribution", default="")
    x.add_argument("--source-url", default="")
    x.add_argument("--target-height", type=float, default=0.0)
    x.add_argument("--commercial-confirmed", action="store_true")
    x.add_argument("--force", action="store_true", help="accepter malgré les problèmes d'inspection")
    x.set_defaults(fn=cmd_asset_add)
    x = sp.add_parser("tts-test", help="écouter la voix configurée sur une phrase")
    x.add_argument("--text", default="Mon coloc a essayé de rendre notre grille-pain célèbre sur TikTok.")
    x.add_argument("--out", default="test_voix.wav")
    x.add_argument("--backend", default="")
    x.add_argument("--model", default="", help="chemin relatif au dépôt d'un modèle .onnx (sinon celui de la config)")
    x.add_argument("--speaker", type=int, default=None)
    x.add_argument("--emotion", default="neutral")
    x.set_defaults(fn=cmd_tts_test)
    x = sp.add_parser("retry", help="remettre une étape arrêtée en attente (humain)")
    x.add_argument("episode")
    x.add_argument("stage")
    x.add_argument("--reset-rounds", action="store_true")
    x.set_defaults(fn=cmd_retry)
    x = sp.add_parser("next", help="ce qu'il reste à faire (JSON, pour le pilote)")
    x.add_argument("episode")
    x.set_defaults(fn=cmd_next)
    x = sp.add_parser("cache")
    x.add_argument("--prune", action="store_true")
    x.set_defaults(fn=cmd_cache)
    x = sp.add_parser("memory")
    x.add_argument("action", choices=["search", "add", "merge"])
    x.add_argument("terms", nargs="*")
    x.add_argument("--limit", type=int, default=5)
    x.add_argument("--category", default="lessons")
    x.add_argument("--title", default="")
    x.add_argument("--text", default="")
    x.add_argument("--tags", default="")
    x.add_argument("--episode", default=None)
    x.set_defaults(fn=cmd_memory)
    x = sp.add_parser("cost", help="journaliser une dépense (crédits TTS externe, GPU loué…)")
    x.add_argument("episode")
    x.add_argument("--kind", required=True)
    x.add_argument("--amount", type=float, required=True)
    x.add_argument("--unit", required=True)
    x.add_argument("--note", default="")
    x.set_defaults(fn=cmd_cost)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    rc = a.fn(a)
    sys.exit(rc or 0)
