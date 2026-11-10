import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "blender"))
DEMO = ROOT / "episodes" / "ep_demo_grillepain"
CREATIVE = ["episode_brief.json", "story_script.json", "cast_bible.json", "asset_manifest.json", "storyboard.json", "animation_plan.json"]


def has_blender():
    return bool(os.environ.get("BLENDER_BIN") or shutil.which("blender") or importlib.util.find_spec("bpy"))


@pytest.fixture
def episode(tmp_path, monkeypatch):
    """Copie isolée de l'épisode de démonstration (artefacts créatifs seulement)."""
    eps = tmp_path / "episodes"
    ep = eps / "ep_demo_grillepain"
    ep.mkdir(parents=True)
    for f in CREATIVE:
        shutil.copy(DEMO / f, ep / f)
    monkeypatch.setenv("STUDIO_PATHS_EPISODES_DIR", str(eps))
    monkeypatch.setenv("STUDIO_PATHS_CACHE_DIR", str(tmp_path / "cache"))
    import studio.cli as cli
    cli.CFG = None
    return ep


@pytest.fixture
def cfg(episode):
    from studio.util import load_config
    return load_config()
