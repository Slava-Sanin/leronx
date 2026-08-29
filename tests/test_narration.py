from leronx.script.narration import extract_narration, extract_spoken_blocks
from leronx.assets.matcher import AssetMatcher


def test_extract_narration_strips_tags():
    script = "[HOOK]\nHello world.\n\n[BODY]\n[Scene 1: 0s-10s]\nMore words."
    assert extract_narration(script) == "Hello world. More words."


def test_spoken_blocks_keep_order():
    script = "[HOOK]\nFirst.\n\n[CTA]\nLast."
    assert extract_spoken_blocks(script) == ["First.", "Last."]


def test_keywords_include_cyrillic():
    words = AssetMatcher().extract_keywords("Будущее искусственного интеллекта в медицине")
    assert "будущее" in words or "интеллекта" in words or "медицине" in words
