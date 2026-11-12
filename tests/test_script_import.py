"""Script imposé par l'utilisateur : import fidèle, verrouillage, habillage obligatoire."""
import json

import pytest

from studio import contracts, script_import

SAMPLE = """# mon script
Ma voisine élève une poule qui s'appelle Bernadette.
Bernadette: Cot cot !
Un jour, elle m'a dit : cette poule va devenir maire.
Narrateur: Et le pire, c'est qu'elle a gagné.
Maire Bernadette: Première mesure ? Plus de nuggets.
"""


def test_parse_speakers_and_normalization():
    lines, chars = script_import.parse(SAMPLE)
    assert [l["speaker"] for l in lines] == ["narrator", "ch_bernadette", "narrator", "narrator", "ch_maire_bernadette"]
    assert lines[1]["text"] == "Cot cot!"                      # ponctuation recollée (ancrages par mot)
    assert lines[2]["text"].startswith("Un jour, elle m'a dit:")   # « dit : » reste de la narration
    assert lines[4]["text"] == "Première mesure? Plus de nuggets."
    assert chars == {"ch_bernadette": "Bernadette", "ch_maire_bernadette": "Maire Bernadette"}


def test_long_line_split_without_losing_words():
    long = " ".join(["Une phrase plutôt longue pour tester la découpe automatique."] * 8)
    lines, _ = script_import.parse(long + "\nFin.")
    assert all(len(l["text"]) <= 240 for l in lines)
    assert " ".join(l["text"] for l in lines[:-1]).split() == long.split()


def test_new_with_script_file_locks_and_requires_dressing(tmp_path, episode):
    from studio import cli
    f = tmp_path / "script.txt"
    f.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        cli.main(["new", "ep_poule_maire", "--script-file", str(f)])
    assert e.value.code == 0
    ep = episode.parent / "ep_poule_maire"
    brief = json.loads((ep / "episode_brief.json").read_text())
    assert brief["source_kind"] == "user_script" and len(brief["script_lock"]["lines"]) == 5
    assert contracts.schema_errors("episode_brief", brief) == []
    sc = json.loads((ep / "story_script.json").read_text())
    assert contracts.schema_errors("story_script", sc) == []
    arts = {"episode_brief": brief, "story_script": sc}
    errs = contracts.cross_errors(arts)
    assert any("visual_intent encore à définir" in x for x in errs), "squelette non habillé = refusé"
    # habillage par le story-architect (texte inchangé) -> accepté
    sc["title"], sc["logline"] = "La poule maire", "Une poule est élue maire et interdit les nuggets."
    for b in sc["beats"]:
        b["summary"] = "ok"
    sc["content_review"]["notes"] = "humour absurde, aucun risque"
    for l in sc["lines"]:
        l["visual_intent"] = "La poule Bernadette au centre, très fière."
    assert contracts.cross_errors({"episode_brief": brief, "story_script": sc}) == []
    # modification du texte imposé -> refusée
    sc["lines"][1]["text"] = "Cot cot cot!"
    assert any("IMPOSÉ" in x for x in contracts.cross_errors({"episode_brief": brief, "story_script": sc}))
