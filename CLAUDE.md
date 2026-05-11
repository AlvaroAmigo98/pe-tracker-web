# pe-tracker-web — Architecture & Agent Guide

## What this repo does

Django web app that displays PE firm headcount changes (hires, leavers, promotions) scraped by `pe-scraper`. It is a **read-mostly** app — it does not write to the DB except through the superuser admin views.

The database is managed externally in Supabase. There are **no Django migrations** (`managed=False` on all models). Schema changes must be applied directly in Supabase SQL editor.

---

## Data flow

```
pe-scraper (weekly)  →  Supabase  →  pe-tracker-web (reads & displays)
```

The scraper writes to `person_snapshot` and `change_event`. This app reads those tables and renders them.

---

## Key models (`tracker/models.py`)

All models use `managed=False` — Django never creates or migrates these tables.

| Model | Table | Description |
|---|---|---|
| `Company` | `company` | PE firms, has a `bucket` field (UK / DACH / France / etc.) |
| `Person` | `person` | Individual tracked, linked to Company |
| `PersonSnapshot` | `person_snapshot` | One row per person per scrape date (title, seniority, team, location) |
| `ChangeEvent` | `change_event` | Detected changes: hire / leaver / promotion / role_change |
| `ScrapeRun` | `scrape_run` | Metadata per weekly run (totals, firms_ok, firms_failed) |
| `ScrapeRunFirm` | `scrape_run_firm` | Per-firm result per run (row_count, status, error_msg) |
| `AuditLog` | `audit_log` | Login events for security audit trail |

`ScrapeRunFirm.status` values: `ok` | `empty` | `below_threshold` | `error`

---

## Key business logic (`tracker/views.py`)

Three inference functions classify snapshot data at query time (not stored):

- `infer_region(location)` — maps office location string → `EMEA` / `North America` / `APAC` / `Unknown`
- `infer_seniority_group(seniority)` → `Senior` (Partner/MD, Director, VP) or `Junior`
- `infer_function_web(title)` → `Buyout / PE` / `Credit / Debt` / `Infrastructure` / `Operations` / `Advisory` / etc.

These run in Python after DB fetch, not in SQL. That means filtering by region/function/group happens **after** the queryset is evaluated.

---

## Access control

- `@login_required` — all main views
- `@_superuser_required` — scrape_logs, user_admin
- `RateLimitedLoginView` — locks IP after 5 failed attempts for 1 hour (uses Django cache)
- `AuditLog` — records every LOGIN, LOGOUT, LOGIN_FAILED with IP

---

## Database connection

- **Host:** `aws-1-eu-west-2.pooler.supabase.com`
- **Port:** `6543` (transaction pooler — never use 5432)
- **Auth:** `SUPABASE_DB_PASSWORD` or `DB_PASSWORD` env var (settings.py tries both)
- **SSL:** required + `gssencmode=disable` + `channel_binding=disable`

---

## Deployment (Railway)

- Auto-deploys on every push to `main` (~2 min)
- URL: `pe-tracker-web-production.up.railway.app`
- Env vars in Railway dashboard: `DB_PASSWORD`, `SUPABASE_DB_PASSWORD`, `SECRET_KEY`, `DEBUG=False`
- **Never commit `.env`**. **Never set `DEBUG=True` in Railway.**

```bash
git add <specific files>
git commit -m "description"
git push   # triggers Railway deploy
```

---

## Templates

All templates extend `tracker/base.html`. Key template variables:

- `bucket_filter` — active geographic bucket (UK / DACH / France / etc.), used for nav highlighting and query scoping
- `companies` — Company queryset, filtered to bucket if active
- `latest_run` — most recent ScrapeRun, shown in nav bar

---

## URL structure summary

```
/                     landing (public)
/dashboard/           main change event feed + filters
/people/              latest snapshot per person
/firms/               firm list with activity indicators
/firms/<id>/          firm detail (team + events)
/firms/<id>/report/   printable firm report
/signals/             cascade alerts + trend chart
/search/              full-text search
/scrape-logs/         superuser — weekly run status table
/users/               superuser — user management + audit log
/profile/             current user settings + login history
/api/search/          JSON autocomplete endpoint
```

---

## Running tests

```bash
python manage.py test tracker.tests
```

Tests use SQLite in-memory — no Supabase connection required. Covers: rate limiting, session cookies, CSP headers, access control, CSRF, audit logging, deployment settings.

---

## Common gotchas

1. **Port 6543, not 5432.** Supabase transaction pooler only. Using 5432 will silently hang.
2. **`managed=False` on all models.** Never run `makemigrations` expecting it to touch the real schema.
3. **In-Python filtering.** Region/function/seniority filters apply after DB fetch. For large result sets, consider pushing more filters into the ORM queryset.
4. **`DISTINCT ON` requires PostgreSQL.** The `_get_latest_snapshots_qs()` helper uses it. SQLite (used in tests) does not support it — don't call it in tests.
5. **Bucket scoping.** When `bucket_filter` is active, company/event queries are scoped via `_bucket_company_ids()`. Always pass it through to keep filters consistent.
