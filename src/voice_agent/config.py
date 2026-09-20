from dataclasses import dataclass
import os

from dotenv import load_dotenv

from .prompts import COOPERATIVE_INSTRUCTIONS


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
    max_output_tokens: int = 600
    tavily_api_key: str | None = None
    indian_kanoon_api_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        _validate_environment(("OPENAI_API_KEY", "SARVAM_API_KEY"))

        try:
            max_tokens = int(os.getenv("AGENT_MAX_OUTPUT_TOKENS", "600"))
            if not 80 <= max_tokens <= 4096:
                raise ValueError
        except ValueError:
            raise ConfigurationError("AGENT_MAX_OUTPUT_TOKENS must be between 80 and 4096") from None
        language = os.getenv("SARVAM_TTS_LANGUAGE", "hi-IN")
        if language not in {"hi-IN", "en-IN"}:
            raise ConfigurationError("SARVAM_TTS_LANGUAGE must be hi-IN or en-IN")

        return cls(
            llm_model=os.getenv("OPENAI_LLM_MODEL", "gpt-5.6-luna"),
            stt_model=os.getenv("OPENAI_STT_MODEL", "gpt-live-transcribe"),
            tts_model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
            tts_language=language,
            tts_speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
            instructions=COOPERATIVE_INSTRUCTIONS,
            max_output_tokens=max_tokens,
            tavily_api_key=_optional_key("TAVILY_API_KEY"),
            indian_kanoon_api_token=_optional_key("INDIAN_KANOON_API_TOKEN"),
        )


def _optional_key(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value if value and "your-" not in value and not value.startswith("<") else None
