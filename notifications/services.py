from datetime import timedelta

from django.utils import timezone

from bookings.models import Booking
from queues.disruptions import (
    get_unnotified_disruption_impact,
    mark_disruption_impact_notified,
)
from queues.models import QueueDisruptionImpact
from queues.services import (
    cancel_expired_unchecked_booking,
    get_booking_datetime,
    get_check_in_opens_at,
)
from .models import Notification


def create_notification_for_impact(impact):
    if impact is None:
        return {
            "notification": None,
            "created": False,
        }

    ticket = impact.ticket
    if ticket is None or ticket.booking is None or ticket.booking.user_id is None:
        return {
            "notification": None,
            "created": False,
        }

    user = ticket.booking.user

    if impact.impact_type == QueueDisruptionImpact.RESCHEDULE_RISK:
        title = "Possible reschedule"
        notification_type = Notification.RESCHEDULE
        default_message = "You may need to be rescheduled due to a service disruption."
    else:
        title = "Queue Disruption"
        notification_type = Notification.DISRUPTION
        default_message = "Your queue was affected by a service disruption."

    message = impact.message or default_message

    notification, created = Notification.objects.get_or_create(
        related_impact=impact,
        defaults={
            "user": user,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "related_ticket": ticket,
        },
    )

    if impact.is_notified is False:
        mark_disruption_impact_notified(impact)

    return {
        "notification": notification,
        "created": created,
    }


def create_notification_for_unnotified_impacts(queue_pause=None):
    impacts = get_unnotified_disruption_impact(queue_pause)
    notifications_created = 0
    notifications_processed = 0

    for impact in impacts:
        result = create_notification_for_impact(impact)

        if result["notification"] is not None:
            notifications_processed += 1

        if result["created"]:
            notifications_created += 1

    return {
        "notification_processed": notifications_processed,
        "notification_created": notifications_created,
    }


def get_user_notification(user):
    if user is None:
        return Notification.objects.none()
    return Notification.objects.filter(user=user)


def get_unread_notification(user):
    if user is None:
        return Notification.objects.none()
    return Notification.objects.filter(user=user, is_read=False)


def get_unread_notification_count(user):
    if user is None:
        return 0
    return get_unread_notification(user).count()


def mark_notification_as_read(notification):
    if notification is None:
        return None
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return notification


def mark_all_notification_as_read(user):
    if user is None:
        return 0
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)


def create_reschedule_applied_notification(recommendation):
    if recommendation is None:
        return {
            "notification": None,
            "created": False,
        }

    booking = recommendation.booking
    ticket = recommendation.ticket

    # Guest walk-ins do not have an account inbox. External/guest notification
    # delivery is a later channel decision.
    if booking is None or ticket is None or booking.user_id is None:
        return {
            "notification": None,
            "created": False,
        }

    user = booking.user
    title = "Reschedule confirmed"
    message = (
        f"Your booking has been rescheduled to {booking.booking_date} at "
        f"{booking.booking_time}. Your new queue is {ticket.queue_number}."
    )

    notification, created = Notification.objects.get_or_create(
        user=user,
        title=title,
        notification_type=Notification.RESCHEDULE,
        related_ticket=ticket,
        defaults={"message": message},
    )

    return {
        "notification": notification,
        "created": created,
    }


def get_check_in_reminder_slots(booking):
    """
    Return the six hourly reminder slots before an appointment.

    For a 15:00 appointment, reminders are eligible at 09:00, 10:00, 11:00,
    12:00, 13:00 and 14:00. The appointment time itself is the cancellation
    deadline when no check-in happened.
    """
    opens_at = get_check_in_opens_at(booking)
    appointment_at = get_booking_datetime(booking)
    slots = []
    current = opens_at

    while current < appointment_at:
        slots.append(current)
        current += timedelta(hours=1)

    return slots


def create_due_check_in_reminders(now=None):
    """
    Generate all reminder slots that are due and have not already been created.

    This function is deliberately scheduler-agnostic. A management command can
    run it hourly now; production can later call the same service from Celery,
    cron, a cloud scheduler, or another approved job runner.
    """
    if now is None:
        now = timezone.now()

    created_count = 0
    cancelled_count = 0

    bookings = Booking.objects.filter(
        source=Booking.ONLINE,
        user__isnull=False,
        checked_in_at__isnull=True,
        status__in=[Booking.PENDING, Booking.CONFIRMED],
    ).select_related("user", "branch", "service")

    for booking in bookings:
        appointment_at = get_booking_datetime(booking)

        if now > appointment_at:
            if cancel_expired_unchecked_booking(booking, now=now):
                cancelled_count += 1
            continue

        if now < get_check_in_opens_at(booking):
            continue

        for reminder_at in get_check_in_reminder_slots(booking):
            if reminder_at > now:
                break

            notification, created = Notification.objects.get_or_create(
                related_booking=booking,
                reminder_at=reminder_at,
                notification_type=Notification.CHECK_IN_REMINDER,
                defaults={
                    "user": booking.user,
                    "title": "Check in to join the live queue",
                    "message": (
                        f"Your {booking.service.name} appointment at "
                        f"{booking.booking_time} is approaching. Check in now to "
                        "activate your place in the Smart Q live queue."
                    ),
                    "related_ticket": getattr(booking, "queueticket", None),
                },
            )

            if created:
                created_count += 1

    return {
        "created": created_count,
        "cancelled": cancelled_count,
    }
