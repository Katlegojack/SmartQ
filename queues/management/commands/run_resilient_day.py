import time as wall_clock
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from counters.services import close_counter, open_counter, resume_counter
from queues.models import QueueTicket
from queues.resilient_day import (
    DEFAULT_CUSTOMERS,
    DEFAULT_NO_SHOWS,
    NO_SHOW_GRACE_MINUTES,
    OPERATING_END,
    OPERATING_START,
    SCENARIO_BRANCH_CODE,
    STAFF_SPECS,
    activate_simulation_booking,
    appointment_datetime,
    is_seeded_no_show,
    mark_scheduled_no_show,
    operating_datetime,
    planned_service_minutes_for_booking,
    scenario_customer_prefix,
)
from queues.services import call_next_ticket, complete_current_ticket, get_current_ticket


class Command(BaseCommand):
    help = "Run the Day 62 resilient Smart Q training day in real time from 09:00 to 18:00."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="target_date", required=True)
        parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
        parser.add_argument("--no-shows", type=int, default=DEFAULT_NO_SHOWS)
        parser.add_argument(
            "--poll-seconds",
            type=float,
            default=2.0,
            help="Internal runner heartbeat; UI time remains minute-based.",
        )

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("run_resilient_day is disabled in production.")

        target_date = self._parse_date(options["target_date"])
        customer_count = int(options["customers"])
        no_show_count = int(options["no_shows"])
        poll_seconds = max(float(options["poll_seconds"]), 0.25)

        branch = self._get_branch()
        prefix = scenario_customer_prefix(target_date)
        seeded = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=target_date,
            branch=branch,
        )
        if seeded.count() != customer_count:
            raise CommandError(
                f"Expected {customer_count} seeded bookings, found {seeded.count()}. Run seed_resilient_day and verify_resilient_day first."
            )

        counters = list(
            Counter.objects.filter(
                branch=branch,
                counter_number__in=[spec[4] for spec in STAFF_SPECS],
            )
            .select_related("assigned_staff", "assigned_staff__profile")
            .order_by("counter_number")
        )
        if len(counters) != 3 or any(counter.assigned_staff_id is None for counter in counters):
            raise CommandError("Day 62 requires exactly three staffed ML01 counters.")

        start_at = operating_datetime(target_date, OPERATING_START)
        close_at = operating_datetime(target_date, OPERATING_END)
        self.stdout.write(
            self.style.SUCCESS(
                f"Day 62 runner armed for {target_date}: ML01 operates 09:00-18:00."
            )
        )
        self.stdout.write(
            f"Seeded workload: {customer_count}; deterministic no-shows: {no_show_count}. "
            "Customer and Reception walk-ins are EXTRA and will be served normally."
        )
        self.stdout.write(
            "Counter 3 keeps Priority first, but helps General whenever no Priority customer is waiting."
        )

        opened = False
        last_wait_message = None
        while True:
            now = timezone.now()
            if now < start_at:
                minutes_left = max(int((start_at - now).total_seconds() // 60), 0)
                if minutes_left != last_wait_message:
                    self.stdout.write(
                        f"Waiting for 09:00 - approximately {minutes_left} min remaining."
                    )
                    last_wait_message = minutes_left
                wall_clock.sleep(min(poll_seconds, 10.0))
                continue

            if not opened:
                self._open_counters(counters)
                opened = True

            self._activate_due_seeded_arrivals(
                branch=branch,
                prefix=prefix,
                target_date=target_date,
                now=now,
                customer_count=customer_count,
                no_show_count=no_show_count,
            )
            self._mark_due_seeded_no_shows(
                branch=branch,
                prefix=prefix,
                target_date=target_date,
                now=now,
                customer_count=customer_count,
                no_show_count=no_show_count,
            )
            self._complete_due_services(counters, target_date)
            self._fill_free_counters(counters, target_date)

            seeded_remaining = seeded.exclude(
                status__in=[Booking.COMPLETED, Booking.NO_SHOW]
            ).count()
            active_live = QueueTicket.objects.filter(
                booking__branch=branch,
                booking__booking_date=target_date,
                status__in=[QueueTicket.WAITING, QueueTicket.SERVING],
            ).count()

            # Stay operational through 18:00 so real Customer and Reception extras
            # can join throughout the experiment. After closing time, drain anyone
            # already in the queue before shutting the training counters.
            if now >= close_at and seeded_remaining == 0 and active_live == 0:
                self._close_counters(counters)
                completed_seeded = seeded.filter(status=Booking.COMPLETED).count()
                no_shows = seeded.filter(status=Booking.NO_SHOW).count()
                all_day = Booking.objects.filter(
                    branch=branch,
                    booking_date=target_date,
                )
                extra_completed = all_day.exclude(
                    user__username__startswith=prefix
                ).filter(status=Booking.COMPLETED).count()
                self.stdout.write(
                    self.style.SUCCESS(
                        "Day 62 resilient simulation complete: "
                        f"{completed_seeded} seeded served, {no_shows} seeded no-shows, "
                        f"{extra_completed} extra live customers served."
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
            raise CommandError("ML01 is missing. Run seed_resilient_day first.") from exc

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
                f"09:00 START - Counter {counter.counter_number} ({counter.queue_type}) opened."
            )

    def _activate_due_seeded_arrivals(
        self,
        *,
        branch,
        prefix,
        target_date,
        now,
        customer_count,
        no_show_count,
    ):
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
            if is_seeded_no_show(
                booking.user.username,
                target_date=target_date,
                customer_count=customer_count,
                no_show_count=no_show_count,
            ):
                continue
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
                    f"ARRIVAL {booking.booking_time.strftime('%H:%M')} - "
                    f"{ticket.queue_number} / {booking.service.name} / {ticket.queue_type}."
                )

    def _mark_due_seeded_no_shows(
        self,
        *,
        branch,
        prefix,
        target_date,
        now,
        customer_count,
        no_show_count,
    ):
        candidates = (
            Booking.objects.filter(
                user__username__startswith=prefix,
                booking_date=target_date,
                branch=branch,
                checked_in_at__isnull=True,
                status__in=[Booking.PENDING, Booking.CONFIRMED],
            )
            .select_related("user", "service")
            .order_by("booking_time", "id")
        )
        for booking in candidates:
            if not is_seeded_no_show(
                booking.user.username,
                target_date=target_date,
                customer_count=customer_count,
                no_show_count=no_show_count,
            ):
                continue
            no_show_at = appointment_datetime(booking) + timedelta(
                minutes=NO_SHOW_GRACE_MINUTES
            )
            if no_show_at > now:
                continue
            ticket, error = mark_scheduled_no_show(
                booking,
                occurred_at=no_show_at,
            )
            if error is None:
                self.stdout.write(
                    f"NO SHOW {booking.booking_time.strftime('%H:%M')} - "
                    f"{ticket.queue_number} / {booking.service.name}; queue continues."
                )

    def _complete_due_services(self, counters, target_date):
        now = timezone.now()
        for counter in counters:
            counter.refresh_from_db()
            ticket = get_current_ticket(counter)
            if ticket is None:
                continue
            booking = Booking.objects.select_related(
                "user", "guest_customer", "service", "branch"
            ).get(pk=ticket.booking_id)
            # ML01 is a dedicated training branch: seeded users and genuine live
            # extras intentionally share this runner and queue.
            planned_minutes = planned_service_minutes_for_booking(
                booking,
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
            source_label = "seeded" if (
                booking.user_id
                and booking.user.username.startswith(scenario_customer_prefix(target_date))
            ) else "EXTRA"
            self.stdout.write(
                f"COMPLETE - {completed.queue_number} at Counter {counter.counter_number}: "
                f"actual {actual_minutes:.1f} min, target "
                f"{(completed.service_target_seconds or 0) / 60:.0f} min, "
                f"variance {variance_minutes:+.1f} min [{source_label}]."
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
            booking = Booking.objects.select_related(
                "user", "guest_customer", "service"
            ).get(pk=ticket.booking_id)
            planned_minutes = planned_service_minutes_for_booking(
                booking,
                target_date,
            )
            overflow = (
                counter.queue_type == QueueTicket.PRIORITY
                and ticket.queue_type == QueueTicket.GENERAL
            )
            overflow_note = " [Priority counter helping General]" if overflow else ""
            self.stdout.write(
                f"CALL - Counter {counter.counter_number} serving {ticket.queue_number} "
                f"({booking.service.name}); planned actual duration {planned_minutes} min "
                f"vs target {(ticket.service_target_seconds or 0) / 60:.0f} min.{overflow_note}"
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
