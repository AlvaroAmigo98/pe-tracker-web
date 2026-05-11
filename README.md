# pe-tracker-web

Django dashboard for tracking PE firm headcount changes (hires, leavers, promotions). Data comes from the [pe-scraper](https://github.com/AlvaroAmigo98/pe-scraper) pipeline which writes to a shared Supabase PostgreSQL database.

**Live app:** `pe-tracker-web-production.up.railway.app`

---

## Stack

- **Backend:** Django 6, Gunicorn, psycopg3
- **Frontend:** WhiteNoise (static files), openpyxl (Excel export)
- **Database:** Supabase PostgreSQL (managed externally — no Django migrations)
- **Hosting:** Railway (auto-deploys on push to main)

---

## Repository structure

```
petracker/
  settings.py         Django settings — reads DB_PASSWORD / SUPABASE_DB_PASSWORD from env
  urls.py             Root URL config

tracker/
  models.py           DB-first models (managed=False): Company, Person, PersonSnapshot,
                      ChangeEvent, ScrapeRun, ScrapeRunFirm, AuditLog
  views.py            All view functions + business logic (infer_region, infer_function, etc.)
  urls.py             App URL patterns
  middleware.py       SecurityHeadersMiddleware (CSP, Referrer-Policy, Permissions-Policy)
  tests.py            Security test suite (rate limiting, CSP, access control, CSRF, audit logging)
  templates/tracker/  HTML templates

manage.py             Django management CLI
Procfile              Railway: web: gunicorn petracker.wsgi
requirements.txt      Python deps
runtime.txt           Python version for Railway
```

---

## Views & URLs

| URL | View | Access |
|---|---|---|
| `/` | `landing` | Public |
| `/dashboard/` | `dashboard` | Login required |
| `/people/` | `people` | Login required |
| `/firms/` | `firms` | Login required |
| `/firms/<id>/` | `firm_detail` | Login required |
| `/firms/<id>/report/` | `firm_report` | Login required |
| `/signals/` | `signals` | Login required |
| `/search/` | `search` | Login required |
| `/scrape-logs/` | `scrape_logs` | Superuser only |
| `/users/` | `user_admin` | Superuser only |
| `/profile/` | `profile` | Login required |

---

## Deployment

Railway auto-deploys on every push to `main`:

```bash
git add tracker/views.py tracker/templates/tracker/dashboard.html
git commit -m "describe change"
git push   # Railway redeploys in ~2 min
```

**Never set `DEBUG=True` in Railway.** Env vars are managed in the Railway dashboard.

---

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

Create `.env` with:
```
DB_PASSWORD=your_supabase_password
SECRET_KEY=any-local-key
DEBUG=True
```

Run: `python manage.py runserver`

---

## Running tests

```bash
python manage.py test tracker.tests
```

Tests run against an in-memory SQLite DB (no Supabase connection needed). Covers: rate limiting, session cookies, security headers, CSP, access control, CSRF, audit logging.
