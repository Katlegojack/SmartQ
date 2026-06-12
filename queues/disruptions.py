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
        
def get_pause_duration_minutes(queue_pause):
     if queue_pause is None:
          return 0
     end_time = queue_pause.ended_at

     if queue_pause.is_active or end_time is None:
        end_time = timezone.now()
    
     duration = end_time -queue_pause.started_at
     return round(duration.total_seconds()/60)

def calculate_lost_service_capacity(queue_pause):
     if queue_pause is None:
          return 0
     
     pause_duration =get_pause_duration_minutes(queue_pause)
     average_service_time = queue_pause.service.average_service_time

     if average_service_time <=0:
          return 0
     
     return round(pause_duration/average_service_time)

def get_pause_impact_summary(queue_pause):
    if queue_pause is None:
        return {
            "duration_minutes": 0,
            "lost_service_capacity": 0,
            "is_active": False,
        }

    return {
        "branch": str(queue_pause.branch),
        "service": str(queue_pause.service),
        "booking_date": queue_pause.booking_date,
        "is_active": queue_pause.is_active,
        "duration_minutes": get_pause_duration_minutes(queue_pause),
        "lost_service_capacity": calculate_lost_service_capacity(queue_pause),
    }