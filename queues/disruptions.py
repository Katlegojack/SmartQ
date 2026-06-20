from .models import QueuePause,QueueTicket,QueueDisruptionImpact
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

def get_affected_waiting_tickets(queue_pause):
     if queue_pause is None:
          return QueueTicket.objects.none()
     
     return QueueTicket.objects.filter(
          booking__branch=queue_pause.branch,
          booking__service = queue_pause.service,
          booking__booking_date= queue_pause.booking_date,
          status = QueueTicket.WAITING
     ).order_by("created_at")

def get_reschedule_risk_tickets(queue_pause):
     if queue_pause is None:
          return []
     lost_capacity =calculate_lost_service_capacity(queue_pause)

     if lost_capacity <=0:
          return []
     
     affected_tickets = list(get_affected_waiting_tickets(queue_pause))

     if lost_capacity >= len(affected_tickets):
          return affected_tickets
     
     return affected_tickets[-lost_capacity:]

def get_disruption_report(queue_pause):
    affected_tickets = list(
        get_affected_waiting_tickets(queue_pause)
    )

    risk_tickets = get_reschedule_risk_tickets(queue_pause)

    return {
        "pause_impact": get_pause_impact_summary(queue_pause),
        "affected_waiting_count": len(affected_tickets),
        "reschedule_risk_count": len(risk_tickets),
        "reschedule_risk_tickets": [
            ticket.queue_number for ticket in risk_tickets
        ],
    }

def create_disruption_impact_records(queue_pause):
     if queue_pause is None:
          return {
               'affected_created':0,
               'reschedule_risk':0
          }
     affected_tickets =list(get_affected_waiting_tickets(queue_pause))
     risk_tickets = get_reschedule_risk_tickets(queue_pause)

     affected_created =0
     reschedule_risk_created =0

     for ticket in affected_tickets:
          impact, created =QueueDisruptionImpact.objects.get_or_create(
               queue_pause = queue_pause,
               ticket = ticket,
               impact_type = QueueDisruptionImpact.AFFECTED,
               defaults= {"message": "Your queue was affected by a service disruption."}
          )
          if created:
               affected_created +=1

          for ticket in risk_tickets:
               impact, created = QueueDisruptionImpact.objects.get_or_create(
               queue_pause=queue_pause,
               ticket=ticket,
               impact_type=QueueDisruptionImpact.RESCHEDULE_RISK,
               defaults={
                    "message": "You may need to be rescheduled due to a service disruption."
               }
          )
          if created:
               reschedule_risk_created +=1

     return {
            'affected_created':affected_created,
            'reschedule_risk_created': reschedule_risk_created,
          }

def get_disruption_report(queue_pause):
    affected_tickets = list(
        get_affected_waiting_tickets(queue_pause)
    )

    risk_tickets = get_reschedule_risk_tickets(queue_pause)

    return {
        "pause_impact": get_pause_impact_summary(queue_pause),
        "affected_waiting_count": len(affected_tickets),
        "reschedule_risk_count": len(risk_tickets),
        "reschedule_risk_tickets": [
            ticket.queue_number for ticket in risk_tickets
        ],
    }
def get_unnotified_disruption_impact(queue_pause=None):
     impacts = QueueDisruptionImpact.objects.filter(is_notified=False)
     if queue_pause is None:
          impacts = impacts.filter(
               queue_pause =queue_pause
          )
     return impacts.order_by("created_at")


def mark_disruption_impact_notified(impact):
     if impact is None:
          return None
     impact.is_notified = True
     impact.save()

     return impact
  