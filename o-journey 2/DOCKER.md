# Local Docker setup — O! Journey

From the `o-journey 2` folder, with Docker Desktop running:

```bash
docker compose up --build
```

Frontend: http://localhost:5188
Backend health: http://localhost:8001/api/health

Stop: `Ctrl+C`, or `docker compose down` in another terminal.

The React development server proxies `/api` to the backend container.
For optional LLM intent extraction, copy `.env.example` to `.env`, set `OPENAI_API_KEY`, and never commit `.env`.

The interactive My World atlas bundles country polygons locally, so that part does not fetch map tiles. City search, weather, lodging, and route calculation still require working internet providers.

This stack is a LOCAL DEVELOPMENT configuration. It uses Vite dev server, not a hardened production frontend.
