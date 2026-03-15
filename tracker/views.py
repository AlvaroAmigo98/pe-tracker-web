from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun


@login_required
def dashboard(request):
    latest_run = ScrapeRun.objects.order_by('-ran_at').first()
    companies  = Company.objects.order_by('name')

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
            people.append(snap)

    if search:
        people = [p for p in people if
                  search.lower() in p.person.full_name.lower() or
                  search.lower() in (p.job_title or '').lower()]

    if company_filter:
        people = [p for p in people if p.person.company.name == company_filter]

    if seniority_filter:
        people = [p for p in people if p.seniority == seniority_filter]

    return render(request, 'tracker/people.html', {
        'people':           people,
        'companies':        companies,
        'seniorities':      seniorities,
        'search':           search,
        'company_filter':   company_filter,
        'seniority_filter': seniority_filter,
    })