from django.core.management.base import BaseCommand

from notifications.services import create_due_check_in_reminders


class Command(BaseCommand):
    help = "Create due hourly check-in reminders and cancel expired unchecked bookings."

    def handle(self, *args, **options):
        result = create_due_check_in_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                "Check-in reminder processing complete: "
                f"created={result['created']}, cancelled={result['cancelled']}"
            )
        )
