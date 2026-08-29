from leronx.assets.imagine import visual_prompt


def test_visual_prompt_forbids_typography():
    prompt = visual_prompt("The Future of AI", "Hospitals change overnight.", "wide", "animation")
    assert "no text" in prompt
    assert "title card" in prompt
    assert "animated feature" in prompt
    assert "Hospitals change overnight" in prompt


def test_visual_prompt_uses_shot():
    prompt = visual_prompt("AI", "A doctor looks at a glowing chart.", "closeup")
    assert "close-up" in prompt
