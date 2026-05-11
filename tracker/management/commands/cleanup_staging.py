from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tracker.models import ScrapeStaging


class Command(BaseCommand):
    help = 'Delete promoted/rejected staging rows older than N days (default: 30)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='Delete rows created more than this many days ago')
        parser.add_argument('--dry-run', action='store_true',
                            help='Print what would be deleted without deleting')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        qs = ScrapeStaging.objects.filter(
            status__in=['promoted', 'rejected'],
            created_at__lt=cutoff,
        )
        count = qs.count()
        if options['dry_run']:
            self.stdout.write(
                f'DRY RUN: {count} staging rows older than {options["days"]} days '
                f'(cutoff: {cutoff.date()}) would be deleted'
            )
        else:
            qs.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {count} staging rows older than {options["days"]} days'
            ))
