from django.db import models


class Company(models.Model):
    name       = models.TextField(unique=True)
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
