from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun
import openpyxl
from openpyxl.styles import Font, PatternFill
from datetime import date, timedelta


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

    # Operations / support — check first to avoid misclassification
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

    # Advisory
    if any(x in t for x in [
        "senior adviser", "senior advisor", "adviser", "advisor",
        "board member", "board director", "chairman", "chairwoman",
        "co-founder", "founding partner", "executive chairman",
        "executive in residence", "entrepreneur in residence",
        "venture partner", "operating partner", "executive advisor",
    ]):
        return "Advisory"

    # Buyout / Private Equity
    if any(x in t for x in [
        "buyout", "private equity", " pe ", "leveraged",
        "lbo", "growth equity", "growth capital",
    ]):
        return "Buyout / PE"

    # Infrastructure
    if any(x in t for x in [
        "infrastructure", "infra", "transport", "energy transition",
        "renewable", "utilities", "power",
    ]):
        return "Infrastructure"

    # Real Estate
    if any(x in t for x in [
        "real estate", "property", "realty", "reit",
        "real assets",
    ]):
        return "Real Estate"

    # Credit / Debt
    if any(x in t for x in [
        "credit", "debt", "lending", "fixed income",
        "distressed", "mezzanine", "direct lending",
        "structured finance", "clo",
    ]):
        return "Credit / Debt"

    # Venture Capital
    if any(x in t for x in [
        "venture", " vc ", "early stage", "seed",
        "series a", "series b",
    ]):
        return "Venture Capital"

    # General investment roles that don't specify a strategy
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
    latest_run     = ScrapeRun.objects.order_by('-ran_at').first()
    companies      = Company.objects.order_by('name')
    company_filter = request.GET.get('company', '')
    region_filter  = request.GET.get('region', '')
    group_filter   = request.GET.get('group', '')
    function_filter = request.GET.get('function', '')
    senior_emea_only = request.GET.get('senior_emea', '')

    events = ChangeEvent.objects.select_related(
        'person', 'person__company'
    ).order_by('-detected_at')

    if company_filter:
        events = events.filter(person__company__name=company_filter)

    events = list(events[:200])

    # Annotate each event with region and function
    for e in events:
        latest_snap = PersonSnapshot.objects.filter(
            person=e.person
        ).order_by('-scraped_at').first()
        e.region   = infer_region(latest_snap.location if latest_snap else '')
        e.function = infer_function_web(
            e.new_title or e.previous_title or ''
        )
        e.seniority_group = infer_seniority_group(
            latest_snap.seniority if latest_snap else ''
        )

    # Apply filters
    if region_filter:
        events = [e for e in events if e.region == region_filter]
    if group_filter:
        events = [e for e in events if e.seniority_group == group_filter]
    if function_filter:
        events = [e for e in events if e.function == function_filter]
    if senior_emea_only:
        events = [e for e in events if
                  e.seniority_group == 'Senior' and
                  e.region == 'EMEA' and
                  e.function in ('Buyout / PE', 'Investment (General)', 'Advisory')]

    hires      = [e for e in events if e.event_type == 'hire']
    leavers    = [e for e in events if e.event_type == 'leaver']
    promotions = [e for e in events if e.event_type in ('promotion', 'role_change')]

    return render(request, 'tracker/dashboard.html', {
        'latest_run':      latest_run,
        'companies':       companies,
        'company_filter':  company_filter,
        'region_filter':   region_filter,
        'group_filter':    group_filter,
        'function_filter': function_filter,
        'senior_emea_only': senior_emea_only,
        'events':          events,
        'hires':           hires,
        'leavers':         leavers,
        'promotions':      promotions,
    })


@login_required
def people(request):
    search           = request.GET.get('q', '')
    company_filter   = request.GET.get('company', '')
    seniority_filter = request.GET.get('seniority', '')
    group_filter     = request.GET.get('group', '')
    region_filter    = request.GET.get('region', '')
    function_filter  = request.GET.get('function', '')
    last_seen_filter = request.GET.get('last_seen', '')
    export           = request.GET.get('export', '')

    companies   = Company.objects.order_by('name')
    seniorities = PersonSnapshot.objects.values_list(
        'seniority', flat=True
    ).distinct().order_by('seniority')

    latest_snapshots = PersonSnapshot.objects.select_related(
        'person', 'person__company'
    ).order_by('person__company__name', 'person__full_name', '-scraped_at')

    seen   = set()
    people = []
    for snap in latest_snapshots:
        pid = snap.person_id
        if pid not in seen:
            seen.add(pid)
            snap.region          = infer_region(snap.location or '')
            snap.seniority_group = infer_seniority_group(snap.seniority or '')
            snap.function        = infer_function_web(snap.job_title or '')
            people.append(snap)

    if search:
        people = [p for p in people if
                  search.lower() in p.person.full_name.lower() or
                  search.lower() in (p.job_title or '').lower()]

    if company_filter:
        people = [p for p in people if p.person.company.name == company_filter]

    if seniority_filter:
        people = [p for p in people if p.seniority == seniority_filter]

    if group_filter:
        people = [p for p in people if p.seniority_group == group_filter]

    if region_filter:
        people = [p for p in people if p.region == region_filter]

    if function_filter:
        people = [p for p in people if p.function == function_filter]

    if last_seen_filter:
        cutoff = date.today() - timedelta(days=int(last_seen_filter))
        people = [p for p in people if p.scraped_at >= cutoff]

    # Excel export
    if export == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PE Tracker Export"

        headers = ['Name', 'Company', 'Title', 'Seniority', 'Group',
                   'Function', 'Region', 'Location', 'Last Seen']
        header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            ws.column_dimensions[cell.column_letter].width = 20

        for row, snap in enumerate(people, 2):
            ws.cell(row=row, column=1, value=snap.person.full_name)
            ws.cell(row=row, column=2, value=snap.person.company.name)
            ws.cell(row=row, column=3, value=snap.job_title or '—')
            ws.cell(row=row, column=4, value=snap.seniority or '—')
            ws.cell(row=row, column=5, value=snap.seniority_group)
            ws.cell(row=row, column=6, value=snap.function)
            ws.cell(row=row, column=7, value=snap.region)
            ws.cell(row=row, column=8, value=snap.location or '—')
            ws.cell(row=row, column=9, value=str(snap.scraped_at))

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="pe_tracker_export.xlsx"'
        wb.save(response)
        return response

    return render(request, 'tracker/people.html', {
        'people':           people,
        'companies':        companies,
        'seniorities':      seniorities,
        'search':           search,
        'company_filter':   company_filter,
        'seniority_filter': seniority_filter,
        'group_filter':     group_filter,
        'region_filter':    region_filter,
        'function_filter':  function_filter,
        'last_seen_filter': last_seen_filter,
    })
