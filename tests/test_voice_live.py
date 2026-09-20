"""Synthetic speech round-trips; these do not replace listening with a microphone."""
import asyncio
import os

import pytest
from livekit import rtc
from livekit.agents import stt
from livekit.agents.utils import http_context

from voice_agent.agent import build_session
from voice_agent.config import Settings

pytestmark = pytest.mark.skipif(os.getenv('RUN_LIVE_VOICE') != '1',
                                reason='Opt-in speech provider smoke test')


@pytest.mark.parametrize('language,text', [
    ('hi-IN', 'नमस्ते, मुझे खेती की जानकारी चाहिए।'),
    ('en-IN', 'Hello, I need help with crop insurance.'),
    ('hi-IN', 'मुझे crop insurance के बारे में बताइए।'),
])
def test_synthetic_speech_roundtrip(language, text, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    async def exercise():
        async with http_context.open():
            session = build_session(Settings.from_env())
            try:
                session.tts.update_options(target_language_code=language)
                async with session.tts.synthesize(text) as synthesis:
                    frames = [chunk.frame async for chunk in synthesis]
                assert frames, 'TTS returned no audio'
                async with session.stt.stream() as recognition:
                    for frame in frames:
                        recognition.push_frame(frame)
                    # Local VAD needs a trailing silence to commit the synthetic utterance.
                    frame = frames[-1]
                    recognition.push_frame(rtc.AudioFrame(
                        data=bytes(frame.sample_rate * frame.num_channels * 2),
                        sample_rate=frame.sample_rate, num_channels=frame.num_channels,
                        samples_per_channel=frame.sample_rate))
                    recognition.end_input()
                    transcript = ""
                    async for event in recognition:
                        if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT and event.alternatives:
                            transcript = event.alternatives[0].text
                            break  # Realtime streams stay open after their final transcript.
                assert transcript.strip(), 'STT returned no final transcript'
            finally:
                await session.stt.aclose()
                await session.tts.aclose()
                await session.llm.aclose()
    asyncio.run(asyncio.wait_for(exercise(), timeout=45))
