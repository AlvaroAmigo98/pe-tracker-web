from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun
import openpyxl
from openpyxl.styles import Font, PatternFill
from datetime import date, timedelta

# ADD THESE IMPORTS
from collections import defaultdict


SENIORITY_GROUP = {
    "Partner / MD": "Senior",
    "Director":     "Senior",
    "VP":           "Senior",
    "Principal":    "Junior",
    "Associate":    "Junior",
    "Analyst":      "Junior",
    "Other":        "Junior",
    "Unknown":      "Junior",
}

LOCATION_REGIONS = {
    "new york": "North America", "san francisco": "North America",
    "chicago": "North America", "boston": "North America",
    "los angeles": "North America", "houston": "North America",
    "toronto": "North America", "miami": "North America",
    "washington": "North America", "menlo park": "North America",
    "nashville": "North America", "atlanta": "North America",
    "dallas": "North America", "montreal": "North America",
    "united states": "North America", "usa": "North America",
    "canada": "North America",
    "london": "EMEA", "paris": "EMEA", "frankfurt": "EMEA",
    "amsterdam": "EMEA", "madrid": "EMEA", "milan": "EMEA",
    "stockholm": "EMEA", "zurich": "EMEA", "munich": "EMEA",
    "dubai": "EMEA", "abu dhabi": "EMEA", "luxembourg": "EMEA",
    "berlin": "EMEA", "copenhagen": "EMEA", "oslo": "EMEA",
    "helsinki": "EMEA", "warsaw": "EMEA", "vienna": "EMEA",
    "brussels": "EMEA", "dublin": "EMEA", "lisbon": "EMEA",
    "uk": "EMEA", "united kingdom": "EMEA", "germany": "EMEA",
    "france": "EMEA", "sweden": "EMEA", "netherlands": "EMEA",
    "spain": "EMEA", "italy": "EMEA", "switzerland": "EMEA",
    "denmark": "EMEA", "norway": "EMEA", "finland": "EMEA",
    "poland": "EMEA", "austria": "EMEA", "belgium": "EMEA",
    "ireland": "EMEA", "portugal": "EMEA", "middle east": "EMEA",
    "hong kong": "APAC", "singapore": "APAC", "tokyo": "APAC",
    "shanghai": "APAC", "beijing": "APAC", "sydney": "APAC",
    "melbourne": "APAC", "seoul": "APAC", "mumbai": "APAC",
    "bangalore": "APAC", "delhi": "APAC", "taipei": "APAC",
    "china": "APAC", "japan": "APAC", "australia": "APAC",
    "india": "APAC", "south korea": "APAC", "taiwan": "APAC",
}


def infer_region(location: str) -> str:
    if not location or location == "N/A":
        return "Unknown"
    loc = location.lower()
    for keyword, region in LOCATION_REGIONS.items():
        if keyword in loc:
            return region
    return "Unknown"


def infer_seniority_group(seniority: str) -> str:
    return SENIORITY_GROUP.get(seniority, "Junior")


def infer_function_web(title: str) -> str:
    if not title or title == "N/A":
        return "Unknown"
    t = title.lower()

    if any(x in t for x in [
        "human resources", " hr,", " hr ", "talent acquisition",
        "recruiting", "recruitment", "office manager", "facilities",
        "procurement", "events ", "marketing", "communications",
        "public relations", " pr ", "legal counsel", "general counsel",
        "compliance officer", "risk officer", "audit", "tax ",
        "accounting", "treasury", "fund admin", "fund finance",
        "fund operations", "portfolio reporting", "valuations",
        "luxembourg operations", "it support", "cyber",
        "information security", "esg", "sustainability",
        "investor relations", "capital formation",
    ]):
        return "Operations"

    if any(x in t for x in [
        "senior adviser", "senior advisor", "adviser", "advisor",
        "board member", "board director", "chairman", "chairwoman",
        "co-founder", "founding partner", "executive chairman",
        "executive in residence", "entrepreneur in residence",
        "venture partner", "operating partner", "executive advisor",
    ]):
        return "Advisory"

    if any(x in t for x in [
        "buyout", "private equity", " pe ", "leveraged",
        "lbo", "growth equity", "growth capital",
    ]):
        return "Buyout / PE"

    if any(x in t for x in [
        "infrastructure", "infra", "transport", "energy transition",
        "renewable", "utilities", "power",
    ]):
        return "Infrastructure"

    if any(x in t for x in [
        "real estate", "property", "realty", "reit", "real assets",
    ]):
        return "Real Estate"

    if any(x in t for x in [
        "credit", "debt", "lending", "fixed income",
        "distressed", "mezzanine", "direct lending",
        "structured finance", "clo",
    ]):
        return "Credit / Debt"

    if any(x in t for x in [
        "venture", " vc ", "early stage", "seed",
    ]):
        return "Venture Capital"

    if any(x in t for x in [
        "managing director", "director", "partner", "principal",
        "associate", "analyst", "vice president", " vp",
        "head of", "co-head", "investment", "portfolio",
        "deal", "transaction", "m&a", "origination",
        "execution", "coverage", "sector",
    ]):
        return "Investment (General)"

    return "Other"


@login_required
def dashboard(request):
    latest_run       = ScrapeRun.objects.order_by('-ran_at').first()
    companies        = Company.objects.order_by('name')
    company_filter   = request.GET.getlist('company')
    region_filter    = request.GET.getlist('region')
    group_filter     = request.GET.getlist('group')
    function_filter  = request.GET.getlist('function')
    senior_emea_only = request.GET.get('senior_emea', '')
    export           = request.GET.get('export', '')

    # Load ALL historical events, newest first
    events_qs = ChangeEvent.objects.select_related(
        'person', 'person__company'
    ).order_by('-detected_at', '-id')

    events = list(events_qs)

    # Bulk load latest snapshot per person to avoid one query per event
    person_ids = list({e.person_id for e in events})

    latest_snapshots_qs = PersonSnapshot.objects.filter(
        person_id__in=person_ids
    ).select_related('person').order_by('person_id', '-scraped_at', '-id')

    latest_snapshot_by_person = {}
    for snap in latest_snapshots_qs:
        if snap.person_id not in latest_snapshot_by_person:
            latest_snapshot_by_person[snap.person_id] = snap

    # Annotate events
    for e in events:
        latest_snap = latest_snapshot_by_person.get(e.person_id)
        e.region = infer_region(latest_snap.location if latest_snap else '')
        e.function = infer_function_web(e.new_title or e.previous_title or '')
        e.seniority_group = infer_seniority_group(
            latest_snap.seniority if latest_snap else ''
        )

    # Apply filters AFTER enrichment
    if company_filter:
        events = [e for e in events if e.person.company.name in company_filter]

    if region_filter:
        events = [e for e in events if e.region in region_filter]

    if group_filter:
        events = [e for e in events if e.seniority_group in group_filter]

    if function_filter:
        events = [e for e in events if e.function in function_filter]

    if senior_emea_only:
        events = [
            e for e in events
            if e.seniority_group == 'Senior'
            and e.region == 'EMEA'
            and e.function in ('Buyout / PE', 'Investment (General)', 'Advisory')
        ]

    hires = [e for e in events if e.event_type == 'hire']
    leavers = [e for e in events if e.event_type == 'leaver']
    promotions = [e for e in events if e.event_type in ('promotion', 'role_change')]

    # Excel export of CURRENTLY FILTERED dashboard events
    if export == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Historical Changes"

        headers = [
            'Name', 'Company', 'Function', 'Change Type', 'Previous Title',
            'New Title', 'Previous Level', 'New Level', 'Region',
            'Seniority Group', 'Detected At'
        ]

        header_fill = PatternFill(
            start_color="1F3864",
            end_color="1F3864",
            fill_type="solid"
        )
        header_font = Font(bold=True, color="FFFFFF")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font

        widths = {
            1: 28, 2: 24, 3: 22, 4: 18, 5: 32,
            6: 32, 7: 16, 8: 16, 9: 16, 10: 18, 11: 16
        }
        for col_idx, width in widths.items():
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

        for row_num, e in enumerate(events, start=2):
            ws.cell(row=row_num, column=1, value=e.person.full_name)
            ws.cell(row=row_num, column=2, value=e.person.company.name)
            ws.cell(row=row_num, column=3, value=e.function)
            ws.cell(row=row_num, column=4, value=e.event_type)
            ws.cell(row=row_num, column=5, value=e.previous_title or '—')
            ws.cell(row=row_num, column=6, value=e.new_title or '—')
            ws.cell(row=row_num, column=7, value=e.previous_level or '—')
            ws.cell(row=row_num, column=8, value=e.new_level or '—')
            ws.cell(row=row_num, column=9, value=e.region)
            ws.cell(row=row_num, column=10, value=e.seniority_group)
            ws.cell(row=row_num, column=11, value=str(e.detected_at))

        ws.freeze_panes = "A2"

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="historical_changes.xlsx"'
        wb.save(response)
        return response

    return render(request, 'tracker/dashboard.html', {
        'latest_run':       latest_run,
        'companies':        companies,
        'company_filter':   company_filter,
        'region_filter':    region_filter,
        'group_filter':     group_filter,
        'function_filter':  function_filter,
        'senior_emea_only': senior_emea_only,
        'events':           events,
        'hires':            hires,
        'leavers':          leavers,
        'promotions':       promotions,
    })
