from datetime import timedelta
from .models import RescheduleRecommendation,RescheduleOption
from queues.models import QueueDisruptionImpact
from .slots import get_available_reschedule_slots

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

def create_reschedule_options_for_recommendation(recommendation,max_slot=5):
    if recommendation is None:
        return{
            
            'options_processed':0,
            'options_created':0,
        }
    booking =recommendation.booking

    if booking is None:
        return{
            'options_processed':0,
            'options_created':0,
        }
    
    RescheduleOption.objects.filter(recommendation=recommendation).update(recommendation=False)
    slots =get_available_reschedule_slots(booking,start_date=recommendation.old_booking_date+timedelta(days=1))
    options_processed=0
    options_created=0
    for slot in slots:
        options,created = RescheduleOption.objects.get_or_create(
            recommendation=recommendation,
            option_date =slot['date'],
            option_time = slot['time'],
            defaults={
                'capacity':slot['capacity'],
                'booked_count':slot['booked_count'],
                'available_count':slot['available_count'],
                'is_recommended':slot['is_recommended'],
            }
        )
        if created is False:
            options.capacity = slot['capacity']
            options.booked_count = slot['booked_capacity']
            options.available_count = slot['available_count']
            options.is_recommended = slot['is_recommended']
            options.save()
        
        options_processed +=1
        if created:
            options_created +=1
        
    return{
        'options_processed':options_processed,
        'options_created':options_created,
    }

def get_selected_reschedule_option(recommendation):
    if recommendation is None:
        return None
    
    return RescheduleOption.objects.filter(
        recommendation=recommendation,
        is_selected = True,
    ).first()

def select_reschedule_option(option):
    if option is None:
        return None
    
    if option.is_available_count <=0:
        return None
    
    recommendation = option.recommendation
    RescheduleOption.objects.filter(
        recommendation = recommendation,

    ).update(is_selected=False)

    option.is_selected = True
    option.save()

    recommendation.suggested_booking_date = option.option_date
    recommendation.suggested_booking_time = option.option_time
    recommendation.status =RescheduleRecommendation.APPROVED
    recommendation.save()

    return option