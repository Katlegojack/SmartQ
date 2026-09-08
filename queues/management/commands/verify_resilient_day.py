from datetime import date, time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueForecastObservation, QueueTicket
from queues.resilient_day import (
    DEFAULT_CUSTOMERS,
    DEFAULT_NO_SHOWS,
    OPERATING_END,
    OPERATING_START,
    SCENARIO_BRANCH_CODE,
    SCENARIO_MANAGER_USERNAME,
    SCENARIO_RECEPTIONIST_USERNAME,
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    appointment_slots,
    no_show_positions,
    planned_service_minutes_for_booking,
    scenario_customer_prefix,
)


class Command(BaseCommand):
    help = "Verify the Day 62 resilient training scenario before the live 09:00 run."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="target_date", required=True)
        parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
        parser.add_argument("--no-shows", type=int, default=DEFAULT_NO_SHOWS)

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("verify_resilient_day is disabled in production.")

        try:
            target_date = date.fromisoformat(options["target_date"])
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc

        expected_customers = int(options["customers"])
        expected_no_shows = int(options["no_shows"])
        errors = []
        warnings = []

        try:
            branch = Branch.objects.get(branch_code=SCENARIO_BRANCH_CODE)
        except Branch.DoesNotExist as exc:
            raise CommandError("Training branch ML01 is missing. Run seed_resilient_day first.") from exc

        if not branch.is_active:
            errors.append("Training branch is inactive.")
        if branch.opening_time != OPERATING_START:
            errors.append(f"Training branch must open at {OPERATING_START:%H:%M}.")
        if branch.closing_time != OPERATING_END:
            errors.append(f"Training branch must close at {OPERATING_END:%H:%M}.")

        prefix = scenario_customer_prefix(target_date)
        bookings = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=target_date,
            branch=branch,
        ).select_related("user", "service", "queueticket")

        if bookings.count() != expected_customers:
            errors.append(f"Expected {expected_customers} seeded bookings, found {bookings.count()}.")

        tickets = QueueTicket.objects.filter(booking__in=bookings)
        expected_priority = max(1, round(expected_customers * 0.10))
        priority_count = tickets.filter(queue_type=QueueTicket.PRIORITY).count()
        general_count = tickets.filter(queue_type=QueueTicket.GENERAL).count()
        if priority_count != expected_priority:
            errors.append(f"Expected {expected_priority} Priority tickets, found {priority_count}.")
        if general_count != expected_customers - expected_priority:
            errors.append(
                f"Expected {expected_customers - expected_priority} General tickets, found {general_count}."
            )

        planned_absences = no_show_positions(
            expected_customers,
            target_date,
            expected_no_shows,
        )
        if len(planned_absences) != expected_no_shows:
            errors.append("Deterministic no-show selector returned the wrong count.")
        if planned_absences & {0, 1, 2}:
            errors.append("Opening customers must remain available so all counters can start.")

        if bookings.filter(checked_in_at__isnull=False).exists():
            errors.append("At least one seeded booking is already checked in.")
        if tickets.exclude(status=QueueTicket.SCHEDULED).exists():
            errors.append("At least one seeded ticket is not SCHEDULED.")
        if QueueForecastObservation.objects.filter(ticket__in=tickets).exists():
            errors.append("Forecast observations already exist; reset before the live run.")

        generated_slots = appointment_slots(expected_customers)
        if not generated_slots or min(generated_slots) != time(9, 0):
            errors.append("Appointment generation does not start at 09:00.")
        if max(generated_slots) > time(17, 45):
            errors.append("Appointment generation extends beyond 17:45.")
        appointment_times = set(bookings.values_list("booking_time", flat=True))
        for checkpoint in (time(9, 0), time(12, 0), time(15, 0), time(17, 45)):
            if checkpoint not in appointment_times:
                errors.append(f"No seeded booking exists at checkpoint {checkpoint:%H:%M}.")

        counters = list(
            Counter.objects.filter(branch=branch)
            .select_related("assigned_staff", "assigned_staff__profile")
            .order_by("counter_number")
        )
        if len(counters) != 3:
            errors.append(f"Expected exactly 3 training counters, found {len(counters)}.")
        else:
            queue_types = [counter.queue_type for counter in counters]
            if queue_types.count(QueueTicket.GENERAL) != 2:
                errors.append("Training branch must have exactly two General counters.")
            if queue_types.count(QueueTicket.PRIORITY) != 1:
                errors.append("Training branch must have exactly one Priority counter.")
            for counter in counters:
                if counter.status != Counter.CLOSED:
                    errors.append(
                        f"Counter {counter.counter_number} is {counter.status}; expected closed before 09:00."
                    )
                if counter.assigned_staff_id is None:
                    errors.append(f"Counter {counter.counter_number} has no assigned staff member.")
                elif counter.assigned_staff.profile.role != Profile.COUNTER_STAFF:
                    errors.append(f"Counter {counter.counter_number} is not assigned to Counter Staff.")
                elif counter.assigned_staff.profile.branch_id != branch.id:
                    errors.append(f"Counter {counter.counter_number} staff belongs to the wrong branch.")

        opening_bookings = list(bookings.filter(booking_time=time(9, 0)))
        opening_general = sum(
            booking.queueticket.queue_type == QueueTicket.GENERAL for booking in opening_bookings
        )
        opening_priority = sum(
            booking.queueticket.queue_type == QueueTicket.PRIORITY for booking in opening_bookings
        )
        if opening_general < 2 or opening_priority < 1:
            errors.append("09:00 must include at least two General and one Priority seeded arrival.")

        for service_code in SERVICE_SEQUENCE:
            service_bookings = list(
                bookings.filter(service__service_code=service_code).select_related("user", "service")
            )
            if not service_bookings:
                errors.append(f"No seeded bookings exist for {service_code}.")
                continue
            target = SERVICE_PROFILES[service_code]["average_minutes"]
            planned = [
                planned_service_minutes_for_booking(booking, target_date)
                for booking in service_bookings
            ]
            if not any(value < target for value in planned):
                errors.append(f"{service_code} has no early-finish examples.")
            if target not in planned:
                errors.append(f"{service_code} has no exactly-on-target examples.")
            if not any(value > target for value in planned):
                errors.append(f"{service_code} has no overrun examples.")

        for username, role in (
            (SCENARIO_MANAGER_USERNAME, Profile.BRANCH_MANAGER),
            (SCENARIO_RECEPTIONIST_USERNAME, Profile.RECEPTIONIST),
        ):
            try:
                observer = User.objects.select_related("profile").get(username=username)
            except User.DoesNotExist:
                errors.append(f"Training observer {username} is missing.")
                continue
            if observer.profile.role != role or observer.profile.branch_id != branch.id:
                errors.append(f"Training observer {username} has the wrong role or branch scope.")
            if not observer.has_usable_password():
                warnings.append(
                    f"{username} login is disabled. Set its SMARTQ_TRAINING_* password variable and reseed if UI observation is required."
                )

        self.stdout.write(f"Day 62 preflight for {target_date}")
        self.stdout.write(
            f"Seeded: {bookings.count()} | General: {general_count} | Priority: {priority_count} | Planned no-shows: {len(planned_absences)}"
        )
        self.stdout.write(f"Counters: {len(counters)} | Branch: {branch.name} | Hours: 09:00-18:00")
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"ERROR: {error}"))
            raise CommandError(f"Day 62 preflight failed with {len(errors)} blocking issue(s).")

        self.stdout.write(
            self.style.SUCCESS(
                "READY: Day 62 is structurally ready for the 09:00 resilient live training run."
            )
        )
