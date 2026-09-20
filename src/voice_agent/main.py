import sys

from dotenv import load_dotenv
from livekit import agents
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
