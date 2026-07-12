# Multi-LLM Router with Automatic Failover

Calls 6 free LLM APIs (Google Gemini, Groq, Cerebras, OpenRouter, NVIDIA NIM,
Cloudflare Workers AI). If one hits a rate limit or quota error, it
automatically retries on the next provider **with the same conversation
history**, so context is never lost.

## Setup

```bash
cd llm-router
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now open .env and paste your real API keys in
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs — FastAPI gives you a free test UI (Swagger).

## Test with curl

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test1", "message": "hello, who are you?"}'
```

Response looks like:
```json
{
  "reply": "Hi! I'm an AI assistant...",
  "provider_used": "google_gemini",
  "attempts": [{"provider": "google_gemini", "status": "success"}]
}
```

If Gemini were rate-limited, `attempts` would show it failing and Groq
picking up instead — same session_id, full context carried over.

## How the failover works

1. `app/providers.py` — ordered list of your 6 providers + which env
   var holds each key. Reorder this list to change priority.
2. `app/context_store.py` — SQLite file (`sessions.db`) storing full
   message history per `session_id`.
3. `app/router.py` — `call_llm()` loops through providers in order,
   catches rate-limit/auth/other errors, and moves to the next one.
4. `app/main.py` — FastAPI `/chat` endpoint wiring it together.

## Next steps (once this is working)

- Add the "job pipeline" / looping-prompt system (e.g. "write code until
  tests pass") as a separate module that calls `call_llm()` in a loop.
- Add a simple frontend (or connect this API to your existing website).
- Swap SQLite for Postgres if you need multiple users at scale.
- Double check current free-tier rate limits before launch — they
  change often; the model names in `providers.py` may also need
  updating if a provider retires a model.

## Security note

Never commit `.env` to GitHub. Add this to a `.gitignore` file:
```
.env
sessions.db
venv/
__pycache__/
```
# MultillmRouter
