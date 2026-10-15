import os
import random
import time as wall_clock
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from counters.services import open_counter, resume_counter
from queues.busy_day import (
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    activate_simulation_booking,
    planned_service_minutes,
)
from queues.models import QueueTicket
from queues.services import (
    call_next_ticket,
    complete_current_ticket,
    create_queue_ticket_for_booking,
    get_current_ticket,
)
from services.models import BranchService, Service


SCENARIO_VERSION = "pretoria-live-study-v1"
DEFAULT_BRANCH_CODE = "PTA01"
CUSTOMER_PREFIX = "ptastudy_"


class Command(BaseCommand):
    help = (
        "Run a small real-time Pretoria Central queue study against the normal "
        "Smart Q queue lifecycle. Intended only for an explicitly enabled demo."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="target_date", required=True)
        parser.add_argument("--start-time", default="02:00")
        parser.add_argument("--customers", type=int, default=15)
        parser.add_argument("--priority", type=int, default=5)
        parser.add_argument("--window-minutes", type=int, default=90)
        parser.add_argument("--poll-seconds", type=float, default=2.0)
        parser.add_argument("--branch-code", default=DEFAULT_BRANCH_CODE)
        parser.add_argument("--prepare-only", action="store_true")

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False) and not self._env_bool(
            "SMARTQ_ALLOW_LIVE_STUDY"
        ):
            raise CommandError(
                "Production live study is disabled. Set SMARTQ_ALLOW_LIVE_STUDY=true "
                "only for an intentional presentation/demo run."
            )

        target_date = self._parse_date(options["target_date"])
        start_time = self._parse_time(options["start_time"])
        customer_count = int(options["customers"])
        priority_count = int(options["priority"])
        window_minutes = int(options["window_minutes"])
        poll_seconds = max(float(options["poll_seconds"]), 0.5)

        if customer_count < 1:
            raise CommandError("--customers must be at least 1.")
        if priority_count < 0 or priority_count > customer_count:
            raise CommandError("--priority must be between 0 and --customers.")
        if window_minutes < 1:
            raise CommandError("--window-minutes must be positive.")

        branch = self._get_branch(options["branch_code"])
        services = self._get_services(branch)
        self._ensure_receptionist_scope(branch)
        counters = self._prepare_counter_staff(branch)

        start_at = timezone.make_aware(
            datetime.combine(target_date, start_time),
            timezone.get_current_timezone(),
        )
        end_of_arrivals = start_at + timedelta(minutes=window_minutes)
        self._seed_scenario(
            branch=branch,
            services=services,
            target_date=target_date,
            start_at=start_at,
            customer_count=customer_count,
            priority_count=priority_count,
            window_minutes=window_minutes,
        )

        if options.get("prepare_only"):
            self.stdout.write(
                self.style.SUCCESS(
                    "PREPARED — Pretoria Central study data is ready; counters remain closed until start time."
                )
            )
            return

        now = timezone.now()
        if now > end_of_arrivals + timedelta(hours=4):
            self.stdout.write(
                self.style.WARNING(
                    "Pretoria live study target window is already too old; nothing was started."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Pretoria Central live study armed for {timezone.localtime(start_at):%Y-%m-%d %H:%M}."
            )
        )
        self.stdout.write(
            f"{customer_count} synthetic customers, exactly {priority_count} priority, "
            f"arrivals spread across {window_minutes} minutes."
        )
        self.stdout.write(
            "All Pretoria Central counters will open at start time. Real customer/walk-in "
            "tickets can join the same queue and will be processed through the same lifecycle."
        )

        last_wait_minute = None
        opened = False

        while True:
            close_old_connections()
            now = timezone.now()

            if now < start_at:
                minutes_left = max(int((start_at - now).total_seconds() // 60), 0)
                if minutes_left != last_wait_minute:
                    self.stdout.write(
                        f"Waiting for {timezone.localtime(start_at):%H:%M} — "
                        f"approximately {minutes_left} min remaining."
                    )
                    last_wait_minute = minutes_left
                wall_clock.sleep(min(poll_seconds, 10.0))
                continue

            if not opened:
                counters = self._prepare_counter_staff(branch)
                self._open_all_counters(counters)
                opened = True

            self._activate_due_synthetic_bookings(
                branch=branch,
                target_date=target_date,
                now=now,
            )
            self._complete_due_services(counters, target_date)
            self._fill_free_counters(counters, target_date)

            synthetic_remaining = (
                Booking.objects.filter(
                    user__username__startswith=self._prefix(target_date),
                    booking_date=target_date,
                    branch=branch,
                )
                .exclude(status__in=[Booking.COMPLETED, Booking.CANCELLED, Booking.NO_SHOW])
                .count()
            )
            branch_active = QueueTicket.objects.filter(
                booking__branch=branch,
                booking__booking_date=target_date,
                status__in=[QueueTicket.WAITING, QueueTicket.SERVING],
            ).count()

            if synthetic_remaining == 0 and branch_active == 0 and now >= end_of_arrivals:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Pretoria Central live study complete. Counters are intentionally left open "
                        "for continued manual observation."
                    )
                )
                return

            wall_clock.sleep(poll_seconds)

    @staticmethod
    def _env_bool(name):
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_date(raw):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc

    @staticmethod
    def _parse_time(raw):
        try:
            return time.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError("--start-time must use HH:MM format.") from exc

    @staticmethod
    def _prefix(target_date):
        return f"{CUSTOMER_PREFIX}{target_date:%Y%m%d}_"

    def _username(self, target_date, index):
        return f"{self._prefix(target_date)}{index:03d}"

    @staticmethod
    def _get_branch(branch_code):
        try:
            return Branch.objects.get(branch_code=branch_code, is_active=True)
        except Branch.DoesNotExist as exc:
            raise CommandError(
                f"Active branch {branch_code!r} was not found. The study will not create "
                "or overwrite the real branch."
            ) from exc

    @staticmethod
    def _get_services(branch):
        services = {}
        for service_code in SERVICE_SEQUENCE:
            try:
                service = Service.objects.get(service_code=service_code, is_active=True)
            except Service.DoesNotExist as exc:
                raise CommandError(
                    f"Required live service {service_code} is missing or inactive."
                ) from exc

            if not BranchService.objects.filter(
                branch=branch,
                service=service,
                is_active=True,
            ).exists():
                raise CommandError(
                    f"{service.name} is not active at {branch.name}; study aborted."
                )
            services[service_code] = service
        return services

    @staticmethod
    def _ensure_receptionist_scope(branch):
        try:
            receptionist = User.objects.get(username="reception_demo")
            profile = receptionist.profile
        except (User.DoesNotExist, Profile.DoesNotExist) as exc:
            raise CommandError(
                "reception_demo is missing. Run the normal demo bootstrap first."
            ) from exc

        changed = []
        if profile.role != Profile.RECEPTIONIST:
            profile.role = Profile.RECEPTIONIST
            changed.append("role")
        if profile.branch_id != branch.id:
            profile.branch = branch
            changed.append("branch")
        if changed:
            profile.save(update_fields=changed)

    def _ensure_counter_user(self, branch, counter):
        username = f"ptastudy_counter_{counter.counter_number}"
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = "Study"
        user.last_name = f"Counter {counter.counter_number}"
        user.email = f"{username}@simulation.smartq.local"
        user.is_active = True
        user.set_unusable_password()
        user.save()

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                "date_of_birth": date(1990, 1, 1),
                "gender": Profile.OTHER,
                "disability_status": False,
                "role": Profile.COUNTER_STAFF,
                "branch": branch,
            },
        )
        profile.date_of_birth = date(1990, 1, 1)
        profile.gender = Profile.OTHER
        profile.disability_status = False
        profile.role = Profile.COUNTER_STAFF
        profile.branch = branch
        profile.save()
        return user

    def _prepare_counter_staff(self, branch):
        counters = list(
            Counter.objects.filter(branch=branch)
            .select_related("assigned_staff", "assigned_staff__profile")
            .order_by("counter_number", "id")
        )
        if not counters:
            raise CommandError(f"{branch.name} has no counters.")

        for counter in counters:
            if counter.assigned_staff_id is not None:
                continue
            user = self._ensure_counter_user(branch, counter)
            Counter.objects.filter(assigned_staff=user).exclude(pk=counter.pk).update(
                assigned_staff=None
            )
            counter.assigned_staff = user
            counter.save(update_fields=["assigned_staff"])
        return list(
            Counter.objects.filter(branch=branch)
            .select_related("assigned_staff", "assigned_staff__profile")
            .order_by("counter_number", "id")
        )

    def _open_all_counters(self, counters):
        for counter in counters:
            counter.refresh_from_db()
            if counter.assigned_staff_id is None:
                raise CommandError(
                    f"Counter {counter.counter_number} is still unassigned."
                )
            if counter.status == Counter.OPEN:
                continue
            if counter.status == Counter.PAUSED:
                counter, error = resume_counter(
                    counter,
                    actor=counter.assigned_staff,
                )
            else:
                counter, error = open_counter(
                    counter,
                    actor=counter.assigned_staff,
                )
            if error not in (None, "already_open"):
                raise CommandError(
                    f"Could not open Counter {counter.counter_number}: {error}."
                )
            self.stdout.write(
                f"OPEN — Counter {counter.counter_number} ({counter.queue_type})."
            )

    def _seed_scenario(
        self,
        *,
        branch,
        services,
        target_date,
        start_at,
        customer_count,
        priority_count,
        window_minutes,
    ):
        prefix = self._prefix(target_date)
        priority_indexes = set(
            random.Random(
                f"{SCENARIO_VERSION}:{target_date.isoformat()}:{branch.branch_code}"
            ).sample(range(customer_count), priority_count)
        )
        priority_rank = {
            position: rank for rank, position in enumerate(sorted(priority_indexes))
        }

        for zero_index in range(customer_count):
            index = zero_index + 1
            username = self._username(target_date, index)
            offset_minutes = (window_minutes * zero_index) / customer_count
            scheduled_at = start_at + timedelta(minutes=offset_minutes)
            local_scheduled = timezone.localtime(scheduled_at)

            is_priority = zero_index in priority_indexes
            rank = priority_rank.get(zero_index, -1)
            if is_priority and rank % 3 == 0:
                dob = date(1960, 1, 1)
                gender = Profile.MALE
                disability = False
                pregnant = False
            elif is_priority and rank % 3 == 1:
                dob = date(1988, 1, 1)
                gender = Profile.OTHER
                disability = True
                pregnant = False
            elif is_priority:
                dob = date(1992, 1, 1)
                gender = Profile.FEMALE
                disability = False
                pregnant = True
            else:
                dob = date(1985 + (index % 18), ((index - 1) % 12) + 1, 15)
                gender = (Profile.MALE, Profile.FEMALE, Profile.OTHER)[index % 3]
                disability = False
                pregnant = False

            user = self._ensure_customer(
                username=username,
                index=index,
                dob=dob,
                gender=gender,
                disability=disability,
            )
            service_code = SERVICE_SEQUENCE[zero_index % len(SERVICE_SEQUENCE)]
            service = services[service_code]

            booking = Booking.objects.filter(
                user=user,
                booking_date=target_date,
                branch=branch,
            ).first()
            if booking is None:
                booking = Booking.objects.create(
                    user=user,
                    branch=branch,
                    service=service,
                    booking_date=target_date,
                    booking_time=local_scheduled.time().replace(
                        second=0,
                        microsecond=0,
                    ),
                    is_pregnant=pregnant,
                    status=Booking.PENDING,
                    source=Booking.ONLINE,
                )
                create_queue_ticket_for_booking(booking, record_event=True)

        seeded = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=target_date,
            branch=branch,
        ).count()
        if seeded != customer_count:
            raise CommandError(
                f"Expected {customer_count} seeded study bookings, found {seeded}."
            )

        actual_priority = QueueTicket.objects.filter(
            booking__user__username__startswith=prefix,
            booking__booking_date=target_date,
            queue_type=QueueTicket.PRIORITY,
        ).count()
        if actual_priority != priority_count:
            raise CommandError(
                f"Expected {priority_count} priority tickets, found {actual_priority}."
            )

        self.stdout.write(
            f"SEEDED — {seeded} Pretoria Central appointments; "
            f"{actual_priority} priority and {seeded - actual_priority} general."
        )
        self.stdout.write(
            "Priority positions (arrival order): "
            + ", ".join(str(i + 1) for i in sorted(priority_indexes))
        )

    @staticmethod
    def _ensure_customer(*, username, index, dob, gender, disability):
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = "Study"
        user.last_name = f"Customer {index:02d}"
        user.email = f"{username}@simulation.smartq.local"
        user.is_active = True
        user.set_unusable_password()
        user.save()

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                "date_of_birth": dob,
                "gender": gender,
                "disability_status": disability,
                "role": Profile.CUSTOMER,
                "branch": None,
            },
        )
        profile.date_of_birth = dob
        profile.gender = gender
        profile.disability_status = disability
        profile.role = Profile.CUSTOMER
        profile.branch = None
        profile.save()
        return user

    def _activate_due_synthetic_bookings(self, *, branch, target_date, now):
        prefix = self._prefix(target_date)
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
            scheduled_at = timezone.make_aware(
                datetime.combine(booking.booking_date, booking.booking_time),
                timezone.get_current_timezone(),
            )
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
                    f"{ticket.queue_number} / {booking.service.name} / "
                    f"{ticket.queue_type}."
                )

    def _planned_minutes_for_ticket(self, ticket, target_date):
        username = ticket.booking.user.username if ticket.booking.user_id else ""
        if username.startswith(self._prefix(target_date)):
            code = ticket.booking.service.service_code
            if code in SERVICE_PROFILES:
                return planned_service_minutes(username, code, target_date)

        target = max(float(ticket.booking.service.average_service_time or 1), 1.0)
        factors = (0.8, 1.0, 1.2, 0.9, 1.1)
        factor = factors[ticket.id % len(factors)]
        return max(int(round(target * factor)), 1)

    def _complete_due_services(self, counters, target_date):
        now = timezone.now()
        for counter in counters:
            counter.refresh_from_db()
            ticket = get_current_ticket(counter)
            if ticket is None or ticket.service_started_at is None:
                continue

            planned_minutes = self._planned_minutes_for_ticket(ticket, target_date)
            elapsed = (now - ticket.service_started_at).total_seconds()
            if elapsed < planned_minutes * 60:
                continue

            completed = complete_current_ticket(
                counter,
                actor=counter.assigned_staff,
            )
            if completed is None:
                continue
            self.stdout.write(
                f"COMPLETE — {completed.queue_number} at Counter "
                f"{counter.counter_number}: actual "
                f"{(completed.actual_service_seconds or 0) / 60:.1f} min."
            )

    def _fill_free_counters(self, counters, target_date):
        for counter in counters:
            counter.refresh_from_db()
            if counter.status != Counter.OPEN:
                continue
            if get_current_ticket(counter) is not None:
                continue

            ticket = call_next_ticket(
                counter,
                booking_date=target_date,
                actor=counter.assigned_staff,
            )
            if ticket is None:
                continue

            planned_minutes = self._planned_minutes_for_ticket(ticket, target_date)
            label = (
                ticket.booking.user.username
                if ticket.booking.user_id
                else "guest walk-in"
            )
            self.stdout.write(
                f"CALL — Counter {counter.counter_number} serving "
                f"{ticket.queue_number} ({label}, {ticket.booking.service.name}); "
                f"planned live service {planned_minutes} min."
            )
