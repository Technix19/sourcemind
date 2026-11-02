# SourceMind

Evidence-first AI document research assistant, built incrementally as a learning and portfolio project.

## Status

| Milestone | State |
|---|---|
| M1 Backend foundation (health endpoint, tests, config) | Implemented |
| M2 Ingestion and chunking | Planned |
| M3 TF-IDF retrieval | Planned |
| M4 Grounded generation | Planned |
| M5 Frontend | Planned |
| M6 Auth, persistence, vectors | Planned |
| M7 Evaluation and deployment | Planned |

Nothing beyond M1 exists yet. No retrieval, uploads, UI or evaluation results.

## Run the API (local)

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/v1/health
```

## Test

```bash
cd apps/api && source .venv/bin/activate
python -m pytest -q
```
