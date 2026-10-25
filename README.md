# Expense Tracker REST API (Task 2: Debugging & Enhancement)

A small FastAPI service for recording expenses (in-memory storage). This submission fixes the original bugs, adds input validation, consistent error handling with correct HTTP status codes, and an automated test suite.

## Setup and run

Requires Python 3.10 or newer.

**Windows (Command Prompt)**
```bat
py -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

## Run the tests

```bash
python -m pytest -v
```

Run it from the project folder (the one containing `main.py`).

### Test results

All 41 tests pass:

 [test_results.txt](test_results.txt)

## API

| Method | Path | Success | Description |
|---|---|---|---|
| GET | `/` | 200 | Health check |
| GET | `/expenses?category=food` | 200 | List expenses; optional case-insensitive category filter |
| GET | `/expenses/summary` | 200 | `{"count": n, "total_amount": sum}` |
| GET | `/expenses/{id}` | 200 | One expense |
| POST | `/expenses` | 201 | Create an expense |
| PUT | `/expenses/{id}` | 200 | Partial update (send only the fields to change) |
| DELETE | `/expenses/{id}` | 204 | Delete an expense (no body) |

Example create:
```bash
curl -X POST http://127.0.0.1:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{"description":"Coffee","amount":12.5,"category":"Food","expense_date":"2026-10-03"}'
```

## Bugs found and fixed

| # | Bug | Why it was wrong | Fix |
|---|---|---|---|
| 1 | `/expenses/summary` returned `len(expenses)` as `total_amount` | It reported the count, not money (two expenses of 450 and 180 gave `2`, not `630.0`) | Sum the `amount` values, rounded to 2 decimals |
| 2 | Amount was an unchecked float | Negative, zero, huge or infinite amounts were accepted | `0 < amount <= 1,000,000,000`, NaN/Infinity rejected, stored with 2 decimals |
| 3 | `expense_date` was a plain string | `"hello"` was accepted and stored | Must match strict `YYYY-MM-DD` and be a real calendar date (the date is kept as a string) |
| 4 | Category filter was case-sensitive | `?category=food` returned nothing for `Food` | Compare case-insensitively, ignoring surrounding spaces |
| 5 | PUT accepted `null` values | `{"description": null}` silently wiped the field (and `{"expense_date": null}` would crash the date validator with a 500) | `null` is rejected with 400 |
| 6 | PUT skipped create-time rules | Negative amounts and invalid dates could be set through update; an empty body returned 200 | Update uses the same field rules; empty body returns 400 |
| 7 | Empty or whitespace-only text accepted | `"   "` was a valid description or category | Whitespace trimmed, 1-200 chars (description), 1-50 chars (category) |
| 8 | DELETE returned 200 with a message | REST convention for a delete with nothing to return is 204 | Returns 204 with no body |
| 9 | No handling for unexpected errors; inconsistent error shapes | A crash returned a raw 500, and errors had different formats | Exception handlers, one JSON error shape, details logged server side only |

## Validation rules

- `description`: required, trimmed, 1-200 characters
- `category`: required, trimmed, 1-50 characters
- `amount`: required, number greater than 0 and at most 1,000,000,000, no NaN/Infinity
- `expense_date`: required, strict `YYYY-MM-DD` and a real calendar date (`2026-13-45`, `2026-1-5`, `20261001` are rejected)
- Unknown fields are rejected (catches typos such as `amout`)
- PUT: at least one field required, and no field may be `null`

## Error handling

All errors share one JSON shape.

| Situation | Status | Body |
|---|---|---|
| Invalid body, query or path value | 400 | `{"error": "Validation failed", "details": ["amount: Input should be greater than 0"]}` |
| Expense not found / unknown route | 404 | `{"error": "Expense not found"}` |
| Method not allowed | 405 | `{"error": "Method Not Allowed"}` |
| Unexpected server error | 500 | `{"error": "Internal server error"}` (traceback is logged, never returned) |

## Assumptions and notes

- **400 instead of FastAPI's default 422** for validation errors, to match the "correct HTTP status codes" requirement. This is done in one exception handler.
- Future-dated expenses are allowed (e.g. planned expenses). A "not in the future" rule would be a one-line addition to `validate_expense_date`.
- A regex enforces strict `YYYY-MM-DD` because `date.fromisoformat` alone accepts other formats on Python 3.11+ (e.g. `2026-W40-1`).
- For PUT, `null` values and an empty body are rejected in the endpoint itself (simple `if` checks), because `null` would otherwise wipe stored data.
- Money is a `float` rounded to 2 decimals, which is fine for this scope. For a real system I would use `Decimal` or integer cents.
- Storage is an in-memory dict, so data resets on restart and concurrent writes are not synchronized. A real deployment would use a database (which also generates ids safely).
- The `/expenses/summary` route is intentionally declared before `/expenses/{expense_id}`, otherwise "summary" would be parsed as an id.
- PUT does partial updates (as in the original code) rather than requiring a full replacement.

## Possible improvements

- Persistent database and migrations
- Pagination and date-range filtering on `GET /expenses`
- Authentication
- Switch to `Decimal` for money