import pytest

from voice_agent.config import ConfigurationError, Settings


def test_missing_required_environment_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required = ("OPENAI_API_KEY", "SARVAM_API_KEY")
    for name in required:
        monkeypatch.setenv(name, f"your-{name.lower()}")

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_env()


def test_model_overrides_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "LIVEKIT_URL": "wss://example.livekit.cloud",
        "LIVEKIT_API_KEY": "key",
        "LIVEKIT_API_SECRET": "secret",
        "OPENAI_API_KEY": "openai",
        "SARVAM_API_KEY": "sarvam",
        "OPENAI_LLM_MODEL": "test-llm",
        "OPENAI_STT_MODEL": "test-stt",
        "SARVAM_TTS_MODEL": "test-tts",
        "SARVAM_TTS_LANGUAGE": "hi-IN",
        "SARVAM_TTS_SPEAKER": "test-speaker",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = Settings.from_env()

    assert (
        settings.llm_model,
        settings.stt_model,
        settings.tts_model,
        settings.tts_language,
        settings.tts_speaker,
    ) == (
        "test-llm",
        "test-stt",
        "test-tts",
        "hi-IN",
        "test-speaker",
    )


def test_retrieval_and_token_settings(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setenv('SARVAM_API_KEY', 'test')
    monkeypatch.setenv('TAVILY_API_KEY', 'your-placeholder')
    monkeypatch.setenv('INDIAN_KANOON_API_TOKEN', 'token')
    monkeypatch.setenv('AGENT_MAX_OUTPUT_TOKENS', '600')
    assert Settings.from_env().tavily_api_key is None
    assert Settings.from_env().indian_kanoon_api_token == 'token'
    assert Settings.from_env().max_output_tokens == 600


@pytest.mark.parametrize('value', ['0', 'abc', '4097'])
def test_bad_token_budget(monkeypatch, value):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setenv('SARVAM_API_KEY', 'test')
    monkeypatch.setenv('AGENT_MAX_OUTPUT_TOKENS', value)
    with pytest.raises(ConfigurationError, match='AGENT_MAX_OUTPUT_TOKENS'):
        Settings.from_env()
