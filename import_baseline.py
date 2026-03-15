"""
import_baseline.py
==================
One-time script to load employees_20260310_220437.xlsx into Supabase
as the Week 1 baseline snapshot.

Run:
    .venv/Scripts/Activate.ps1
    python import_baseline.py
"""

import os
import django
import pandas as pd
from datetime import datetime, date

# ── Django setup ─────────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'petracker.settings')
django.setup()

from tracker.models import Company, Person, PersonSnapshot, ScrapeRun

# ── Config ────────────────────────────────────────────────────────────────────
EXCEL_FILE   = 'employees_20260310_220437.xlsx'
SCRAPED_DATE = date(2026, 3, 10)

SENIORITY_MAP = {
    'partner':           'Partner',
    'co-founder':        'Partner',
    'managing partner':  'Partner',
    'managing director': 'Managing Director',
    'md':                'Managing Director',
    'director':          'Director',
    'principal':         'Principal',
    'vice president':    'Vice President',
    'vp':                'Vice President',
    'associate':         'Associate',
    'analyst':           'Analyst',
    'senior advisor':    'Senior Advisor',
    'operating partner': 'Operating Partner',
}

def infer_seniority(title: str) -> str | None:
    if not title or title == 'N/A':
        return None
    t = title.lower()
    for keyword, level in SENIORITY_MAP.items():
        if keyword in t:
            return level
    return None

# ── Load Excel ────────────────────────────────────────────────────────────────
print(f"Loading {EXCEL_FILE}...")
df = pd.read_excel(EXCEL_FILE)
df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
df = df.fillna('')
print(f"  → {len(df):,} rows, {df['firm_name'].nunique()} firms")

# ── Step 1: Create ScrapeRun ──────────────────────────────────────────────────
print("\nStep 1: Creating ScrapeRun entry...")
run = ScrapeRun.objects.create(
    ran_at       = datetime(2026, 3, 10, 22, 4, 37),
    total_rows   = len(df),
    firms_ok     = df['firm_name'].nunique(),
    firms_failed = 0,
)
print(f"  → ScrapeRun id={run.id}")

# ── Step 2: Create Companies ──────────────────────────────────────────────────
print("\nStep 2: Creating companies...")
firm_names = df['firm_name'].unique()
company_map = {}  # name → Company instance

for name in firm_names:
    if not name:
        continue
    obj, created = Company.objects.get_or_create(
        name=name,
        defaults={'created_at': datetime(2026, 3, 10)}
    )
    company_map[name] = obj
    if created:
        print(f"  + {name}")

print(f"  → {len(company_map)} companies ready")

# ── Step 3: Create People + Snapshots ────────────────────────────────────────
print("\nStep 3: Creating people and snapshots...")

created_people    = 0
created_snapshots = 0
skipped           = 0

# Process in batches of 500 for progress visibility
total = len(df)
for i, row in df.iterrows():
    firm_name   = str(row.get('firm_name', '')).strip()
    person_name = str(row.get('person_name', '')).strip()
    position    = str(row.get('person_position', '')).strip() or None
    team        = str(row.get('team', '')).strip() or None
    location    = str(row.get('location', '')).strip() or None

    if not firm_name or not person_name:
        skipped += 1
        continue

    company = company_map.get(firm_name)
    if not company:
        skipped += 1
        continue

    # Get or create Person
    person, p_created = Person.objects.get_or_create(
        full_name=person_name,
        company=company,
        defaults={'first_seen_at': datetime(2026, 3, 10)}
    )
    if p_created:
        created_people += 1

    # Always create a new snapshot (one per scrape date)
    already_exists = PersonSnapshot.objects.filter(
        person=person,
        scraped_at=SCRAPED_DATE
    ).exists()

    if not already_exists:
        PersonSnapshot.objects.create(
            person     = person,
            job_title  = position if position and position != 'N/A' else None,
            seniority  = infer_seniority(position or ''),
            team       = team if team and team != 'N/A' else None,
            location   = location if location and location != 'N/A' else None,
            scraped_at = SCRAPED_DATE,
        )
        created_snapshots += 1

    # Progress every 1000 rows
    if (i + 1) % 1000 == 0:
        print(f"  [{i+1:,}/{total:,}] {created_people} people, {created_snapshots} snapshots...")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"""
════════════════════════════════════════
  IMPORT COMPLETE
════════════════════════════════════════
  Companies   : {len(company_map)}
  People      : {created_people} created
  Snapshots   : {created_snapshots} created
  Skipped     : {skipped} rows
  Scraped date: {SCRAPED_DATE}
════════════════════════════════════════
""")
