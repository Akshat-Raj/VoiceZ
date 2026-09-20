import json
from typing import Literal

from livekit.agents import Agent, AgentSession, RunContext, function_tool
from livekit.plugins import openai, sarvam, silero
from openai.types import Reasoning

from .config import Settings
from .retrieval import Retrieval


class VoiceAssistant(Agent):
    def __init__(self, settings: Settings, *, room=None, retrieval=None) -> None:
        super().__init__(instructions=settings.instructions)
        self.retrieval = retrieval or Retrieval(
            settings.tavily_api_key, settings.indian_kanoon_api_token
        )
        self.room = room
        self.language = settings.tts_language
        self._generation = 0

    async def on_user_turn_completed(self, turn_ctx, new_message):
        self._generation += 1

    async def _lookup(self, context, operation, *args):
        generation = self._generation
        handle = context.speech_handle
        if handle.interrupted:
            return {"status": "interrupted", "sources": []}
        try:
            payload = await operation(*args)
        except ValueError:
            payload = {"status": "invalid_query", "sources": []}
        if handle.interrupted or generation != self._generation:
            return {"status": "interrupted", "sources": []}
        event = {"turn_id": handle.id, "reference_type": "retrieved", **payload}
        if self.room is not None and self.room.isconnected():
            try:
                await self.room.local_participant.send_text(
                    json.dumps(event, ensure_ascii=False), topic="cooperative.sources"
                )
            except Exception:
                # Reference transport failure must not discard evidence for the answer.
                # Cancellation is intentionally not caught (CancelledError is BaseException).
                event["delivery_status"] = "failed"
        return event

    @function_tool
    async def search_official_sources(self, context: RunContext, query: str) -> dict:
        """Find official evidence for schemes, PACS, PMFBY, laws or contacts.

        Use an impersonal topic/location query; never include personal identifiers.
        """
        return await self._lookup(context, self.retrieval.official, query)

    @function_tool
    async def search_legal_sources(self, context: RunContext, query: str) -> dict:
        """Search Indian Kanoon for laws and judgments, specifying jurisdiction.

        Use only generic legal issues and location, never personal case details.
        """
        return await self._lookup(context, self.retrieval.legal, query)

    @function_tool
    async def legal_excerpt(self, context: RunContext, document_id: str, query: str) -> dict:
        """Get relevant passages from a document found by search_legal_sources.

        Query must contain generic legal terms, not personal identifiers.
        """
        return await self._lookup(context, self.retrieval.excerpt, document_id, query)

    @function_tool
    async def set_language(self, context: RunContext, language: Literal["hi-IN", "en-IN"]) -> dict:
        """Set speech language BEFORE answering: hi-IN for Hindi/Hinglish, en-IN for English."""
        if context.speech_handle.interrupted:
            return {"status": "interrupted"}
        if language not in {"hi-IN", "en-IN"}:
            return {"status": "unsupported_language"}
        context.session.tts.update_options(target_language_code=language)
        self.language = language
        return {"status": "ok", "language": language}


def build_session(settings: Settings) -> AgentSession:
    vad = silero.VAD.load(min_silence_duration=0.3)

    return AgentSession(
        llm=openai.responses.LLM(
            model=settings.llm_model,
            reasoning=Reasoning(effort="none"),
            verbosity="low",
            max_output_tokens=settings.max_output_tokens,
        ),
        stt=openai.STT(
            model=settings.stt_model,
            detect_language=True,
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
