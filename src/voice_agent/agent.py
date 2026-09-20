from livekit.agents import Agent, AgentSession
from livekit.plugins import openai, sarvam, silero
from openai.types import Reasoning

from .config import Settings


class VoiceAssistant(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)


def build_session(settings: Settings) -> AgentSession:
    vad = silero.VAD.load(min_silence_duration=0.3)

    return AgentSession(
        llm=openai.responses.LLM(
            model=settings.llm_model,
            reasoning=Reasoning(effort="none"),
            verbosity="low",
            max_output_tokens=80,
        ),
        stt=openai.STT(
            model=settings.stt_model,
            language="en",
            vad=vad,
        ),
        tts=sarvam.TTS(
            model=settings.tts_model,
            target_language_code=settings.tts_language,
            speaker=settings.tts_speaker,
            min_buffer_size=30,
            max_chunk_length=80,
        ),
        vad=vad,
        turn_handling={
            "endpointing": {"min_delay": 0.2, "max_delay": 1.0},
            "preemptive_generation": {"enabled": True},
        },
    )
