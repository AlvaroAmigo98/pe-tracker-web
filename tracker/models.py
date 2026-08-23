from django.db import models

# All models are managed=False — the schema (and its indexes) live in Supabase,
# not in Django migrations. Performance indexes applied directly in Supabase:
#   person_snapshot (person_id, scraped_at DESC)   ix_person_snapshot_person_scraped
#   person_snapshot (scraped_at)                    ix_person_snapshot_scraped
#   change_event    (detected_at DESC)              ix_change_event_detected
#   change_event    (person_id)                     ix_change_event_person
#   change_event    (event_type, detected_at)       ix_change_event_type_detected
#   person          (company_id)                    ix_person_company


class Company(models.Model):
    name       = models.TextField(unique=True)
    bucket     = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = 'company'

    def __str__(self):
        return self.name


class Person(models.Model):
    company      = models.ForeignKey(Company, models.DO_NOTHING, blank=True, null=True)
    full_name    = models.TextField()
    first_seen_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = 'person'

    def __str__(self):
        return self.full_name


class PersonSnapshot(models.Model):
    person     = models.ForeignKey(Person, models.DO_NOTHING, blank=True, null=True)
    job_title  = models.TextField(blank=True, null=True)
    seniority  = models.TextField(blank=True, null=True)
    team       = models.TextField(blank=True, null=True)
    location   = models.TextField(blank=True, null=True)
    scraped_at = models.DateField()

    class Meta:
        managed  = False
        db_table = 'person_snapshot'


class ChangeEvent(models.Model):
    person         = models.ForeignKey(Person, models.DO_NOTHING, blank=True, null=True)
    event_type     = models.TextField()
    previous_title = models.TextField(blank=True, null=True)
    new_title      = models.TextField(blank=True, null=True)
    previous_level = models.TextField(blank=True, null=True)
    new_level      = models.TextField(blank=True, null=True)
    detected_at    = models.DateField()

    class Meta:
        managed  = False
        db_table = 'change_event'


class ScrapeRun(models.Model):
    ran_at       = models.DateTimeField(blank=True, null=True)
    total_rows   = models.IntegerField(blank=True, null=True)
    firms_ok     = models.IntegerField(blank=True, null=True)
    firms_failed = models.IntegerField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = 'scrape_run'


class ScrapeRunFirm(models.Model):
    run          = models.ForeignKey(ScrapeRun, models.CASCADE, related_name='firms')
    firm_name    = models.TextField()
    row_count    = models.IntegerField(default=0)
    status       = models.TextField()   # ok | empty | below_threshold | error
    error_msg    = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = 'scrape_run_firm'


class AuditLog(models.Model):
    event_type = models.TextField()          # LOGIN | LOGOUT | LOGIN_FAILED
    username   = models.TextField()
    ip_address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed  = False
        db_table = 'audit_log'


class ScrapeStaging(models.Model):
    batch_id    = models.TextField()
    firm_name   = models.TextField()
    run_date    = models.DateField()
    person_name = models.TextField(blank=True, null=True)
    job_title   = models.TextField(blank=True, null=True)
    team        = models.TextField(blank=True, null=True)
    location    = models.TextField(blank=True, null=True)
    raw_html    = models.TextField(blank=True, null=True)
    status      = models.TextField(default='pending')  # pending | promoted | rejected | flagged
    flag_reason = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed  = False
        db_table = 'scrape_staging'

    def __str__(self):
        return f'{self.firm_name} / {self.person_name} [{self.status}]'


class ScrapeHealth(models.Model):
    company         = models.ForeignKey(Company, models.SET_NULL, blank=True, null=True)
    firm_name       = models.TextField()
    week_commencing = models.DateField()
    row_count       = models.IntegerField(default=0)
    prev_row_count  = models.IntegerField(blank=True, null=True)
    status          = models.TextField()  # ok | warning | broken | skipped
    error_msg       = models.TextField(blank=True, null=True)
    retry_count     = models.IntegerField(default=0)
    raw_html_sample = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed  = False
        db_table = 'scrape_health'
        unique_together = [('firm_name', 'week_commencing')]

    def __str__(self):
        return f'{self.firm_name} w/c {self.week_commencing} [{self.status}]'
