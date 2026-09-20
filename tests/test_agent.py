import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from voice_agent.agent import VoiceAssistant
from voice_agent.config import Settings
from voice_agent.prompts import COOPERATIVE_INSTRUCTIONS


def assistant(room=None):
    return VoiceAssistant(Settings('llm', 'stt', 'tts', 'hi-IN', 'speaker', COOPERATIVE_INSTRUCTIONS), room=room)


def context():
    return SimpleNamespace(speech_handle=SimpleNamespace(id='turn-1', interrupted=False),
                           session=SimpleNamespace(tts=Mock()))


def test_tools_registered():
    assert {t.info.name for t in assistant().tools} == {
        'search_official_sources', 'search_legal_sources', 'legal_excerpt', 'set_language'}


def test_language_updates_tts_before_return():
    agent, ctx = assistant(), context()
    for language in ['en-IN', 'hi-IN']:
        assert asyncio.run(agent.set_language(ctx, language))['language'] == language
        ctx.session.tts.update_options.assert_called_with(target_language_code=language)
    assert asyncio.run(agent.set_language(ctx, 'xx'))['status'] == 'unsupported_language'
    ctx.speech_handle.interrupted = True
    assert asyncio.run(agent.set_language(ctx, 'en-IN'))['status'] == 'interrupted'
    assert agent.language == 'hi-IN'


def test_reference_contract_and_console():
    room = SimpleNamespace(isconnected=lambda: True,
                           local_participant=SimpleNamespace(send_text=AsyncMock()))
    agent = assistant(room)
    operation = AsyncMock(return_value={'status': 'ok', 'sources': [{'id': 'source'}]})
    payload = asyncio.run(agent._lookup(context(), operation, 'PACS'))
    sent = room.local_participant.send_text.call_args
    assert sent.kwargs['topic'] == 'cooperative.sources'
    assert json.loads(sent.args[0]) == payload
    assert payload['turn_id'] == 'turn-1' and payload['reference_type'] == 'retrieved'
    assert asyncio.run(assistant()._lookup(context(), operation, 'PACS'))['status'] == 'ok'


def test_interruption_and_new_turn_suppress_late_results():
    async def scenario(new_turn):
        room = SimpleNamespace(isconnected=lambda: True,
                               local_participant=SimpleNamespace(send_text=AsyncMock()))
        agent, ctx = assistant(room), context()
        async def operation(query):
            if new_turn:
                await agent.on_user_turn_completed(None, None)
            else:
                ctx.speech_handle.interrupted = True
            return {'status': 'ok', 'sources': [{'id': 'old'}]}
        assert (await agent._lookup(ctx, operation, 'PACS'))['status'] == 'interrupted'
        room.local_participant.send_text.assert_not_called()
    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_reference_transport_failure_does_not_lose_evidence():
    room = SimpleNamespace(isconnected=lambda: True,
                           local_participant=SimpleNamespace(send_text=AsyncMock(side_effect=RuntimeError)))
    operation = AsyncMock(return_value={'status': 'ok', 'sources': [{'id': 'source'}]})
    payload = asyncio.run(assistant(room)._lookup(context(), operation, 'PACS'))
    assert payload['sources'] and payload['delivery_status'] == 'failed'


def test_agent_session_state_is_not_shared():
    first, second = assistant(), assistant()
    asyncio.run(first.on_user_turn_completed(None, None))
    assert second._generation == 0
    assert first.retrieval is not second.retrieval
