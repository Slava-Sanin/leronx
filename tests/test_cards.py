from pathlib import Path

from leronx.assets.cards import render_title_card


def test_title_card_writes_png(tmp_path: Path):
    dest = tmp_path / "card.png"
    render_title_card("The future of AI", dest, resolution=(640, 360), index=0, kicker="Scene 1")
    assert dest.exists()
    assert dest.stat().st_size > 500
