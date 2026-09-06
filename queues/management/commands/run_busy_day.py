import time as wall_clock
from datetime import date, datetime, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from counters.services import close_counter, open_counter, resume_counter
from queues.busy_day import (
    SCENARIO_BRANCH_CODE,
    SCENARIO_VERSION,
    STAFF_SPECS,
    activate_simulation_booking,
    appointment_datetime,
    planned_service_minutes,
    scenario_customer_prefix,
)
from queues.models import QueueTicket
from queues.services import call_next_ticket, complete_current_ticket, get_current_ticket


class Command(BaseCommand):
    help = "Run the Smart Q synthetic busy day in real time using three automated counters."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            required=True,
            help="Scenario date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--poll-seconds",
            type=float,
            default=2.0,
            help="Internal simulator heartbeat. User-facing Smart Q time remains minutes.",
        )

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("run_busy_day is disabled in production.")

        target_date = self._parse_date(options["target_date"])
        poll_seconds = max(float(options["poll_seconds"]), 0.25)
        branch = self._get_branch()
        prefix = scenario_customer_prefix(target_date)
        bookings = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=target_date,
            branch=branch,
        )
        if not bookings.exists():
            raise CommandError(
                f"No busy-day scenario found for {target_date}. Run seed_busy_day first."
            )

        counters = list(
            Counter.objects.filter(
                branch=branch,
                counter_number__in=[spec[4] for spec in STAFF_SPECS],
            )
            .select_related("assigned_staff", "assigned_staff__profile")
            .order_by("counter_number")
        )
        if len(counters) != 3:
            raise CommandError("Busy-day scenario requires exactly three prepared counters.")
        if any(counter.assigned_staff_id is None for counter in counters):
            raise CommandError("Every busy-day counter must have assigned Counter Staff.")

        start_at = timezone.make_aware(
            datetime.combine(target_date, time(8, 0)),
            timezone.get_current_timezone(),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Busy-day simulator armed for {target_date} at 08:00 on {branch.name}."
            )
        )
        self.stdout.write(
            "The three counters will open automatically, arrivals will enter at their "
            "scheduled times, and service completions will use varied planned durations."
        )

        opened = False
        last_wait_message = None
        while True:
            now = timezone.now()
            if now < start_at:
                minutes_left = max(int((start_at - now).total_seconds() // 60), 0)
                if minutes_left != last_wait_message:
                    self.stdout.write(f"Waiting for 08:00 — approximately {minutes_left} min remaining.")
                    last_wait_message = minutes_left
                wall_clock.sleep(min(poll_seconds, 10.0))
                continue

            if not opened:
                self._open_counters(counters)
                opened = True

            self._activate_due_bookings(
                branch=branch,
                prefix=prefix,
                target_date=target_date,
                now=now,
            )
            self._complete_due_services(counters, target_date)
            self._fill_free_counters(counters, target_date)

            remaining = Booking.objects.filter(
                user__username__startswith=prefix,
                booking_date=target_date,
                branch=branch,
            ).exclude(status=Booking.COMPLETED).count()
            if remaining == 0:
                self._close_counters(counters)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Busy-day simulation complete: all {bookings.count()} customers processed."
                    )
                )
                return

            wall_clock.sleep(poll_seconds)

    def _parse_date(self, raw):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc

    def _get_branch(self):
        try:
            return Branch.objects.get(branch_code=SCENARIO_BRANCH_CODE)
        except Branch.DoesNotExist as exc:
            raise CommandError("Busy-day training branch is missing. Run seed_busy_day first.") from exc

    def _open_counters(self, counters):
        for counter in counters:
            counter.refresh_from_db()
            if counter.status == Counter.OPEN:
                continue
            if counter.status == Counter.PAUSED:
                counter, error = resume_counter(counter, actor=counter.assigned_staff)
            else:
                counter, error = open_counter(counter, actor=counter.assigned_staff)
            if error not in (None, "already_open"):
                raise CommandError(
                    f"Could not open Counter {counter.counter_number}: {error}."
                )
            self.stdout.write(
                f"08:00 START — Counter {counter.counter_number} ({counter.queue_type}) opened."
            )

    def _activate_due_bookings(self, *, branch, prefix, target_date, now):
        due = (
            Booking.objects.filter(
                user__username__startswith=prefix,
                booking_date=target_date,
                branch=branch,
                checked_in_at__isnull=True,
                status__in=[Booking.PENDING, Booking.CONFIRMED],
            )
            .select_related("user", "service", "branch")
            .order_by("booking_time", "id")
        )
        for booking in due:
            scheduled_at = appointment_datetime(booking)
            if scheduled_at > now:
                break
            ticket, error = activate_simulation_booking(
                booking,
                occurred_at=scheduled_at,
            )
            if error not in (None, "already_checked_in"):
                raise CommandError(
                    f"Could not activate {booking.user.username}: {error}."
                )
            if ticket is not None and error is None:
                self.stdout.write(
                    f"ARRIVAL {booking.booking_time.strftime('%H:%M')} — "
                    f"{ticket.queue_number} / {booking.service.name} / {ticket.queue_type}."
                )

    def _complete_due_services(self, counters, target_date):
        now = timezone.now()
        for counter in counters:
            counter.refresh_from_db()
            ticket = get_current_ticket(counter)
            if ticket is None or ticket.booking.user_id is None:
                continue
            username = ticket.booking.user.username
            if not username.startswith(scenario_customer_prefix(target_date)):
                continue
            planned_minutes = planned_service_minutes(
                username,
                ticket.booking.service.service_code,
                target_date,
            )
            if ticket.service_started_at is None:
                continue
            elapsed = (now - ticket.service_started_at).total_seconds()
            if elapsed < planned_minutes * 60:
                continue

            completed = complete_current_ticket(counter, actor=counter.assigned_staff)
            if completed is None:
                continue
            actual_minutes = (completed.actual_service_seconds or 0) / 60
            variance_minutes = (completed.service_variance_seconds or 0) / 60
            self.stdout.write(
                f"COMPLETE — {completed.queue_number} at Counter {counter.counter_number}: "
                f"actual {actual_minutes:.1f} min, target "
                f"{(completed.service_target_seconds or 0) / 60:.0f} min, "
                f"variance {variance_minutes:+.1f} min."
            )

    def _fill_free_counters(self, counters, target_date):
        for counter in counters:
            counter.refresh_from_db()
            if counter.status != Counter.OPEN or get_current_ticket(counter) is not None:
                continue
            ticket = call_next_ticket(
                counter,
                booking_date=target_date,
                actor=counter.assigned_staff,
            )
            if ticket is None:
                continue
            planned_minutes = planned_service_minutes(
                ticket.booking.user.username,
                ticket.booking.service.service_code,
                target_date,
            )
            self.stdout.write(
                f"CALL — Counter {counter.counter_number} serving {ticket.queue_number} "
                f"({ticket.booking.service.name}); planned actual duration "
                f"{planned_minutes} min vs target "
                f"{(ticket.service_target_seconds or 0) / 60:.0f} min."
            )

    def _close_counters(self, counters):
        for counter in counters:
            counter.refresh_from_db()
            if counter.status == Counter.CLOSED:
                continue
            counter, error = close_counter(counter, actor=counter.assigned_staff)
            if error not in (None, "already_closed"):
                self.stdout.write(
                    self.style.WARNING(
                        f"Counter {counter.counter_number} could not close cleanly: {error}."
                    )
                )
