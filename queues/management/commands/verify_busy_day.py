from datetime import date, time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.busy_day import (
    SCENARIO_BRANCH_CODE,
    SCENARIO_MANAGER_PASSWORD,
    SCENARIO_MANAGER_USERNAME,
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    planned_service_minutes,
    scenario_customer_prefix,
)
from queues.models import QueueForecastObservation, QueueTicket


class Command(BaseCommand):
    help = "Verify that a seeded Smart Q busy-day scenario is safe and ready to run."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="target_date", required=True)
        parser.add_argument("--customers", type=int, default=80)

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("verify_busy_day is disabled in production.")

        try:
            target_date = date.fromisoformat(options["target_date"])
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc

        expected_customers = int(options["customers"])
        errors = []
        warnings = []

        try:
            branch = Branch.objects.get(branch_code=SCENARIO_BRANCH_CODE)
        except Branch.DoesNotExist as exc:
            raise CommandError("Training branch ML01 is missing. Run seed_busy_day first.") from exc

        if not branch.is_active:
            errors.append("Training branch is inactive.")
        if branch.opening_time != time(8, 0):
            errors.append(f"Training branch opens at {branch.opening_time}, expected 08:00.")

        prefix = scenario_customer_prefix(target_date)
        bookings = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=target_date,
            branch=branch,
        ).select_related("user", "service", "queueticket")

        if bookings.count() != expected_customers:
            errors.append(
                f"Expected {expected_customers} synthetic bookings, found {bookings.count()}."
            )

        tickets = QueueTicket.objects.filter(booking__in=bookings)
        expected_priority = max(1, round(expected_customers * 0.10))
        priority_count = tickets.filter(queue_type=QueueTicket.PRIORITY).count()
        general_count = tickets.filter(queue_type=QueueTicket.GENERAL).count()
        if priority_count != expected_priority:
            errors.append(
                f"Expected {expected_priority} Priority tickets, found {priority_count}."
            )
        if general_count != expected_customers - expected_priority:
            errors.append(
                f"Expected {expected_customers - expected_priority} General tickets, "
                f"found {general_count}."
            )

        if bookings.filter(checked_in_at__isnull=False).exists():
            errors.append("At least one synthetic booking is already checked in.")
        if tickets.exclude(status=QueueTicket.SCHEDULED).exists():
            errors.append("At least one synthetic ticket is not in SCHEDULED state.")
        if QueueForecastObservation.objects.filter(ticket__in=tickets).exists():
            errors.append("Forecast observations already exist; reset before the live run.")

        appointment_times = set(bookings.values_list("booking_time", flat=True))
        for checkpoint in (time(8, 0), time(10, 0), time(11, 0), time(14, 0)):
            if checkpoint not in appointment_times:
                errors.append(f"No booking exists at required checkpoint {checkpoint:%H:%M}.")

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
                        f"Counter {counter.counter_number} is {counter.status}; expected closed before 08:00."
                    )
                if counter.assigned_staff_id is None:
                    errors.append(f"Counter {counter.counter_number} has no assigned staff member.")
                    continue
                try:
                    profile = counter.assigned_staff.profile
                except Profile.DoesNotExist:
                    errors.append(
                        f"Counter {counter.counter_number} staff has no Smart Q profile."
                    )
                    continue
                if profile.role != Profile.COUNTER_STAFF:
                    errors.append(
                        f"Counter {counter.counter_number} is not assigned to Counter Staff."
                    )
                if profile.branch_id != branch.id:
                    errors.append(
                        f"Counter {counter.counter_number} staff belongs to the wrong branch."
                    )

        opening_bookings = list(bookings.filter(booking_time=time(8, 0)))
        opening_general = sum(
            booking.queueticket.queue_type == QueueTicket.GENERAL
            for booking in opening_bookings
        )
        opening_priority = sum(
            booking.queueticket.queue_type == QueueTicket.PRIORITY
            for booking in opening_bookings
        )
        if opening_general < 2 or opening_priority < 1:
            errors.append(
                "08:00 must contain at least two General and one Priority arrival so all counters can start."
            )

        for service_code in SERVICE_SEQUENCE:
            service_bookings = list(
                bookings.filter(service__service_code=service_code).select_related("user")
            )
            if not service_bookings:
                errors.append(f"No bookings exist for service {service_code}.")
                continue
            target = SERVICE_PROFILES[service_code]["average_minutes"]
            planned = [
                planned_service_minutes(
                    booking.user.username,
                    service_code,
                    target_date,
                )
                for booking in service_bookings
            ]
            if not any(value < target for value in planned):
                errors.append(f"{service_code} has no early-finish examples.")
            if target not in planned:
                errors.append(f"{service_code} has no exactly-on-target examples.")
            if not any(value > target for value in planned):
                errors.append(f"{service_code} has no overrun examples.")

        try:
            manager = User.objects.select_related("profile").get(
                username=SCENARIO_MANAGER_USERNAME
            )
        except User.DoesNotExist:
            warnings.append("Training Branch Manager observer account is missing.")
        else:
            if manager.profile.role != Profile.BRANCH_MANAGER or manager.profile.branch_id != branch.id:
                errors.append("Training observer account is not a Branch Manager for ML01.")
            if SCENARIO_MANAGER_PASSWORD:
                if not manager.has_usable_password():
                    errors.append(
                        "SMARTQ_TRAINING_MANAGER_PASSWORD is set but the observer account has no usable password; reseed."
                    )
            elif manager.has_usable_password():
                warnings.append(
                    "Observer manager has a usable password from an earlier seed. Reset the scenario if this was not intentional."
                )
            else:
                warnings.append(
                    "Observer login is disabled. Set SMARTQ_TRAINING_MANAGER_PASSWORD before seeding if you want the Branch Manager UI tomorrow."
                )

        self.stdout.write(f"Busy-day preflight for {target_date}")
        self.stdout.write(
            f"Customers: {bookings.count()} | General: {general_count} | Priority: {priority_count}"
        )
        self.stdout.write(f"Counters: {len(counters)} | Branch: {branch.name}")
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f"ERROR: {error}"))
            raise CommandError(
                f"Busy-day preflight failed with {len(errors)} blocking issue(s)."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "READY: the Smart Q busy-day scenario is structurally ready for the 08:00 live run."
            )
        )
