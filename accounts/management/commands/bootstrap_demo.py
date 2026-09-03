from datetime import date, time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueTicket
from services.models import BranchService, Service


DEMO_PASSWORD = "SmartQDemo2026!"


class Command(BaseCommand):
    help = "Create or refresh a safe local Smart Q demo environment with all operational roles."

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False):
            raise CommandError("bootstrap_demo is disabled in production.")

        with transaction.atomic():
            pretoria, _ = Branch.objects.update_or_create(
                branch_code="PTA01",
                defaults={
                    "name": "Pretoria Central",
                    "address": "230 Johannes Ramokhoase Street",
                    "city": "Pretoria",
                    "opening_time": time(8, 0),
                    "closing_time": time(16, 30),
                    "is_active": True,
                },
            )
            centurion, _ = Branch.objects.update_or_create(
                branch_code="CEN01",
                defaults={
                    "name": "Centurion Service Centre",
                    "address": "1269 Gordon Hood Road",
                    "city": "Centurion",
                    "opening_time": time(8, 0),
                    "closing_time": time(16, 30),
                    "is_active": True,
                },
            )

            id_service, _ = Service.objects.update_or_create(
                service_code="IDAPP",
                defaults={
                    "name": "ID Applications",
                    "description": "Identity document applications and related service.",
                    "average_service_time": 15,
                    "is_active": True,
                },
            )
            passport_service, _ = Service.objects.update_or_create(
                service_code="PASSPORT",
                defaults={
                    "name": "Passport Applications",
                    "description": "Passport applications and related service.",
                    "average_service_time": 20,
                    "is_active": True,
                },
            )
            collections_service, _ = Service.objects.update_or_create(
                service_code="COLLECT",
                defaults={
                    "name": "Collections",
                    "description": "Document and application collections.",
                    "average_service_time": 10,
                    "is_active": True,
                },
            )

            for branch, service, capacity in (
                (pretoria, id_service, 4),
                (pretoria, passport_service, 3),
                (pretoria, collections_service, 6),
                (centurion, id_service, 3),
                (centurion, passport_service, 2),
                (centurion, collections_service, 5),
            ):
                BranchService.objects.update_or_create(
                    branch=branch,
                    service=service,
                    defaults={"max_bookings_per_slot": capacity, "is_active": True},
                )

            users = {
                "customer": self.ensure_user(
                    "customer_demo",
                    "Demo",
                    "Customer",
                    Profile.CUSTOMER,
                    branch=None,
                ),
                "receptionist": self.ensure_user(
                    "reception_demo",
                    "Demo",
                    "Receptionist",
                    Profile.RECEPTIONIST,
                    branch=pretoria,
                ),
                "counter": self.ensure_user(
                    "counter_demo",
                    "Demo",
                    "Counter Staff",
                    Profile.COUNTER_STAFF,
                    branch=pretoria,
                ),
                "manager": self.ensure_user(
                    "manager_demo",
                    "Demo",
                    "Manager",
                    Profile.BRANCH_MANAGER,
                    branch=pretoria,
                ),
                "admin": self.ensure_user(
                    "admin_demo",
                    "Demo",
                    "Administrator",
                    Profile.SYSTEM_ADMIN,
                    branch=None,
                ),
            }

            pta_general, _ = Counter.objects.update_or_create(
                branch=pretoria,
                counter_number="1",
                defaults={
                    "queue_type": QueueTicket.GENERAL,
                    "status": Counter.CLOSED,
                },
            )
            Counter.objects.update_or_create(
                branch=pretoria,
                counter_number="2",
                defaults={
                    "queue_type": QueueTicket.GENERAL,
                    "status": Counter.CLOSED,
                },
            )
            Counter.objects.update_or_create(
                branch=pretoria,
                counter_number="3",
                defaults={
                    "queue_type": QueueTicket.PRIORITY,
                    "status": Counter.CLOSED,
                },
            )
            Counter.objects.update_or_create(
                branch=centurion,
                counter_number="1",
                defaults={
                    "queue_type": QueueTicket.GENERAL,
                    "status": Counter.CLOSED,
                },
            )
            Counter.objects.update_or_create(
                branch=centurion,
                counter_number="2",
                defaults={
                    "queue_type": QueueTicket.PRIORITY,
                    "status": Counter.CLOSED,
                },
            )

            Counter.objects.filter(assigned_staff=users["counter"]).exclude(
                pk=pta_general.pk
            ).update(assigned_staff=None)
            pta_general.assigned_staff = users["counter"]
            pta_general.status = Counter.CLOSED
            pta_general.save(update_fields=["assigned_staff", "status"])

        self.stdout.write(self.style.SUCCESS("Smart Q demo environment is ready."))
        self.stdout.write("")
        self.stdout.write(f"Password for every demo account: {DEMO_PASSWORD}")
        self.stdout.write("customer_demo   -> Customer")
        self.stdout.write("reception_demo  -> Receptionist")
        self.stdout.write("counter_demo    -> Counter Staff (Pretoria Counter 1)")
        self.stdout.write("manager_demo    -> Branch Manager (Pretoria Central)")
        self.stdout.write("admin_demo      -> System Admin")
        self.stdout.write("")
        self.stdout.write("Branches: Pretoria Central, Centurion Service Centre")
        self.stdout.write("Services: ID Applications, Passport Applications, Collections")

    def ensure_user(self, username, first_name, last_name, role, branch):
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = first_name
        user.last_name = last_name
        user.email = f"{username}@smartq.local"
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()

        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                "date_of_birth": date(1990, 1, 1),
                "gender": Profile.OTHER,
                "disability_status": False,
                "role": role,
                "branch": branch,
            },
        )
        profile.date_of_birth = date(1990, 1, 1)
        profile.gender = Profile.OTHER
        profile.disability_status = False
        profile.role = role
        profile.branch = branch
        profile.save()
        return user
