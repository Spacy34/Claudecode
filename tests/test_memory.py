"""Mémoire : les leçons apprises sur une machine vont dans memory/local (ignoré par git) ; fusion sans perte ni doublon."""
import shutil

from studio import memory
from studio.util import load_config


def test_add_local_and_merge(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    shutil.copytree(memory.ROOT / "memory", mem, ignore=shutil.ignore_patterns("local"))
    monkeypatch.setenv("STUDIO_PATHS_MEMORY_DIR", str(mem))
    cfg = load_config()
    p = memory.add(cfg, "lessons", "Leçon VPS", "texte", ["vps"])
    assert p.parent.name == "local"
    assert "Leçon VPS" in [e["title"] for e in memory.search(cfg, ["vps"], limit=10)]
    modified = tmp_path / "lessons.md"
    modified.write_text((mem / "lessons.md").read_text(encoding="utf-8") + "\n## Leçon écrite par Codex\ntags: x\n\ncorps\n", encoding="utf-8")
    _, added = memory.merge_file(cfg, modified)
    assert added == ["Leçon écrite par Codex"]
    _, again = memory.merge_file(cfg, modified)
    assert again == []
