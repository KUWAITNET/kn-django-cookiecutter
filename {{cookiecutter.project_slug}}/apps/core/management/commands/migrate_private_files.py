"""Copy the files of every private field from public storage to private storage.

Changing a field's ``storage=`` moves nothing. Files uploaded before the change
stay in the ``default`` storage, still on a public URL, until this copies them.
It follows the media storage standard, section 8:

- every private field is found by introspection, so there is no list to forget;
- each file is copied under **the same name**, so no database row changes;
- a file already in private storage is skipped, so it is safe to re-run;
- a missing source file is reported, and any failure exits non-zero;
- ``--dry-run`` reports and changes nothing;
- ``--delete-source`` first copies anything uploaded since the last run, then
  deletes each public copy, and only once it exists in private storage;
- it refuses to run when both aliases point at the same place, where
  ``--delete-source`` would delete the only copy.

History tables (django-simple-history and the like) store file names as text.
Their rows keep the old names and are not copied.

The rollout order - copy, check in the browser, then delete, then invalidate any
CDN - is in docs/03-infrastructure.md.
"""

from pathlib import Path

from django.core.files.storage import FileSystemStorage, storages
from django.core.management.base import BaseCommand, CommandError

from apps.core.private_files import private_file_fields


def _location(storage):
    """Where a storage writes, in a form two storages can be compared on."""
    if isinstance(storage, FileSystemStorage):
        return ("filesystem", str(Path(storage.location).resolve()))
    store = getattr(storage, "bucket_name", None) or getattr(storage, "azure_container", None)
    return ("bucket", store, getattr(storage, "location", ""))


class Command(BaseCommand):
    help = "Copy files of private fields from the default storage to the private storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be copied or deleted, and change nothing.",
        )
        parser.add_argument(
            "--delete-source",
            action="store_true",
            help="After copying, delete each public copy that now exists in private storage.",
        )

    def handle(self, *args, dry_run=False, delete_source=False, **options):
        source = storages["default"]
        target = storages["private"]
        if _location(source) == _location(target):
            raise CommandError(
                "The default and private storages point at the same place; "
                "copying is meaningless and --delete-source would delete the only copy."
            )

        names = self._stored_names()
        copied = skipped = 0
        failures = []
        for name in names:
            if target.exists(name):
                skipped += 1
                continue
            if not source.exists(name):
                failures.append(f"missing in default storage: {name}")
                continue
            if dry_run:
                self.stdout.write(f"would copy {name}")
                copied += 1
                continue
            try:
                with source.open(name, "rb") as handle:
                    saved = target.save(name, handle)
            except OSError as exc:
                failures.append(f"copy failed: {name}: {exc}")
                continue
            if saved != name:
                # The storage renamed it, so the row would point at nothing.
                target.delete(saved)
                failures.append(f"copy failed: {name}: saved as {saved}")
                continue
            copied += 1

        deleted = 0
        if delete_source:
            for name in names:
                if not source.exists(name):
                    continue
                if not dry_run and not target.exists(name):
                    # Never delete what has not arrived; a failure is reported above.
                    continue
                if dry_run:
                    self.stdout.write(f"would delete {name} from default storage")
                else:
                    source.delete(name)
                deleted += 1

        verb = "would copy" if dry_run else "copied"
        summary = f"{verb} {copied}, already private {skipped}, failed {len(failures)}"
        if delete_source:
            summary += f", {'would delete' if dry_run else 'deleted'} {deleted}"
        for failure in failures:
            self.stderr.write(failure)
        if failures:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))

    def _stored_names(self):
        """Every distinct stored name across every private field, in a stable order."""
        names = set()
        for model, field in private_file_fields():
            values = (
                model._default_manager.exclude(**{field.name: ""})
                .exclude(**{f"{field.name}__isnull": True})
                .values_list(field.name, flat=True)
            )
            names.update(values)
        return sorted(names)
