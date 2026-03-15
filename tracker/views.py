from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun


SENIORITY_GROUP = {
    "Partner / MD": "Senior",
    "Director":     "Senior",
    "VP":           "Senior",
    "Principal":    "Senior",
    "Associate":    "Junior",
    "Analyst":      "Junior",
    "Other":        "Junior",
    "Unknown":      "Junior",
}

LOCATION_REGIONS = {
    # North America
    "new york": "North America", "san francisco": "North America",
    "chicago": "North America", "boston": "North America",
    "los angeles": "North America", "houston": "North America",
    "toronto": "North America", "miami": "North America",
    "washington": "North America", "menlo park": "North America",
    "nashville": "North America", "atlanta": "North America",
    "dallas": "North America", "montreal": "North America",
    "united states": "North America", "usa": "North America",
    "canada": "North America",
    # EMEA
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
    "ireland": "EMEA", "portugal": "EMEA",
    # APAC
    "hong kong": "APAC", "singapore": "APAC", "tokyo": "APAC",
    "shanghai": "APAC", "beijing": "APAC", "sydney": "APAC",
    "melbourne": "APAC", "seoul": "APAC", "mumbai": "APAC",
    "bangalore": "APAC", "delhi": "APAC", "taipei": "APAC",
    "china": "APAC", "japan": "APAC", "australia": "APAC",
    "india": "APAC", "south korea": "APAC", "taiwan": "APAC",
    "new zealand": "APAC", "indonesia": "APAC", "malaysia": "APAC",
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


@login_required
def dashboard(request):
    latest_run     = ScrapeRun.objects.order_by('-ran_at').first()
    companies      = Company.objects.order_by('name')
    company_filter = request.GET.get('company', '')

    events = ChangeEvent.objects.select_related(
        'person', 'person__company'
    ).order_by('-detected_at')

    if company_filter:
        events = events.filter(person__company__name=company_filter)

    events = events[:50]

    hires      = [e for e in events if e.event_type == 'hire']
    leavers    = [e for e in events if e.event_type == 'leaver']
    promotions = [e for e in events if e.event_type in ('promotion', 'role_change')]

    return render(request, 'tracker/dashboard.html', {
        'latest_run':     latest_run,
        'companies':      companies,
        'company_filter': company_filter,
        'events':         events,
        'hires':          hires,
        'leavers':        leavers,
        'promotions':     promotions,
    })


@login_required
def people(request):
    search           = request.GET.get('q', '')
    company_filter   = request.GET.get('company', '')
    seniority_filter = request.GET.get('seniority', '')
    group_filter     = request.GET.get('group', '')
    region_filter    = request.GET.get('region', '')

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
            # Annotate with region and seniority group
            snap.region           = infer_region(snap.location or '')
            snap.seniority_group  = infer_seniority_group(snap.seniority or '')
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

    return render(request, 'tracker/people.html', {
        'people':           people,
        'companies':        companies,
        'seniorities':      seniorities,
        'search':           search,
        'company_filter':   company_filter,
        'seniority_filter': seniority_filter,
        'group_filter':     group_filter,
        'region_filter':    region_filter,
    })
