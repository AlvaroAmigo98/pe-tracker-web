import csv
from datetime import datetime, date
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Company, Person, PersonSnapshot, ChangeEvent, ScrapeRun


# ── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    latest_run       = ScrapeRun.objects.order_by('-ran_at').first()
    companies        = Company.objects.order_by('name')
    company_filter   = request.GET.get('company', '')
    event_type_filter = request.GET.get('event_type', '')
    date_from        = request.GET.get('date_from', '')

    events = ChangeEvent.objects.select_related(
        'person', 'person__company'
    ).order_by('-detected_at')

    if company_filter:
        events = events.filter(person__company__name=company_filter)

    if event_type_filter:
        if event_type_filter == 'promotion':
            events = events.filter(event_type__in=('promotion', 'role_change'))
        else:
            events = events.filter(event_type=event_type_filter)

    if date_from:
        try:
            dt = datetime.strptime(date_from, '%Y-%m-%d').date()
            events = events.filter(detected_at__date__gte=dt)
        except ValueError:
            pass

    # Counts BEFORE slicing
    all_events = list(events)
    hires      = [e for e in all_events if e.event_type == 'hire']
    leavers    = [e for e in all_events if e.event_type == 'leaver']
    promotions = [e for e in all_events if e.event_type in ('promotion', 'role_change')]

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="dashboard_events.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Company', 'Event Type', 'Previous Title', 'New Title', 'Date'])
        for e in all_events:
            writer.writerow([
                e.person.full_name,
                e.person.company.name,
                e.event_type,
                e.previous_title or '',
                e.new_title or '',
                e.detected_at.strftime('%Y-%m-%d'),
            ])
        return response

    # Paginate (50 per page)
    paginator   = Paginator(all_events, 50)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    return render(request, 'tracker/dashboard.html', {
        'latest_run':        latest_run,
        'companies':         companies,
        'company_filter':    company_filter,
        'event_type_filter': event_type_filter,
        'date_from':         date_from,
        'events':            page_obj,
        'hires':             hires,
        'leavers':           leavers,
        'promotions':        promotions,
        'page':              page_obj.number,
        'has_next':          page_obj.has_next(),
        'has_prev':          page_obj.has_previous(),
    })


# ── PEOPLE ───────────────────────────────────────────────────────────────────

@login_required
def people(request):
    search            = request.GET.get('q', '')
    company_filter    = request.GET.get('company', '')
    seniority_filter  = request.GET.get('seniority', '')
    location_filter   = request.GET.get('location', '')
    last_seen_from    = request.GET.get('last_seen_from', '')
    sort              = request.GET.get('sort', 'name')  # default sort by name

    # Dropdown options
    companies   = Company.objects.order_by('name')
    seniorities = PersonSnapshot.objects.values_list(
        'seniority', flat=True
    ).exclude(seniority__isnull=True).exclude(seniority='').distinct().order_by('seniority')
    locations   = PersonSnapshot.objects.values_list(
        'location', flat=True
    ).exclude(location__isnull=True).exclude(location='').distinct().order_by('location')

    # Get latest snapshot per person efficiently
    latest_snapshots = PersonSnapshot.objects.select_related(
        'person', 'person__company'
    ).order_by('person_id', '-scraped_at')

    seen   = set()
    people_list = []
    for snap in latest_snapshots:
        pid = snap.person_id
        if pid not in seen:
            seen.add(pid)
            people_list.append(snap)

    # Filters
    if search:
        people_list = [p for p in people_list if
                       search.lower() in p.person.full_name.lower() or
                       search.lower() in (p.job_title or '').lower()]

    if company_filter:
        people_list = [p for p in people_list if
                       p.person.company.name == company_filter]

    if seniority_filter:
        people_list = [p for p in people_list if
                       p.seniority == seniority_filter]

    if location_filter:
        people_list = [p for p in people_list if
                       (p.location or '') == location_filter]

    if last_seen_from:
        try:
            dt = datetime.strptime(last_seen_from, '%Y-%m-%d').date()
            people_list = [p for p in people_list if
                           p.scraped_at.date() >= dt]
        except ValueError:
            pass

    # Sorting
    reverse = sort.startswith('-')
    sort_key = sort.lstrip('-')

    sort_map = {
        'name':       lambda p: p.person.full_name.lower(),
        'company':    lambda p: p.person.company.name.lower(),
        'seniority':  lambda p: (p.seniority or '').lower(),
        'location':   lambda p: (p.location or '').lower(),
        'scraped_at': lambda p: p.scraped_at,
    }

    if sort_key in sort_map:
        people_list = sorted(people_list, key=sort_map[sort_key], reverse=reverse)

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="people.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Company', 'Title', 'Seniority', 'Location', 'Last Seen'])
        for p in people_list:
            writer.writerow([
                p.person.full_name,
                p.person.company.name,
                p.job_title or '',
                p.seniority or '',
                p.location or '',
                p.scraped_at.strftime('%Y-%m-%d'),
            ])
        return response

    # Paginate (100 per page)
    paginator   = Paginator(people_list, 100)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    return render(request, 'tracker/people.html', {
        'people':           page_obj,
        'companies':        companies,
        'seniorities':      seniorities,
        'locations':        locations,
        'search':           search,
        'company_filter':   company_filter,
        'seniority_filter': seniority_filter,
        'location_filter':  location_filter,
        'last_seen_from':   last_seen_from,
        'sort':             sort,
        'page':             page_obj.number,
        'has_next':         page_obj.has_next(),
        'has_prev':         page_obj.has_previous(),
    })
