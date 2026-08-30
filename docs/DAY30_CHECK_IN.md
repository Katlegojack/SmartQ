# Day 30 - Customer Arrival and Check-In

## Objective

Day 30 closes a major operational gap in Smart Q: a booking should not become part of the live physical queue until the customer actually arrives.

Before Day 30, booking creation automatically created a `QueueTicket` in `WAITING`, which meant a future/scheduled appointment could look like a live waiting customer.

Day 30 introduces the explicit boundary:

```text
BOOKING CREATED
    ↓
QueueTicket = SCHEDULED
checked_in_at = null
    ↓
CUSTOMER ARRIVES / RECEPTION CHECK-IN
    ↓
checked_in_at = timestamp
QueueTicket = WAITING
    ↓
CALL NEXT
    ↓
SERVING
    ↓
COMPLETED / NO_SHOW
```

## Model changes

### Booking.checked_in_at

`Booking` now stores:

```python
checked_in_at = models.DateTimeField(null=True, blank=True)
```

This timestamp is the authoritative signal that a scheduled appointment has entered the live queue.

A convenience property was added:

```python
@property
def is_checked_in(self):
    return self.checked_in_at is not None
```

### QueueTicket.SCHEDULED

`QueueTicket` now includes:

```text
SCHEDULED
WAITING
SERVING
COMPLETED
NO_SHOW
CANCELLED
```

New booking tickets default to `SCHEDULED`, not `WAITING`.

## Booking creation behavior

`create_queue_ticket_for_booking()` now creates:

```python
status=QueueTicket.SCHEDULED
```

This means customers can still receive a digital queue number when booking, but the ticket does not participate in Call Next, waiting-room lists, or ETA position until check-in.

## Check-in service

Day 30 adds a reusable transactional service:

```python
check_in_booking(booking)
```

The service:

1. locks the booking for update;
2. requires the booking date to be today;
3. rejects CANCELLED, COMPLETED, and NO_SHOW bookings;
4. detects duplicate check-in;
5. obtains/creates the related ticket;
6. recalculates queue type at arrival;
7. changes the ticket to `WAITING`;
8. clears any stale counter assignment;
9. stores `checked_in_at = timezone.now()`;
10. returns the booking to the active `PENDING` state.

The service returns a simple `(ticket, error_code)` result so customer and reception APIs share one business rule implementation.

## Customer self check-in API

```http
POST /api/v1/bookings/<id>/check-in/
```

Rules:

- authentication required;
- booking must belong to the logged-in customer;
- booking must be for today;
- final-state bookings cannot check in;
- duplicate check-in returns HTTP 409;
- successful check-in returns the updated booking and live ticket state.

## Reception / staff check-in API

```http
POST /api/v1/bookings/<id>/staff-check-in/
```

This endpoint uses Day 29's `IsQueueViewer` permission and object-level branch authorization.

That means:

```text
Receptionist      -> assigned branch only
Counter Staff     -> assigned branch only
Branch Manager    -> assigned branch only
System Admin      -> global
Customer          -> denied
```

The staff member must be authorised for the booking's branch.

## Rescheduling behavior

A rescheduled customer must check in again on the new date.

Therefore rescheduling now:

```text
checked_in_at -> null
QueueTicket   -> SCHEDULED
assigned_counter -> null
Booking       -> PENDING
```

This prevents an old arrival/check-in from incorrectly carrying over to a new appointment date.

## Live queue filtering

The live waiting queue now requires:

```python
booking__checked_in_at__isnull=False
status=QueueTicket.WAITING
```

`call_next_ticket()` uses the same requirement.

This means a same-day `SCHEDULED` appointment cannot be called before check-in.

## FIFO ordering

Queue order is now based on actual arrival/check-in time rather than ticket creation time:

```python
.order_by("booking__checked_in_at", "id")
```

This better matches the real physical queue.

## Waiting-time prediction

`get_people_ahead()` now compares `booking.checked_in_at` timestamps for WAITING tickets.

That means queue position reflects live arrival order rather than how early the appointment was originally created.

## Queue statistics

Queue statistics now distinguish:

```text
scheduled
waiting
serving
completed
no_show
cancelled
```

`scheduled_customers` are expected appointments but are not counted as active physical queue customers.

## API serialization

Booking responses now expose:

```text
checked_in_at
is_checked_in
```

Queue ticket responses now expose:

```text
checked_in_at
```

This gives the frontend a clear distinction between appointment state and live-queue state.

## Tests added

Day 30 booking/check-in tests cover:

- customer checks in own booking today;
- future booking cannot check in;
- customer cannot check in someone else's booking;
- duplicate check-in returns 409;
- cancelled booking cannot check in;
- receptionist can check in a booking in assigned branch;
- receptionist cannot check in another branch;
- rescheduling clears old check-in and returns ticket to SCHEDULED;
- booking creation creates SCHEDULED rather than WAITING.

Queue regression tests were updated so active test tickets have `checked_in_at`, and a new regression test confirms a SCHEDULED same-day appointment cannot be called before check-in.

## CI verification

The Day 30 branch runs:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test
```

## Important limitations

Day 30 intentionally does not yet add:

- geographic/geofence validation;
- QR-code check-in;
- kiosk hardware integration;
- appointment check-in windows such as only 30 minutes early;
- walk-in ticket creation;
- receptionist booking search endpoint;
- automatic no-show timeout;
- queue-event history table.

These can be added on top of the explicit check-in foundation without changing its main lifecycle.

## Result

Day 30 changes Smart Q from:

```text
BOOKING = WAITING
```

into the more accurate operational model:

```text
BOOKING -> SCHEDULED -> CHECK-IN -> WAITING -> SERVING
```

This is a critical step toward a real branch pilot because the live queue now represents customers who have actually arrived rather than every appointment that exists in the database.
