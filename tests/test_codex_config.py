"""Tests B et C (statiques) — la configuration Codex respecte les formats vérifiés dans le code source officiel.

Les règles reproduisent codex-rs/agent-roles/src/agent_role_config.rs (fichiers de rôle) et le validateur
officiel du skill-creator (frontmatter SKILL.md). La découverte effective par Codex se vérifie en exécution
(voir README §Vérifier Codex) : ces tests ne la remplacent pas.
"""
import json
import re
import tomllib

import pytest
import yaml
from jsonschema import Draft7Validator

from conftest import ROOT

SCHEMA = json.loads((ROOT / "references/codex/config.schema.json").read_text())
CONFIG_KEYS = set(SCHEMA["properties"])
EXPECTED_ROLES = {"motion-designer", "story-architect", "script-critic", "director", "character-artist", "environment-artist", "animator",
                  "voice-sound", "pipeline-engineer", "continuity-auditor", "visual-critic", "retention-editor"}


def test_project_config_matches_official_schema():
    cfg = tomllib.loads((ROOT / ".codex/config.toml").read_text())
    errs = [e.message for e in Draft7Validator(SCHEMA).iter_errors(cfg)]
    assert errs == []
    assert cfg["sandbox_mode"] != "danger-full-access"
    assert cfg["agents"]["max_concurrent_threads_per_session"] >= 1


@pytest.mark.parametrize("path", sorted((ROOT / ".codex/agents").glob("*.toml")), ids=lambda p: p.stem)
def test_agent_role_file(path):
    d = tomllib.loads(path.read_text())
    assert d.get("name", "").strip() == path.stem
    assert d.get("description", "").strip(), "description non vide"
    assert d.get("developer_instructions", "").strip(), "developer_instructions obligatoire"
    nick = d.get("nickname_candidates")
    if nick is not None:
        assert nick and len(set(nick)) == len(nick)
        assert all(re.fullmatch(r"[A-Za-z0-9 _-]+", n.strip()) for n in nick)
    rest = {k: v for k, v in d.items() if k not in ("name", "description", "nickname_candidates")}
    unknown = set(rest) - CONFIG_KEYS
    assert not unknown, f"clés inconnues (deny_unknown_fields) : {unknown}"
    assert [e.message for e in Draft7Validator(SCHEMA).iter_errors(rest)] == []
    if "model_reasoning_effort" in rest:
        assert rest["model_reasoning_effort"] in ("low", "medium", "high")
    instr = rest["developer_instructions"]
    assert "MISSION" in instr
    if path.stem in ("script-critic", "visual-critic", "continuity-auditor", "retention-editor"):
        assert "ecture seule" in instr, "un critique doit être explicitement en lecture seule"
    assert "studio approve" not in instr, "aucun agent ne valide une gate humaine"


def test_all_roles_present():
    assert {p.stem for p in (ROOT / ".codex/agents").glob("*.toml")} == EXPECTED_ROLES


def _frontmatter(p):
    t = p.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    assert m, f"frontmatter manquant : {p}"
    return yaml.safe_load(m.group(1)), t[m.end():]


@pytest.mark.parametrize("path", sorted((ROOT / ".agents/skills").glob("*/SKILL.md")), ids=lambda p: p.parent.name)
def test_skill_files(path):
    fm, body = _frontmatter(path)
    assert set(fm) <= {"name", "description", "license", "allowed-tools", "metadata"}
    assert fm["name"] == path.parent.name and re.fullmatch(r"[a-z0-9-]{1,64}", fm["name"])
    assert 20 < len(fm["description"]) <= 1024
    assert len(body.split()) < 900, "SKILL.md doit rester court (détails en references/)"
    meta = path.parent / "agents" / "openai.yaml"
    if meta.exists():
        y = yaml.safe_load(meta.read_text())
        assert set(y) <= {"interface", "dependencies", "policy"}
        dp = y.get("interface", {}).get("default_prompt", "")
        assert f"${fm['name']}" in dp


def test_main_skill_exists_and_references_resolve():
    p = ROOT / ".agents/skills/tiktok-3d-studio/SKILL.md"
    _, body = _frontmatter(p)
    for ref in re.findall(r"`((?:references|schemas)/[\w./-]+\.(?:md|json))`", body + (ROOT / "AGENTS.md").read_text()):
        assert (ROOT / ref).exists(), ref


def test_agents_md_size():
    assert len((ROOT / "AGENTS.md").read_bytes()) < 32768
