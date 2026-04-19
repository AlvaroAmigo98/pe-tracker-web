from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Count, Max, Q
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
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


def _get_latest_snapshots_qs(company=None):
    """Return latest snapshot per person using DISTINCT ON (PostgreSQL).
    Reduces DB load from loading all historical rows to only the latest per person.
    """
    qs = PersonSnapshot.objects.order_by('person_id', '-scraped_at').distinct('person_id')
    if company:
        qs = PersonSnapshot.objects.filter(
            person__company=company
        ).order_by('person_id', '-scraped_at').distinct('person_id')
    return qs


def _make_excel_response(filename, headers, rows, col_widths):
    wb = openpyxl.Workbook()
    ws = wb.active
    header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        ws.column_dimensions[get_column_letter(col)].width = col_widths.get(col, 18)
    for row_num, row_data in enumerate(rows, start=2):
        for col, val in enumerate(row_data, 1):
            ws.cell(row=row_num, column=col, value=val)
    ws.freeze_panes = "A2"
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


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

    events_qs = ChangeEvent.objects.select_related(
        'person', 'person__company'
    ).order_by('-detected_at', '-id')

    events = list(events_qs)

    person_ids = list({e.person_id for e in events})

    latest_snapshot_by_person = {}
    if person_ids:
        latest_snapshots_qs = PersonSnapshot.objects.filter(
            person_id__in=person_ids
        ).select_related('person').order_by('person_id', '-scraped_at', '-id')

        for snap in latest_snapshots_qs:
            if snap.person_id not in latest_snapshot_by_person:
                latest_snapshot_by_person[snap.person_id] = snap

    for e in events:
        latest_snap = latest_snapshot_by_person.get(e.person_id)
        e.region = infer_region(latest_snap.location if latest_snap else '')
        e.function = infer_function_web(e.new_title or e.previous_title or '')
        e.seniority_group = infer_seniority_group(
            latest_snap.seniority if latest_snap else ''
        )

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

    hires      = [e for e in events if e.event_type == 'hire']
    leavers    = [e for e in events if e.event_type == 'leaver']
    promotions = [e for e in events if e.event_type in ('promotion', 'role_change')]

    if export == 'excel':
        headers = [
            'Name', 'Company', 'Function', 'Change Type', 'Previous Title',
            'New Title', 'Previous Level', 'New Level', 'Region',
            'Seniority Group', 'Detected At'
        ]
        rows = [
            [
                e.person.full_name, e.person.company.name, e.function,
                e.event_type, e.previous_title or '—', e.new_title or '—',
                e.previous_level or '—', e.new_level or '—',
                e.region, e.seniority_group, str(e.detected_at),
            ]
            for e in events
        ]
        widths = {1:28,2:24,3:22,4:18,5:32,6:32,7:16,8:16,9:16,10:18,11:16}
        return _make_excel_response('historical_changes.xlsx', headers, rows, widths)

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


@login_required
def people(request):
    search           = request.GET.get('q', '')
    company_filter   = request.GET.getlist('company')
    seniority_filter = request.GET.getlist('seniority')
    group_filter     = request.GET.getlist('group')
    region_filter    = request.GET.getlist('region')
    function_filter  = request.GET.getlist('function')
    last_seen_filter = request.GET.get('last_seen', '')
    export           = request.GET.get('export', '')

    companies   = Company.objects.order_by('name')
    seniorities = PersonSnapshot.objects.values_list(
        'seniority', flat=True
    ).distinct().order_by('seniority')

    # DISTINCT ON (person_id) — returns only the latest snapshot per person.
    # Replaces the old full-table scan + Python dedup loop.
    people_qs = PersonSnapshot.objects.order_by(
        'person_id', '-scraped_at'
    ).distinct('person_id').select_related('person', 'person__company')

    people = []
    for snap in people_qs:
        snap.region = infer_region(snap.location or '')
        snap.seniority_group = infer_seniority_group(snap.seniority or '')
        snap.function = infer_function_web(snap.job_title or '')
        people.append(snap)

    people.sort(key=lambda p: (p.person.company.name, p.person.full_name))

    if search:
        people = [
            p for p in people if
            search.lower() in p.person.full_name.lower() or
            search.lower() in (p.job_title or '').lower()
        ]
    if company_filter:
        people = [p for p in people if p.person.company.name in company_filter]
    if seniority_filter:
        people = [p for p in people if p.seniority in seniority_filter]
    if group_filter:
        people = [p for p in people if p.seniority_group in group_filter]
    if region_filter:
        people = [p for p in people if p.region in region_filter]
    if function_filter:
        people = [p for p in people if p.function in function_filter]
    if last_seen_filter:
        cutoff = date.today() - timedelta(days=int(last_seen_filter))
        people = [p for p in people if p.scraped_at >= cutoff]

    if export == 'excel':
        headers = [
            'Name', 'Company', 'Title', 'Seniority', 'Group',
            'Function', 'Region', 'Location', 'Last Seen'
        ]
        rows = [
            [
                snap.person.full_name, snap.person.company.name,
                snap.job_title or '—', snap.seniority or '—',
                snap.seniority_group, snap.function, snap.region,
                snap.location or '—', str(snap.scraped_at),
            ]
            for snap in people
        ]
        widths = {i: 20 for i in range(1, 10)}
        return _make_excel_response('pe_tracker_export.xlsx', headers, rows, widths)

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


@login_required
def firms(request):
    sort_by = request.GET.get('sort', 'leavers')
    valid_sorts = {'leavers', 'hires', 'promotions', 'headcount', 'name', 'activity'}
    if sort_by not in valid_sorts:
        sort_by = 'leavers'

    latest_date = PersonSnapshot.objects.aggregate(d=Max('scraped_at'))['d']

    headcount_map = {}
    if latest_date:
        headcount_qs = PersonSnapshot.objects.filter(
            scraped_at=latest_date
        ).values('person__company_id').annotate(headcount=Count('id'))
        headcount_map = {row['person__company_id']: row['headcount'] for row in headcount_qs}

    event_qs = ChangeEvent.objects.values('person__company_id').annotate(
        hires=Count('id', filter=Q(event_type='hire')),
        leavers=Count('id', filter=Q(event_type='leaver')),
        promotions=Count('id', filter=Q(event_type__in=['promotion', 'role_change'])),
    )
    event_map = {row['person__company_id']: row for row in event_qs}

    companies = Company.objects.order_by('name')
    firm_stats = []
    for company in companies:
        stats = event_map.get(company.id, {})
        hires      = stats.get('hires', 0)
        leavers    = stats.get('leavers', 0)
        promotions = stats.get('promotions', 0)
        firm_stats.append({
            'company':    company,
            'headcount':  headcount_map.get(company.id, 0),
            'hires':      hires,
            'leavers':    leavers,
            'promotions': promotions,
            'activity':   hires + leavers + promotions,
        })

    if sort_by == 'name':
        firm_stats.sort(key=lambda x: x['company'].name)
    else:
        firm_stats.sort(key=lambda x: x[sort_by], reverse=True)

    totals = {
        'headcount':  sum(f['headcount']  for f in firm_stats),
        'hires':      sum(f['hires']      for f in firm_stats),
        'leavers':    sum(f['leavers']    for f in firm_stats),
        'promotions': sum(f['promotions'] for f in firm_stats),
    }

    return render(request, 'tracker/firms.html', {
        'firm_stats': firm_stats,
        'sort_by':    sort_by,
        'totals':     totals,
        'latest_date': latest_date,
    })


@login_required
def firm_detail(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    tab     = request.GET.get('tab', 'team')
    search  = request.GET.get('q', '')
    export  = request.GET.get('export', '')

    # Latest snapshot per person for this firm
    team_qs = PersonSnapshot.objects.filter(
        person__company=company
    ).order_by('person_id', '-scraped_at').distinct('person_id').select_related('person')

    snap_by_person = {}
    team = []
    for snap in team_qs:
        snap.region = infer_region(snap.location or '')
        snap.seniority_group = infer_seniority_group(snap.seniority or '')
        snap.function = infer_function_web(snap.job_title or '')
        snap_by_person[snap.person_id] = snap
        team.append(snap)

    team.sort(key=lambda p: p.person.full_name)

    # All change events for this firm
    events_qs = ChangeEvent.objects.filter(
        person__company=company
    ).select_related('person').order_by('-detected_at', '-id')

    events = list(events_qs)
    for e in events:
        snap = snap_by_person.get(e.person_id)
        e.region = infer_region(snap.location if snap else '')
        e.function = infer_function_web(e.new_title or e.previous_title or '')
        e.seniority_group = infer_seniority_group(snap.seniority if snap else '')

    hires      = [e for e in events if e.event_type == 'hire']
    leavers    = [e for e in events if e.event_type == 'leaver']
    promotions = [e for e in events if e.event_type in ('promotion', 'role_change')]

    # Apply search to the active tab
    if search:
        def name_match(name, t1='', t2=''):
            q = search.lower()
            return q in name.lower() or q in t1.lower() or q in t2.lower()

        team = [p for p in team if
            name_match(p.person.full_name, p.job_title or '')]
        if tab == 'hires':
            hires = [e for e in hires if
                name_match(e.person.full_name, e.new_title or '', e.previous_title or '')]
        elif tab == 'leavers':
            leavers = [e for e in leavers if
                name_match(e.person.full_name, e.new_title or '', e.previous_title or '')]
        elif tab == 'promotions':
            promotions = [e for e in promotions if
                name_match(e.person.full_name, e.new_title or '', e.previous_title or '')]

    # Excel exports
    if export == 'team':
        headers = ['Name', 'Title', 'Seniority', 'Group', 'Function', 'Region', 'Location', 'Last Seen']
        rows = [
            [p.person.full_name, p.job_title or '—', p.seniority or '—',
             p.seniority_group, p.function, p.region, p.location or '—', str(p.scraped_at)]
            for p in team
        ]
        return _make_excel_response(f'{company.name}_team.xlsx', headers, rows, {i: 22 for i in range(1, 9)})

    if export == 'events':
        headers = ['Name', 'Change Type', 'Previous Title', 'New Title', 'Previous Level', 'New Level', 'Function', 'Region', 'Date']
        source = {'hires': hires, 'leavers': leavers, 'promotions': promotions}.get(tab, events)
        rows = [
            [e.person.full_name, e.event_type, e.previous_title or '—', e.new_title or '—',
             e.previous_level or '—', e.new_level or '—', e.function, e.region, str(e.detected_at)]
            for e in source
        ]
        return _make_excel_response(f'{company.name}_{tab}.xlsx', headers, rows, {i: 22 for i in range(1, 10)})

    return render(request, 'tracker/firm_detail.html', {
        'company':    company,
        'tab':        tab,
        'search':     search,
        'team':       team,
        'hires':      hires,
        'leavers':    leavers,
        'promotions': promotions,
        'all_events': events,
    })
