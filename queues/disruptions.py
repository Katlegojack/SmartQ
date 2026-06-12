from .models import QueuePause
from django.utils import timezone

def pause_queue(branch,service,booking_date,reason=''):
    active_pause = QueuePause.objects.filter(
        branch =branch,
        service =service,
        booking_date=booking_date,
        is_active = True
    ).first()

    if active_pause:
        return active_pause
    
    return QueuePause.objects.create(
        branch=branch,
        service=service,
        booking_date=booking_date,
        reason=reason,
        is_active = True
    )
    
def resume_queue(queue_pause):
        if queue_pause is None:
            return None
        if queue_pause.is_active is False:
            return queue_pause
        
        queue_pause.ended_at = timezone.now()
        queue_pause.is_active = False
        queue_pause.save()
        return queue_pause
        