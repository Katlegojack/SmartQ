from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.busy_day import (
    SCENARIO_BRANCH_CODE,
    SCENARIO_BRANCH_NAME,
    SCENARIO_MANAGER_PASSWORD,
    SCENARIO_MANAGER_USERNAME,
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    STAFF_SPECS,
    appointment_slots,
    planned_service_minutes,
    priority_positions,
    scenario_customer_prefix,
    scenario_username,
    service_code_for_index,
)
from queues.models import QueueEvent, QueueForecastObservation, QueueNumberSequence, QueueTicket
from queues.services import create_queue_ticket_for_booking
from services.models import BranchService, Service


class Command(BaseCommand):
    help = "Seed a non-production Smart Q busy-day scenario for queue/forecast training."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Scenario date in YYYY-MM-DD format. Defaults to tomorrow in Smart Q local time.",
        )
        parser.add_argument("--customers", type=int, default=80)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("seed_busy_day is disabled in production.")

        target_date = self._parse_date(options.get("target_date"))
        customer_count = options["customers"]
        if customer_count < 10:
            raise CommandError("Use at least 10 customers so the priority/general mix remains meaningful.")

        prefix = scenario_customer_prefix(target_date)
        if User.objects.filter(username__startswith=prefix).exists():
            if not options["reset"]:
                raise CommandError(
                    f"Busy-day customers already exist for {target_date}. "
                    "Run again with --reset to rebuild this scenario."
                )
            self._reset_existing_scenario(target_date, prefix)

        with transaction.atomic():
            branch = self._ensure_branch()
            services = self._ensure_services(branch)
            staff = self._ensure_staff(branch)
            self._ensure_counters(branch, staff)
            self._ensure_manager(branch)
            self._create_customers_and_bookings(
                branch=branch,
                services=services,
                target_date=target_date,
                customer_count=customer_count,
            )

        tickets = QueueTicket.objects.filter(
            booking__user__username__startswith=prefix,
            booking__booking_date=target_date,
        )
        priority_count = tickets.filter(queue_type=QueueTicket.PRIORITY).count()
        general_count = tickets.filter(queue_type=QueueTicket.GENERAL).count()

        self.stdout.write(self.style.SUCCESS("Smart Q busy-day scenario is ready."))
        self.stdout.write(f"Date: {target_date}")
        self.stdout.write(f"Branch: {SCENARIO_BRANCH_NAME} ({SCENARIO_BRANCH_CODE})")
        self.stdout.write(f"Customers: {tickets.count()} = {general_count} general + {priority_count} priority")
        self.stdout.write("Counters: 2 General + 1 Priority")
        self.stdout.write("Appointments: 08:00 through 15:45 in 15-minute slots")
        self.stdout.write("")
        self.stdout.write("Service targets and planned variation:")
        for service_code in SERVICE_SEQUENCE:
            profile = SERVICE_PROFILES[service_code]
            values = []
            for booking in Booking.objects.filter(
                user__username__startswith=prefix,
                booking_date=target_date,
                service__service_code=service_code,
            ).select_related("user", "service"):
                values.append(
                    planned_service_minutes(
                        booking.user.username,
                        service_code,
                        target_date,
                    )
                )
            self.stdout.write(
                f"  {profile['name']}: target {profile['average_minutes']} min; "
                f"planned range {min(values)}-{max(values)} min"
            )
        self.stdout.write("")
        self.stdout.write(
            f"Observer login: {SCENARIO_MANAGER_USERNAME} / {SCENARIO_MANAGER_PASSWORD}"
        )
        self.stdout.write(
            f"Run: python manage.py run_busy_day --date {target_date}"
        )

    def _parse_date(self, raw):
        if not raw:
            return timezone.localdate() + timedelta(days=1)
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD format.") from exc

    def _reset_existing_scenario(self, target_date, prefix):
        users = User.objects.filter(username__startswith=prefix)
        bookings = Booking.objects.filter(user__in=users, booking_date=target_date)
        ticket_ids = list(
            QueueTicket.objects.filter(booking__in=bookings).values_list("id", flat=True)
        )
        booking_ids = list(bookings.values_list("id", flat=True))
        QueueEvent.objects.filter(ticket_id__in=ticket_ids).delete()
        QueueEvent.objects.filter(booking_id__in=booking_ids).delete()
        QueueForecastObservation.objects.filter(ticket_id__in=ticket_ids).delete()
        users.delete()
        QueueNumberSequence.objects.filter(
            branch__branch_code=SCENARIO_BRANCH_CODE,
            booking_date=target_date,
        ).delete()

    def _ensure_branch(self):
        branch, _ = Branch.objects.update_or_create(
            branch_code=SCENARIO_BRANCH_CODE,
            defaults={
                "name": SCENARIO_BRANCH_NAME,
                "address": "Synthetic training environment",
                "city": "Pretoria",
                "opening_time": time(8, 0),
                "closing_time": time(18, 0),
                "is_active": True,
            },
        )
        return branch

    def _ensure_services(self, branch):
        descriptions = {
            "COLLECT": "Synthetic document collection workload for Smart Q training.",
            "IDAPP": "Synthetic identity application workload for Smart Q training.",
            "PASSPORT": "Synthetic passport application workload for Smart Q training.",
        }
        services = {}
        for service_code in SERVICE_SEQUENCE:
            profile = SERVICE_PROFILES[service_code]
            service, _ = Service.objects.update_or_create(
                service_code=service_code,
                defaults={
                    "name": profile["name"],
                    "description": descriptions[service_code],
                    "average_service_time": profile["average_minutes"],
                    "is_active": True,
                },
            )
            BranchService.objects.update_or_create(
                branch=branch,
                service=service,
                defaults={"max_bookings_per_slot": 4, "is_active": True},
            )
            services[service_code] = service
        return services

    def _ensure_user_profile(
        self,
        *,
        username,
        first_name,
        last_name,
        role,
        branch,
        date_of_birth,
        gender,
        disability_status,
        usable_password=None,
    ):
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = first_name
        user.last_name = last_name
        user.email = f"{username}@simulation.smartq.local"
        user.is_active = True
        if usable_password:
            user.set_password(usable_password)
        else:
            user.set_unusable_password()
        user.save()

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                "date_of_birth": date_of_birth,
                "gender": gender,
                "disability_status": disability_status,
                "role": role,
                "branch": branch,
            },
        )
        profile.date_of_birth = date_of_birth
        profile.gender = gender
        profile.disability_status = disability_status
        profile.role = role
        profile.branch = branch
        profile.save()
        return user

    def _ensure_staff(self, branch):
        users = {}
        for username, first_name, last_name, queue_type, counter_number in STAFF_SPECS:
            users[username] = self._ensure_user_profile(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=Profile.COUNTER_STAFF,
                branch=branch,
                date_of_birth=date(1990, 1, 1),
                gender=Profile.OTHER,
                disability_status=False,
            )
        return users

    def _ensure_manager(self, branch):
        return self._ensure_user_profile(
            username=SCENARIO_MANAGER_USERNAME,
            first_name="Training",
            last_name="Manager",
            role=Profile.BRANCH_MANAGER,
            branch=branch,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            disability_status=False,
            usable_password=SCENARIO_MANAGER_PASSWORD,
        )

    def _ensure_counters(self, branch, staff):
        for username, _first, _last, queue_type, counter_number in STAFF_SPECS:
            staff_user = staff[username]
            Counter.objects.filter(assigned_staff=staff_user).exclude(
                branch=branch,
                counter_number=counter_number,
            ).update(assigned_staff=None)
            counter, _ = Counter.objects.update_or_create(
                branch=branch,
                counter_number=counter_number,
                defaults={
                    "queue_type": queue_type,
                    "status": Counter.CLOSED,
                },
            )
            counter.queue_type = queue_type
            counter.status = Counter.CLOSED
            counter.assigned_staff = staff_user
            counter.save(update_fields=["queue_type", "status", "assigned_staff"])

    def _create_customers_and_bookings(
        self,
        *,
        branch,
        services,
        target_date,
        customer_count,
    ):
        slots = appointment_slots(customer_count)
        priority_indexes = priority_positions(customer_count)
        priority_rank = {position: rank for rank, position in enumerate(sorted(priority_indexes))}

        for zero_index, booking_time in enumerate(slots):
            index = zero_index + 1
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
                dob = date(1980 + (index % 20), ((index - 1) % 12) + 1, 15)
                gender = (Profile.MALE, Profile.FEMALE, Profile.OTHER)[index % 3]
                disability = False
                pregnant = False

            username = scenario_username(target_date, index)
            user = self._ensure_user_profile(
                username=username,
                first_name="Simulation",
                last_name=f"Customer {index:03d}",
                role=Profile.CUSTOMER,
                branch=None,
                date_of_birth=dob,
                gender=gender,
                disability_status=disability,
            )
            service_code = service_code_for_index(index)
            booking = Booking.objects.create(
                user=user,
                branch=branch,
                service=services[service_code],
                booking_date=target_date,
                booking_time=booking_time,
                is_pregnant=pregnant,
                status=Booking.PENDING,
                source=Booking.ONLINE,
            )
            create_queue_ticket_for_booking(booking, record_event=True)
