from .models import Notification
from queues.models import QueueDisruptionImpact
from queues.disruptions import (get_unnotified_disruption_impact,mark_disruption_impact_notified)

def create_notification_for_impact(impact):
    if impact is None:
        return {
            "notification":None,
            'created':False,
        }
    ticket = impact.ticket
    if ticket is None or ticket.booking is None:
        return {
            'notification':None,
            'created':False,
        }
    user = ticket.booking.user

    if impact.impact_type ==QueueDisruptionImpact.RESCHEDULE_RISK:
        title = 'Possible reschedule'
        notification_type = Notification.RESCHEDULE
        default_message = "You may need to be rescheduled due to a service disruption."
    else:
        title = "Queue Disruption"
        notification_type = Notification.DISRUPTION
        default_message = "Your queue was affected by a service disruption."
    
    message = impact.message
    if not message:
        message = default_message
    
    notification,created = Notification.objects.get_or_create(
        related_impact=impact,
        defaults={
            "user": user,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "related_ticket": ticket,
        }
    
    )
    if impact.is_notified is False:
        mark_disruption_impact_notified(impact)
    
    return{
        'notification':notification,
        'created':created,
    }

def create_notification_for_unnotified_impacts(queue_pause=None):
    impacts = get_unnotified_disruption_impact(queue_pause)
    notifications_created =0
    notifications_processed =0
    for impact in impacts:
        result = create_notification_for_impact(impact)
        
        if result['notification'] is not None:
            notifications_processed +=1

        if result['created']:
            notifications_created += 1

    return{
        'notification_processed':notifications_processed,
        'notification_created':notifications_created,
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
    notification.save()
    return notification

def mark_all_notification_as_read(user):
    if user is None:
        return 0
    
    updated_count =Notification.objects.filter(
        user=user,
        is_read = False
    ).update(is_read=True)

    return updated_count

def  create_reschedule_applied_notification(recommendation):
    #if no recommendation is given stop safely
    if recommendation is None:
        return {
            'notification':None,
            'created':False,
        }
    #Get the booking linked to this recommendation
    booking = recommendation.booking
    #Get the queue ticket linked to this recommendation
    ticket = recommendation.ticket

    #If the booking or ticket is missing, we cannot create a proper notification
    if booking is None or ticket is None:
        return{
            'notification':None,
            'created':False,
        }
    #The notification must be sent to the user who owns the booking
    user = booking.user

    #Short notification heading
    title = 'Reschedule confirmed'

    #Full Message shown to the customer
    message = (
        f"Your booking has been rescheduled to {booking.booking_date} at {booking.booking_time}. Your new queue is {ticket.queue_number}."

    )
    #Create the notification only if it does not already exist
    #This prevents duplicate notifications for the same rescheduled ticket
    notification,created =Notification.objects.get_or_create(
        user = user,
        title =title,
        notification_type =Notification.RESCHEDULE,
        related_ticket =ticket,
        defaults={'message':message}
    )
    #Return both the notification and whether it was newley created
    return{
        'notification':notification,
        'created':created,
    }