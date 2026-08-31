from django.db import transaction

from accounts.models import Profile
from queues.events import record_queue_event
from queues.models import QueueEvent, QueueTicket
from .models import Counter


def get_active_counter_count(branch, queue_type):
    return Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN,
        assigned_staff__isnull=False,
    ).count()


def get_current_ticket(counter):
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).first()


def is_counter_free(counter):
    return get_current_ticket(counter) is None


def get_free_counters(branch, queue_type):
    counters = Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN,
        assigned_staff__isnull=False,
    )
    return [counter for counter in counters if is_counter_free(counter)]


def get_free_counter_count(branch, queue_type):
    return len(get_free_counters(branch, queue_type))


def get_counter_status_summary(branch, queue_type):
    open_counters = get_active_counter_count(branch, queue_type)
    free_counters = get_free_counter_count(branch, queue_type)
    busy_counters = open_counters - free_counters
    return {
        "queue_type": queue_type,
        "open_counters": open_counters,
        "free_counters": free_counters,
        "busy_counters": busy_counters,
    }


def _lock_counter(counter):
    return Counter.objects.select_for_update().select_related(
        "branch", "assigned_staff", "assigned_staff__profile"
    ).get(pk=counter.pk)


@transaction.atomic
def assign_counter_staff(counter, staff_user, *, actor=None):
    counter = _lock_counter(counter)
    try:
        profile = staff_user.profile
    except Profile.DoesNotExist:
        return counter, "invalid_staff_role"

    if profile.role != Profile.COUNTER_STAFF:
        return counter, "invalid_staff_role"
    if profile.branch_id != counter.branch_id:
        return counter, "wrong_branch"
    if counter.status != Counter.CLOSED:
        return counter, "counter_not_closed"
    if get_current_ticket(counter) is not None:
        return counter, "counter_busy"

    existing = Counter.objects.select_for_update().filter(
        assigned_staff=staff_user
    ).exclude(pk=counter.pk).first()
    if existing is not None:
        return counter, "staff_already_assigned"

    counter.assigned_staff = staff_user
    counter.save(update_fields=["assigned_staff"])
    record_queue_event(
        QueueEvent.COUNTER_STAFF_ASSIGNED,
        counter=counter,
        actor=actor,
        metadata={
            "assigned_staff_id": staff_user.id,
            "assigned_staff_username": staff_user.get_username(),
        },
    )
    return counter, None


@transaction.atomic
def unassign_counter_staff(counter, *, actor=None):
    counter = _lock_counter(counter)
    if counter.status != Counter.CLOSED:
        return counter, "counter_not_closed"
    if get_current_ticket(counter) is not None:
        return counter, "counter_busy"

    previous_staff = counter.assigned_staff
    counter.assigned_staff = None
    counter.save(update_fields=["assigned_staff"])
    record_queue_event(
        QueueEvent.COUNTER_STAFF_UNASSIGNED,
        counter=counter,
        actor=actor,
        metadata={
            "previous_staff_id": previous_staff.id if previous_staff else None,
            "previous_staff_username": previous_staff.get_username() if previous_staff else "",
        },
    )
    return counter, None


@transaction.atomic
def open_counter(counter, *, actor=None):
    counter = _lock_counter(counter)
    if counter.assigned_staff_id is None:
        return counter, "unassigned"
    if counter.status == Counter.OPEN:
        return counter, "already_open"
    if counter.status == Counter.PAUSED:
        return counter, "use_resume"

    old_status = counter.status
    counter.status = Counter.OPEN
    counter.save(update_fields=["status"])
    record_queue_event(
        QueueEvent.COUNTER_OPENED,
        counter=counter,
        actor=actor,
        metadata={"from_counter_status": old_status, "to_counter_status": Counter.OPEN},
    )
    return counter, None


@transaction.atomic
def pause_counter(counter, *, actor=None):
    counter = _lock_counter(counter)
    if counter.status != Counter.OPEN:
        return counter, "not_open"

    counter.status = Counter.PAUSED
    counter.save(update_fields=["status"])
    record_queue_event(
        QueueEvent.COUNTER_PAUSED,
        counter=counter,
        actor=actor,
        metadata={"from_counter_status": Counter.OPEN, "to_counter_status": Counter.PAUSED},
    )
    return counter, None


@transaction.atomic
def resume_counter(counter, *, actor=None):
    counter = _lock_counter(counter)
    if counter.assigned_staff_id is None:
        return counter, "unassigned"
    if counter.status != Counter.PAUSED:
        return counter, "not_paused"

    counter.status = Counter.OPEN
    counter.save(update_fields=["status"])
    record_queue_event(
        QueueEvent.COUNTER_RESUMED,
        counter=counter,
        actor=actor,
        metadata={"from_counter_status": Counter.PAUSED, "to_counter_status": Counter.OPEN},
    )
    return counter, None


@transaction.atomic
def close_counter(counter, *, actor=None):
    counter = _lock_counter(counter)
    if get_current_ticket(counter) is not None:
        return counter, "counter_busy"
    if counter.status == Counter.CLOSED:
        return counter, "already_closed"

    old_status = counter.status
    counter.status = Counter.CLOSED
    counter.save(update_fields=["status"])
    record_queue_event(
        QueueEvent.COUNTER_CLOSED,
        counter=counter,
        actor=actor,
        metadata={"from_counter_status": old_status, "to_counter_status": Counter.CLOSED},
    )
    return counter, None
