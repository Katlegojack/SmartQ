from .models import Counter


def get_active_counter_count(branch):
    return Counter.objects.filter(
        branch=branch,
        status=Counter.OPEN
    ).count()