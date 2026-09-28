from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bookings.models import Booking


class Command(BaseCommand):
    help = "Shift prepared Pretoria live-study appointments to a new start time."

    def add_arguments(self, parser):
        parser.add_argument("--date", required=True)
        parser.add_argument("--start-time", required=True)
        parser.add_argument("--window-minutes", type=int, default=90)

    def handle(self, *args, **options):
        target_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
        start_time = datetime.strptime(options["start_time"], "%H:%M").time()
        start_at = timezone.make_aware(
            datetime.combine(target_date, start_time),
            timezone.get_current_timezone(),
        )

        bookings = list(
            Booking.objects.filter(
                user__username__startswith=f"ptastudy_{target_date:%Y%m%d}_",
                booking_date=target_date,
                branch__branch_code="PTA01",
                checked_in_at__isnull=True,
            ).order_by("user__username")
        )
        if not bookings:
            raise CommandError("No prepared Pretoria study bookings were found.")

        window = int(options["window_minutes"])
        total = len(bookings)
        for index, booking in enumerate(bookings):
            when = start_at + timedelta(minutes=(window * index) / total)
            booking.booking_time = timezone.localtime(when).time().replace(
                second=0,
                microsecond=0,
            )
            booking.save(update_fields=["booking_time"])

        self.stdout.write(
            self.style.SUCCESS(
                f"RESCHEDULED — {total} Pretoria Central study bookings from "
                f"{start_time.strftime('%H:%M')} across {window} minutes."
            )
        )
