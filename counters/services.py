from django.db import transaction

from accounts.models import Profile
from queues.models import QueueTicket
from .models import Counter


def get_active_counter_count(branch, queue_type):
    """
    Return the number of genuinely active counters for ETA calculations.

    Day 33 requires an OPEN counter to also have assigned staff. This prevents an
    accidentally-open but unstaffed counter from making customer wait estimates
    look artificially shorter.
    """
    return Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN,
        assigned_staff__isnull=False,
    ).count()


def get_current_ticket(counter):
    """Return the ticket currently being served at this counter, if any."""
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).first()


def is_counter_free(counter):
    return get_current_ticket(counter) is None


def get_free_counters(branch, queue_type):
    """Return staffed OPEN counters that are not currently serving a customer."""
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
    """Return simple capacity numbers for manager/staff dashboards."""
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
    """Reload and lock a counter before assignment/lifecycle state changes."""
    return Counter.objects.select_for_update().select_related(
        "branch",
        "assigned_staff",
        "assigned_staff__profile",
    ).get(pk=counter.pk)


@transaction.atomic
def assign_counter_staff(counter, staff_user):
    """
    Assign one same-branch COUNTER_STAFF user to a CLOSED, idle counter.

    Returns (counter, error_code). OneToOneField also protects the one-counter-per-
    staff invariant at database level while the explicit query gives a clear API
    error before the constraint is reached.
    """
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
        assigned_staff=staff_user,
    ).exclude(pk=counter.pk).first()
    if existing is not None:
        return counter, "staff_already_assigned"

    counter.assigned_staff = staff_user
    counter.save(update_fields=["assigned_staff"])
    return counter, None


@transaction.atomic
def unassign_counter_staff(counter):
    """Remove staff only when the counter is CLOSED and not serving a customer."""
    counter = _lock_counter(counter)

    if counter.status != Counter.CLOSED:
        return counter, "counter_not_closed"
    if get_current_ticket(counter) is not None:
        return counter, "counter_busy"

    counter.assigned_staff = None
    counter.save(update_fields=["assigned_staff"])
    return counter, None


@transaction.atomic
def open_counter(counter):
    """Open a staffed CLOSED counter so it can call waiting customers."""
    counter = _lock_counter(counter)

    if counter.assigned_staff_id is None:
        return counter, "unassigned"
    if counter.status == Counter.OPEN:
        return counter, "already_open"
    if counter.status == Counter.PAUSED:
        return counter, "use_resume"

    counter.status = Counter.OPEN
    counter.save(update_fields=["status"])
    return counter, None


@transaction.atomic
def pause_counter(counter):
    """
    Pause an OPEN counter.

    The current customer may still be completed/no-show while PAUSED, but Call
    Next is stopped until the counter is resumed.
    """
    counter = _lock_counter(counter)

    if counter.status != Counter.OPEN:
        return counter, "not_open"

    counter.status = Counter.PAUSED
    counter.save(update_fields=["status"])
    return counter, None


@transaction.atomic
def resume_counter(counter):
    """Resume a staffed PAUSED counter back to OPEN."""
    counter = _lock_counter(counter)

    if counter.assigned_staff_id is None:
        return counter, "unassigned"
    if counter.status != Counter.PAUSED:
        return counter, "not_paused"

    counter.status = Counter.OPEN
    counter.save(update_fields=["status"])
    return counter, None


@transaction.atomic
def close_counter(counter):
    """Close an idle counter. A currently serving customer must be resolved first."""
    counter = _lock_counter(counter)

    if get_current_ticket(counter) is not None:
        return counter, "counter_busy"
    if counter.status == Counter.CLOSED:
        return counter, "already_closed"

    counter.status = Counter.CLOSED
    counter.save(update_fields=["status"])
    return counter, None
