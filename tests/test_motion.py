from leronx.assets.motion import motion_prompt


def test_motion_prompt_asks_for_animation():
    prompt = motion_prompt("The Future of AI", "A doctor watches a hologram.", "wide")
    assert "Animated movie shot" in prompt
    assert "character motion" in prompt
    assert "no text on screen" in prompt
    assert "A doctor watches a hologram" in prompt
