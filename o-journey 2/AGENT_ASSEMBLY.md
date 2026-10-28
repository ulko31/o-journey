# O! Journey — agent assembly

## What this iteration actually implements
- `POST /api/agent/assemble` accepts city, exact check-in/out, travelers, rooms, target currency and optional per-person budget.
- Calls existing StayAPI adapter **once**, only on explicit action. This spends real provider credits.
- Filters unavailable / non-numeric offers and sorts remaining offers by quoted amount.
- Budget comparisons are allowed only when provider and budget currencies match. Otherwise result is `null`.
- Price basis is NOT verified as complete stay total; full-trip total is `null`. This deliberately prevents fabricated totals and discounts.
- Tests mock the external provider, so do not spend credits.

## Example
```bash
curl -X POST http://localhost:8001/api/agent/assemble \
-H 'Content-Type: application/json' \
-d '{"city":"Istanbul","checkin":"2026-12-01","checkout":"2026-12-04","travelers":2,"rooms":1,"currency":"USD","budget_per_person":500,"budget_currency":"USD"}'
```

## Check before merge
```bash
python -m pytest -q tests/test_assembly.py
docker compose up --build -d
curl http://localhost:8001/api/health
```

## Next critical integration
Connect explicit "Compare hotels" button in React to `/api/agent/assemble`; do not call automatically per keystroke. Verify upstream StayAPI price semantics, taxes, rooms, and final booking link before any automatic total. Expand the agent to invoke the weather and POI tools and present a structured list of missing transport/activity quotes. Live airfare, transit fares, visa decisions and verified discounts remain unavailable.
