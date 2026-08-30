# Smart Q — Day 28 Operational Core

## Purpose

Day 28 moves Smart Q from having isolated queue actions toward a frontend-ready operational queue workflow.

The goal of this work is not to redesign Smart Q. It is to make the existing architecture safer and expose the queue information the real frontend needs.

The work follows the existing Smart Q architecture:

```text
API Request
    ↓
DRF API View
    ↓
Service Layer
    ↓
Django Models / ORM
    ↓
Database
```

Business state changes remain inside service functions. API views handle authentication, object lookup and HTTP responses.

---

## Why this work was necessary

Before Day 28, Smart Q already supported these staff actions:

```text
Call Next
Complete Current Ticket
Mark Current Ticket No-Show
```

However, several important problems remained:

1. Any authenticated user could call staff queue-operation endpoints.
2. `call_next_ticket()` could crash when no waiting ticket existed because it accessed the ticket before checking for `None`.
3. A counter could potentially call a future booking because the queue service was not restricted to today's booking date.
4. QueueTicket status and Booking status could become inconsistent.
5. Counter helper functions contained field-name and counting bugs.
6. Queue statistics contained inconsistent function names.
7. The booking creation date validator was accidentally nested inside `Meta`, so it was not being used by DRF.
8. Customer and staff frontends had action endpoints but were missing essential read endpoints.
9. Broad `except Exception` blocks could hide real programming errors.
10. There were no meaningful automated queue API regression tests.

Day 28 addresses these problems without replacing the existing project structure.

---

# Changes Implemented

## 1. Staff-only queue operations

### File

`queues/permissions.py`

### New permission

```python
class IsQueueStaff(BasePermission):
```

Smart Q does not yet have a dedicated staff-role model, so Django's existing `User.is_staff` field is used as the current authorization boundary.

This means:

```text
Authenticated customer → cannot operate counter
Authenticated staff user → can operate counter
```

This is safer than the previous `IsAuthenticated` rule, which only checked whether a user was logged in.

### Important future improvement

`is_staff` is an intermediate security boundary, not the final role system.

Future Smart Q should introduce explicit roles such as:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

and branch-level authorization so staff can operate only their assigned branch/counters.

---

## 2. Queue lifecycle hardening

### File

`queues/services.py`

Queue lifecycle functions were reorganized and documented.

### `call_next_ticket(counter)`

The function now:

1. Requires the counter to be OPEN.
2. Defaults to today's date.
3. Checks whether the counter is already serving someone.
4. Searches only today's waiting tickets.
5. Searches only tickets matching the counter's branch and queue type.
6. Ignores cancelled/completed booking states.
7. Uses FIFO ordering.
8. Assigns the selected ticket to the counter.
9. Changes ticket status from `WAITING` to `SERVING`.
10. Changes booking status from `PENDING` to `CONFIRMED`.

Simplified flow:

```text
OPEN Counter
    ↓
Already serving someone?
    ├── Yes → do not call another customer
    └── No
         ↓
Find today's next matching WAITING ticket
         ↓
Assign counter
         ↓
WAITING → SERVING
         ↓
Booking PENDING → CONFIRMED
```

### Why transactions were added

Queue transitions are wrapped with:

```python
@transaction.atomic
```

This means the database treats the transition as one operation.

`select_for_update()` was also introduced for important ticket selection paths. This matters when Smart Q later runs on PostgreSQL and multiple staff members use the queue simultaneously.

---

## 3. Booking and queue status synchronization

Previously the QueueTicket could be completed while the Booking remained `pending`.

That creates contradictory history:

```text
Booking: pending
QueueTicket: completed
```

The lifecycle is now synchronized.

### Call Next

```text
QueueTicket: WAITING → SERVING
Booking: PENDING → CONFIRMED
```

### Complete

```text
QueueTicket: SERVING → COMPLETED
Booking: CONFIRMED → COMPLETED
assigned_counter → None
```

### No Show

```text
QueueTicket: SERVING → NO_SHOW
Booking: CONFIRMED → NO_SHOW
assigned_counter → None
```

### Cancel

```text
Booking → CANCELLED
QueueTicket → CANCELLED
assigned_counter → None
```

This gives Smart Q one consistent customer history.

---

## 4. Customer live queue API

### Endpoint

```http
GET /api/v1/queues/my-current/
```

### Permission

Authenticated customer.

### Purpose

This endpoint powers the customer Queue Tracker screen.

It returns the customer's active queue ticket for today together with the existing waiting-time prediction logic.

Example conceptual response:

```json
{
  "ticket": {
    "queue_number": "A014",
    "queue_type": "general",
    "status": "waiting",
    "branch_name": "Kimberley Branch",
    "service_name": "ID Application"
  },
  "prediction": {
    "people_ahead": 3,
    "queue_position": 4,
    "estimated_wait_time": 30
  }
}
```

This exposes existing Smart Q intelligence instead of leaving it trapped inside Python service functions.

When a ticket is already `SERVING`, the endpoint reports zero remaining wait.

---

## 5. Staff current-customer API

### Endpoint

```http
GET /api/v1/queues/counters/<counter_id>/current/
```

### Permission

Staff only.

### Purpose

A counter dashboard needs to know who is currently being served.

This endpoint lets the frontend display:

```text
Counter 3
Currently Serving
A014
ID Application
Customer Name
```

without guessing state in the frontend.

---

## 6. Staff waiting-queue API

### Endpoint

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
```

Optional query parameter:

```text
?queue_type=general
?queue_type=priority
```

### Permission

Staff only.

### Purpose

This provides today's live waiting queue for reception/counter dashboards.

The backend owns the queue state. The frontend only displays it.

---

## 7. Queue serializer expansion

### File

`queues/serializers.py`

The queue ticket response now includes useful booking context:

```text
booking_id
branch_name
service_name
booking_date
booking_time
customer_name
```

This avoids forcing the frontend to make several additional requests simply to show one queue ticket.

The serializer remains read-only.

---

## 8. Booking validation fixes

### File

`bookings/serializers.py`

### Past-date validation

The original `validate_booking_date()` function was nested inside the serializer's `Meta` class.

DRF therefore did not treat it as a field validator.

It was moved to the correct serializer level.

The API now rejects:

```text
booking_date < today
```

### Branch operating-hours validation

Booking creation and rescheduling now validate that the requested time is within:

```text
branch.opening_time
branch.closing_time
```

This prevents obviously invalid appointments such as booking a branch at 23:00 when it closes at 16:30.

This is not yet the final availability engine. Capacity/slot availability remains future work.

---

## 9. Safer cancellation and rescheduling

### File

`bookings/api_views.py`

Cancellation and rescheduling now use database transactions.

Broad error handling such as:

```python
except Exception:
```

was replaced with the queue-ticket missing case.

This is important because broad exception handling can hide actual bugs.

### Rescheduling rules

The endpoint now rejects rescheduling when the booking is:

```text
COMPLETED
CANCELLED
NO_SHOW
```

A successfully rescheduled booking returns to an active pending state and its queue ticket is reset to `WAITING` with a newly generated queue number.

---

## 10. Counter service fixes

### File

`counters/services.py`

Fixed the incorrect field name:

```text
assinged_counter
```

to:

```text
assigned_counter
```

The counter summary also previously mixed a list of free counters with a numeric count. It now returns consistent integer values:

```json
{
  "queue_type": "general",
  "open_counters": 4,
  "free_counters": 2,
  "busy_counters": 2
}
```

---

## 11. Statistics fixes

### File

`queues/statistics.py`

The project had two inconsistent names:

```text
get_queue_branch_statistics
get_branch_queue_statistics
```

This caused report helper functions to reference a function that did not exist.

The statistics module now consistently uses:

```python
get_branch_queue_statistics()
```

and documents the purpose of each aggregation helper.

---

# Automated Tests Added

### File

`queues/tests.py`

Day 28 introduces regression tests around the operational queue workflow.

Current tests cover:

### 1. Customer authorization

A normal customer attempting to call the next ticket must receive:

```text
403 Forbidden
```

### 2. Staff Call Next

Verifies:

```text
WAITING → SERVING
counter assigned
Booking PENDING → CONFIRMED
```

### 3. Complete Current Ticket

Verifies:

```text
SERVING → COMPLETED
counter released
Booking → COMPLETED
```

### 4. Customer current queue tracker

Verifies the customer receives:

```text
queue ticket
queue number
prediction
queue position
```

---

# Testing Commands

After pulling this branch locally, run:

```powershell
python manage.py check
python manage.py test queues
python manage.py test bookings
python manage.py test
```

Expected result:

```text
System check identified no issues
```

and all automated tests should pass.

The connected GitHub environment used to prepare this work can edit and inspect the repository but does not execute the Django project, so the branch must be run locally/CI before merging into `main`.

---

# New/Updated API Surface

```text
CUSTOMER
GET  /api/v1/queues/my-current/

STAFF READ
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/queues/counters/<counter_id>/current/

STAFF OPERATIONS
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

---

# What Day 28 Does NOT Claim to Finish

The following remain deliberate future work:

- dedicated staff/manager/admin role model
- branch-level staff assignments
- customer check-in
- walk-in registration
- slot-capacity booking availability
- Branch ↔ Service availability mapping
- authentication API/token strategy for a separate frontend
- counter open/pause/resume APIs
- manager dashboard API
- disruption/rescheduling manager APIs
- real-time WebSocket updates
- SMS/WhatsApp/email delivery
- historical queue-event timestamps
- production PostgreSQL deployment
- AI/ML wait-time forecasting

These should be implemented in controlled slices rather than rushed into one unsafe change.

---

# Engineering Principle

The most important Day 28 principle is:

> The frontend must never become responsible for Smart Q's business rules.

The backend owns:

```text
who can operate queues
who is next
what status a ticket is in
what status a booking is in
what counter owns a ticket
what the customer's queue prediction is
```

The frontend should request that information and display it.

This separation keeps Smart Q maintainable when the temporary pitch frontend is later replaced by the real production frontend.
