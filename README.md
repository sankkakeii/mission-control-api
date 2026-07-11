# Mission Control API

FastAPI backend for the Mission Control earthquake response demo.

## Run

```bash
uv sync --extra dev
uv run uvicorn mission_control_api.main:app --reload
```

### Enable the LLM

Set the following environment variables for live agent reasoning:

```bash
FIREWORKS_API_KEY=...
GEMMA_ENDPOINT=...
```

If `GEMMA_ENDPOINT` is set, the backend routes agent calls to the AMD MI300X / vLLM path using Gemma. Otherwise it uses Fireworks with the Gemma model. When neither is present, the backend falls back to deterministic responses for local development and tests.

## Test

```bash
uv run pytest
```
