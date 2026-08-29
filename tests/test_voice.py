"""Tests for TTS and emotion mapping."""
from leronx.voice.tts_base import TTSEngine, DummyTTS, resolve_voice
from leronx.voice.emotions import Emotion, EmotionMapper

class TestEmotionMapper:
    def test_professional_maps_to_serious(self):
        assert EmotionMapper().map_tone("professional").emotion == Emotion.SERIOUS

class TestTTSEngine:
    def test_dummy_returns_none(self):
        assert DummyTTS().synthesize("test") is None


class TestResolveVoice:
    def test_short_name(self):
        assert resolve_voice("dmitry") == "ru-RU-DmitryNeural"

    def test_full_name_passthrough(self):
        assert resolve_voice("en-US-GuyNeural") == "en-US-GuyNeural"

    def test_empty_is_auto(self):
        assert resolve_voice(None) is None
        assert resolve_voice("") is None
