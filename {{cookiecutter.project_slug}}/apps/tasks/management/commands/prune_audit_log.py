"""Run the audit-log retention policy by hand.

The scheduled task calls the same function. This command exists so the job can be
run once, watched, and its output read before anybody trusts a schedule with it -
and so it still works from a crontab if the queue is ever removed.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.tasks import retention


class Command(BaseCommand):
    help = "Delete audit-log entries older than the retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Retention period in days. Defaults to AUDITLOG_RETENTION_DAYS. "
                "Values below 365 are refused: the security baseline requires at "
                "least 12 months of audit history."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many entries would be deleted, and delete nothing.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if options["dry_run"]:
            count = retention.count_prunable_audit_entries(days)
            self.stdout.write(f"{count} audit log entries are older than the retention period.")
            return

        try:
            deleted = retention.prune_audit_log(days)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} audit log entries."))
