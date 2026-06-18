from datetime import datetime,timedelta, time
from django.utils import timezone
from bookings.models import Booking
from queues.models import QueueTicket
from counters.services import get_active_counter_count

OPEN_TIME = time(8,0)
CLOSE_TIME = time(16,0)

DEFAULT_SERVICE_TIME_MINUTES =15
DEFAULT_MAX_SLOTS =5
DEFUALT_DAYS_AHEAD =5

def get_service_time_minutes(service):
    if service is None:
        return DEFAULT_SERVICE_TIME_MINUTES
    if service.average_service_time <=0:
        return DEFAULT_SERVICE_TIME_MINUTES
    return service.average_service_time

def generate_day_slots(target_date,service_time_minutes):
    current_datetime = datetime.combine(target_date,OPEN_TIME)
    closing_datetime = datetime.combine(target_date,CLOSE_TIME)

    while current_datetime < closing_datetime:
        yield current_datetime.time()
        current_datetime += timedelta(minutes=service_time_minutes)

def get_slot_capacity(branch,queue_type):
    active_counter_count =get_active_counter_count(branch,queue_type)
    if active_counter_count <=0:
        return 1
    return active_counter_count

def get_existing_booking_count(booking,target_date,target_time):
    if booking is None:
        return 0
    return Booking.objects.filter(
        branch =booking.branch,
        service = booking.service,
        booking_date =target_date,
        booking_time =target_time

    ).exclude(id=booking.id).count()

def get_slot_availability(booking,target_date,target_time,queue_type):
    capacity = get_slot_capacity(booking.branch,queue_type)
    booked_count =  get_existing_booking_count(booking,target_date,target_time)
    available_count = capacity - booked_count

    return {
         "date": target_date,
        "time": target_time,
        "capacity": capacity,
        "booked_count": booked_count,
        "available_count": available_count,
        "is_available": available_count > 0,
    }

def get_available_reschedule_slots(booking,start_date=None,days_ahead=DEFUALT_DAYS_AHEAD,max_slots=DEFAULT_MAX_SLOTS):
    if booking is None:
        return []
    if start_date is None:
        start_date =booking.booking_date + timedelta(days=1)
    
    queue_type =QueueTicket.PRIORITY
    service_time_minutes =get_service_time_minutes(booking.service)
    available_slots = []

    for day_offset in range(days_ahead):
        target_date = start_date +timedelta(days=day_offset)
        for target_time in generate_day_slots(target_date,service_time_minutes):
            slot = get_slot_availability(booking,target_date,target_time,queue_type)
            if slot['is_available']:
                slot['is_recommended'] =len(available_slots) ==0
                available_slots.append(slot)
            if len(available_slots)>=max_slots:
                return available_slots
    return available_slots


    