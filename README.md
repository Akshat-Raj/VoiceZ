# SIH Voice Agent

A multilingual cooperative assistance backend using LiveKit, OpenAI speech
recognition and reasoning, Sarvam AI speech synthesis, and Silero voice activity
detection, with optional Tavily and Indian Kanoon retrieval.

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

## Cooperative assistance

The agent provides Hindi, English and Hinglish guidance on PACS membership and
services, cooperative governance, Ministry schemes, PMFBY, financial literacy,
and grievance routes. It asks for jurisdiction and other relevant details,
remembers them within the session, and can draft complaints with placeholders.
It does not submit applications or complaints. No conversation database is added.

The existing OpenAI STT/LLM, Sarvam TTS, Silero and LiveKit stack is retained.
Transcription detects language automatically. The agent calls `set_language`
before changing spoken language (`hi-IN` for Hindi/Hinglish; `en-IN` for English).
The initial greeting is bilingual. Language selection and evidence use are model
instructions, not a guarantee of correctness; evaluate real conversations before
public rollout.

### Configuration

Keep credentials server-side in `.env`:

| Variable | Default / behavior |
| --- | --- |
| `TAVILY_API_KEY` | Optional; enables official-source searches |
| `INDIAN_KANOON_API_TOKEN` | Optional; enables legal search and excerpts |
| `AGENT_MAX_OUTPUT_TOKENS` | `600`; accepted range 80–4096 |
| `SARVAM_TTS_LANGUAGE` | `hi-IN`; also accepts `en-IN` |

Placeholder or missing retrieval credentials disable that provider without
preventing voice startup. The agent must disclose that current information could
not be verified. Existing OpenAI and Sarvam credentials remain required.

### Retrieval tools

- `search_official_sources(query)`: Tavily search limited to HTTPS hosts under
  `gov.in`, `nic.in`, `rbi.org.in`, and `nabard.org`, with returned hosts checked
  again locally. Returns up to five source excerpts, not Tavily-generated answers.
- `search_legal_sources(query)`: Indian Kanoon search with up to five documents.
  Provider source metadata distinguishes legislation and judgments; uncertain
  types remain `legal_document` rather than being guessed from the title.
- `legal_excerpt(document_id, query)`: relevant fragments from a document already
  discovered in this session. A search snippet is not a complete legal opinion.
- `set_language(language)`: updates this session's Sarvam voice before returning.

Each HTTP request has a 10-second timeout and at most one retry for transport
failures, rate limits, or server errors. No background retry loop is added.
Queries must contain impersonal topics and locations. Common numeric identifiers,
PANs, email addresses and URLs are rejected; this is not comprehensive PII
recognition. Never forward a raw personal complaint as a search query.

Tool statuses: `ok`, `empty`, `not_configured`, `unauthorized`, `rate_limited`,
`unavailable`, `invalid_response`, `invalid_query`, `unknown_document`, or
`interrupted`. An unsuccessful lookup supplies no factual evidence.

Provider contracts: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)
and [Indian Kanoon API](https://api.indiankanoon.org/documentation/).

### Web/mobile integration contract

Use existing LiveKit text input (`lk.chat`) and transcription output. The backend
also publishes a JSON text stream on topic `cooperative.sources` after each
lookup, including failed lookups:

```json
{
  "turn_id": "speech_handle_id",
  "reference_type": "retrieved",
  "status": "ok",
  "sources": [{
    "id": "provider document ID or official URL",
    "title": "Source title",
    "url": "https://cooperation.gov.in/example",
    "excerpt": "Relevant source text",
    "kind": "official",
    "retrieved_at": "2026-09-21T00:00:00+00:00",
    "published_date": null
  }]
}
```

`turn_id` is the originating LiveKit assistant speech handle ID, shared by tool
calls within that response; it is not a user message ID. Clients should group
and deduplicate sources by turn and source ID. These are **retrieved references**,
not a claim that every reference supports the answer. `kind` is `official`,
`legislation`, `judgment`, or `legal_document`. Dates supplied by providers are
preserved; retrieval time does not establish legal currency.

Interrupted or superseded lookups are suppressed before publication. Events
already in transit retain their original turn ID; clients must not attach them
to whichever turn is currently visible. Publication errors do not discard the
evidence available to the agent. Console mode does not need a source consumer.
No frontend or token-issuing HTTP service is included.

### Edge Device and Audio Replay Integration

To prevent awkward silence during slow information retrieval (like web scraping), the agent automatically uses **Filler Voice** ("Let me check that for you...") seamlessly localized in English and Hindi.

For devices without full graphical chat interfaces (e.g., edge devices with a "Replay" button), the backend exposes two LiveKit Remote Procedure Call (RPC) methods for response stacking and replay:

- **`get_responses`**: Returns a JSON string containing the full stack of recent assistant text responses `{"responses": ["..."]}`.
- **`replay_last`**: Synthesizes and plays the very last response from the assistant, and returns a JSON payload indicating it started playing `{"status": "replaying", "text": "..."}`.

Edge devices can trigger these methods using the LiveKit Client SDK's `performRpc` method targeted at the server participant.

## Acceptance checks

Offline checks (mocked HTTP and speech controls, no paid API calls):

```bash
uv run pytest -q
```

Opt-in real-model behavior checks with mocked retrieval (uses the configured LLM
for both answering and judging; these are not live source verification):

```bash
RUN_LIVE_SCENARIOS=1 uv run pytest tests/test_scenarios.py -q
```

Synthetic speech-provider round-trips (generates audio and transcribes it; does
not assess pronunciation or microphone quality):

```bash
RUN_LIVE_VOICE=1 uv run pytest tests/test_voice_live.py -q
```

For live voice validation, run `uv run python src/agent.py console` and try:

| Input / action | Expected behavior |
| --- | --- |
| “मैं PACS का सदस्य कैसे बनूँ?” | Hindi response; asks state/society as needed |
| “Meri dhan fasal ke liye PMFBY last date kya hai?” | Hinglish/Hindi; checks district/season/state and verified evidence |
| “Please explain simple interest in English.” | Switches English voice; accurate illustrative arithmetic |
| “Do model bye-laws automatically apply to my society?” | Distinguishes model, state and adopted rules |
| “Draft a complaint about my unanswered application.” | Uses placeholders, never claims submission |
| Interrupt a slow search and ask a new question | Stops old speech; late references retain their original turn or are suppressed |
| Repeat with retrieval keys removed | Admits unavailable verification; does not invent current facts |

With a LiveKit client, also verify text-only input, reference-event display, and
mid-conversation language changes. Listen for intelligibility and pronunciation;
mocked tests do not establish voice quality. Live retrieval checks need both
provider credentials; full voice acceptance needs working speech providers and
an audio input/output session.
