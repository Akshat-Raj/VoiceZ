from dataclasses import dataclass
import os

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required agent configuration is missing."""


def _validate_environment(names: tuple[str, ...]) -> None:
    missing = [
        name
        for name in names
        if not (value := os.getenv(name, "").strip())
        or "your-" in value
        or value.startswith("<")
    ]
    if missing:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def validate_livekit_environment() -> None:
    _validate_environment(
        ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    )


@dataclass(frozen=True, slots=True)
class Settings:
    llm_model: str
    stt_model: str
    tts_model: str
    tts_language: str
    tts_speaker: str
    instructions: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        _validate_environment(("OPENAI_API_KEY", "SARVAM_API_KEY"))

        return cls(
            llm_model=os.getenv("OPENAI_LLM_MODEL", "gpt-5.6-luna"),
            stt_model=os.getenv("OPENAI_STT_MODEL", "gpt-live-transcribe"),
            tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            tts_language=os.getenv("SARVAM_TTS_LANGUAGE", "en-IN"),
            tts_speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
            instructions=(
                "You are a helpful voice assistant. Answer naturally in one or two "
                "short sentences, normally under 30 words."
            ),
        )
