# O! Journey — local development and handoff

## Requirements
- Docker Desktop running
- Ollama installed on the Mac/host with `qwen3:4b`
- A StayAPI key if hotel prices are to be queried (separate credentials permitted by provider)

## Setup
From the repository folder `o-journey 2`:

```bash
cp .env.example .env
ollama pull qwen3:4b
docker compose up --build -d
docker compose ps
```

Edit `.env` with your own StayAPI key. The frontend and backend containers read the latest local settings after recreation.

On macOS, Ollama runs outside Docker and backend calls `http://host.docker.internal:11434`.

## Addresses
- React frontend: http://localhost:5188
- API Swagger: http://localhost:8001/docs
- Backend health: http://localhost:8001/api/health
- Provider diagnostics: http://localhost:8001/api/agent/diagnostics
- Real LLM completion test: http://localhost:8001/api/agent/self-test
- Hotel search: `GET /api/hotels/search?city=Almaty&checkin=2026-12-01&checkout=2026-12-04&adults=2&rooms=1&currency=USD` — consumes provider credits.
- Agent discovery: `POST /api/agent/inspect` JSON with `message`, `origin`, `days`, `travelers`, `citizenship` and optionally `budget_per_person`, `departure_date`, `is_student`.

## Troubleshooting
```bash
docker compose ps -a
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
```

If a code update was pulled:
```bash
git pull origin main
docker compose up --build -d --force-recreate
```

Do not use `0.0.0.0` as the browser URL. Do not commit `.env`, send keys in chat, or expose port 11434 publicly.

## What works / still needs implementation
- Ollama local intent parsing is tested; this is *not* an autonomous multi-tool agent.
- StayAPI returns dated hotel offers when key is valid; price may exclude final fees and availability can change.
- Open-Meteo weather / geocoding and OpenStreetMap place discovery are available subject to upstream service limits.
- Transport fares are **not** verified live. Travelpayouts token, if configured, provides cached flight observations.
- Visa decisions, carrier-specific student/pensioner discounts and end-to-end confirmed package budgets **are not implemented**.
- Saved map data is local browser storage.
- The old root `index.html` is not the active React frontend; use port 5188.

## Working on different laptops
Each developer clones GitHub repository, runs their *own* Docker/Ollama instance, and has their own permitted StayAPI credentials. GitHub synchronizes code only; it does not sync secrets, Ollama model files, or browser localStorage. A real shared remote backend requires a separate deployment and authentication. Coordinate branches/PRs to avoid overwriting `main`.
