# O! Journey — backend phase 6

## What has been implemented

- `POST /api/plan`: structured travel discovery from an arbitrary natural-language request. Extracts interests in Russian, ranks diverse destinations, takes group composition, likes/dislikes, novelty mode, budget and dates into account. Never invents bookable prices.
- `POST /api/itinerary/check`: validates ordering and overlaps of activities, transit buffer, and missing source for a claimed verified tariff.
- Existing `/api/weather/{destination_id}` and `/api/quote` remain available.
- `POST /api/plan?use_llm=true`: optional OpenAI-compatible parsing assistance if `OPENAI_API_KEY` is provided. **The model does not provide prices or real bookability**; the deterministic engine produces scenario records.

### Example request

```bash
curl -X POST http://127.0.0.1:8001/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"message":"Мы вдвоём студенты. Хотим города с архитектурой и необычной едой, а не горы. До 45000 рублей на человека", "origin":"Санкт-Петербург", "days":5, "travelers":[{"student":true},{"student":true}], "novelty":"new"}'
```

### Optional LLM mode

```bash
export OPENAI_API_KEY='...'
# Optional model override:
export OPENAI_MODEL='gpt-4.1-mini'
```

**Never commit secrets.** Current LLM use is an experimental intent parsing call, not a real tool-using travel agent. No provider APIs for real hotel inventory, flights or activities have been linked. `/api/plan` returns unquoted discovery results and explicit `needed_for_verification` until those integrations are implemented.

### Next API integrations to finish before claiming competition readiness

1. Hotels: contracted/authorized inventory feed with accommodation offers for exact dates, number of guests, room type, cancellation, currency, timestamp. Without API access use clearly labeled demo inventory.
2. Transport: ticketing/search data, including schedule, origin and end-to-end transfers.
3. Places and activities: operator price/availability, source URL and hours, student conditions verified per traveler.
4. Geography/routing: geocoding plus route matrix for realistic transfer minutes.
5. Trip state: Supabase/PostgreSQL persistence of traveler feedback, trips, and selected offers; draft bookings and explicit confirmation.
6. Weather: query forecast for trip date, climate statistics for dates outside forecast window; fail closed when weather sources are unavailable.
7. Observability: log tool outputs and source timestamps for reproducible evaluations; no private documents or API keys in logs.

## Quality bar

Never label an itinerary 'bookable' until dates, transport, accommodation and activity availability have been checked; never reduce prices based on unverified benefits. Present a verification-needed status instead of fabricating a checkout total.
