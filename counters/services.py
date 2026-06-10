from .models import Counter


def get_active_counter_count(branch, queue_type):
    return Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN
    ).count()