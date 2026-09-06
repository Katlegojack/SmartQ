import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from branches.models import Branch
from queues.forecasting import FORECAST_EXPORT_FIELDS, iter_forecasting_rows


class Command(BaseCommand):
    help = "Export Smart Q forecasting observations as a PII-minimised CSV dataset."

    def add_arguments(self, parser):
        parser.add_argument("--branch-id", type=int)
        parser.add_argument("--start-date")
        parser.add_argument("--end-date")
        parser.add_argument("--output")

    def handle(self, *args, **options):
        start_date = parse_date(options["start_date"]) if options["start_date"] else None
        end_date = parse_date(options["end_date"]) if options["end_date"] else None

        if options["start_date"] and start_date is None:
            raise CommandError("--start-date must use YYYY-MM-DD.")
        if options["end_date"] and end_date is None:
            raise CommandError("--end-date must use YYYY-MM-DD.")
        if start_date and end_date and start_date > end_date:
            raise CommandError("--start-date cannot be after --end-date.")

        branch = None
        if options["branch_id"] is not None:
            try:
                branch = Branch.objects.get(pk=options["branch_id"])
            except Branch.DoesNotExist as exc:
                raise CommandError("The requested branch does not exist.") from exc

        rows = list(
            iter_forecasting_rows(
                branch=branch,
                start_date=start_date,
                end_date=end_date,
            )
        )

        output_path = options["output"]
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FORECAST_EXPORT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"Exported {len(rows)} observations to {path}."))
            return

        writer = csv.DictWriter(self.stdout, fieldnames=FORECAST_EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
