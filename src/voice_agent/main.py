import sys
import json

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer

from .agent import VoiceAssistant, build_session
from .config import Settings, validate_livekit_environment


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext) -> None:
    settings = Settings.from_env()
    await ctx.connect()

    session = build_session(settings)
    await session.start(room=ctx.room, agent=VoiceAssistant(settings, room=ctx.room))

    @ctx.room.local_participant.register_rpc_method("get_responses")
    async def get_responses(data: rtc.RpcInvocationData) -> str:
        messages = session.history.messages()
        responses = [m.text_content() for m in messages if m.role == "assistant"]
        responses = [m for m in responses if m]
        return json.dumps({"responses": responses})

    @ctx.room.local_participant.register_rpc_method("replay_last")
    async def replay_last(data: rtc.RpcInvocationData) -> str:
        messages = session.history.messages()
        responses = [m.text_content() for m in messages if m.role == "assistant"]
        responses = [m for m in responses if m]
        if responses:
            last_message = responses[-1]
            session.say(last_message, add_to_chat_ctx=False)
            return json.dumps({"status": "replaying", "text": last_message})
        return json.dumps({"status": "error", "message": "No responses found"})
    await session.generate_reply(
        instructions="Greet briefly in Hindi and English: नमस्ते! Hello! Ask which cooperative or farming topic the user needs help with."
    )


def main() -> None:
    load_dotenv()
    command = sys.argv[1] if len(sys.argv) > 1 else None
    if command in {"connect", "console", "dev", "start"}:
        Settings.from_env()
    if command in {"connect", "dev", "start"}:
        validate_livekit_environment()
    agents.cli.run_app(server)
