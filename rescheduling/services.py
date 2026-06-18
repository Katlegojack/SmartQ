from datetime import timedelta
from .models import RescheduleRecommendation
from queues.models import QueueDisruptionImpact

def get_next_recommended_date(booking):
    return booking.booking_date + timedelta(days=1)

def get_reschedule_risk_impacts(queue_pause=None):
    impacts = QueueDisruptionImpact.objects.filter(
        impact_type =QueueDisruptionImpact.RESCHEDULE_RISK
    )
    if queue_pause is None:
        impacts = impacts.filter(queue_pause=queue_pause)
    return impacts.order_by("created_at")

def create_reschedule_recommendation_for_impact(impact,suggested_date=None,suggested_time=None,reason=''):
    if impact is None:
        return {
            'recommendation':None,
            'created':False,
        }
    if impact.impact_type != QueueDisruptionImpact.RESCHEDULE_RISK:
        return {
            'recommendation':None,
            'created':False,
        }
    ticket = impact.ticket
    if ticket is None or ticket.booking is None:
        return{
            'recommendation':None,
            'created':False,
        }
    booking = ticket.booking

    if suggested_date is None:
        suggested_date =get_next_recommended_date(booking)

    if suggested_time is None:
        suggested_time = booking.booking_time
    
    if not reason:
        reason = ("Customer was at risk of not being served due to lost "
            "service capacity from a queue disruption."
        )

    recommendation,created = RescheduleRecommendation.objects.get_or_create(
        disruption_impact = impact,
        defaults={
            'booking':booking,
            'ticket':ticket,
            'old_booking_date':booking.booking_date,
            'old_booking_time':booking.booking_time,
            'suggest_booking_date':suggested_date,
            'suggest_booking_time':suggested_time,
            'priority_on_reschedule':True,
            'reason':reason,
        }
    )
    return{
        'recommendation':recommendation,
        'created':created,
    }

def create_reschedule_recommendations_for_risk_impacts(queue_pause=None):
    impacts =get_reschedule_risk_impacts(queue_pause)
    recommendation_created =0
    recommendation_processed =0

    for impact in impacts:
        result = create_reschedule_recommendation_for_impact(impact)

        if result['recommendation'] is None:
            recommendation_processed += 1

        if result['created'] is None:
            recommendation_created +=1
        
    return{
        'recommendation_processed':recommendation_processed,
        'recommendation_created':recommendation_created,
    }
