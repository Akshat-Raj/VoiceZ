# SIH Voice Agent

A minimal LiveKit voice agent using OpenAI for speech recognition and reasoning,
Sarvam AI for speech synthesis, and Silero for voice activity detection.

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in the required values in `.env`. Download the Silero model once:

```bash
uv run python src/agent.py download-files
```

Run the agent locally without a LiveKit project:

```bash
uv run python src/agent.py console
```

Run the agent with a LiveKit frontend or telephony integration:

```bash
uv run python src/agent.py dev
```

Run the focused checks:

```bash
uv run pytest
```
