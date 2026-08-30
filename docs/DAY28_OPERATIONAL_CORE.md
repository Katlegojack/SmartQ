# Smart Q - Day 28 Operational Core

## Status

**Day 28 is complete and verified.**

The Day 28 branch passed automated GitHub Actions verification covering:

```powershell
python manage.py check
python manage.py test queues
python manage.py test bookings
python manage.py test
```

All stages completed successfully before the pull request was prepared for merge.

---

# 1. Purpose

Day 28 moves Smart Q from having isolated queue actions toward a safer, frontend-ready operational queue workflow.

The goal was not to redesign Smart Q. The goal was to harden the existing backend so that the frontend can reliably ask the backend:

```text
Who is waiting?
Who is currently being served?
What is my queue position?
How long might I wait?
Can this user operate a counter?
Can this counter call another customer?
```

The work continues to follow the existing architecture:

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

Business state changes remain in service functions. API views handle authentication/authorization, object lookup and HTTP responses. Serializers convert model data into frontend-friendly JSON.

---

# 2. Problems Found Before Day 28

Repository inspection identified several issues that could prevent Smart Q from becoming a reliable operational queue system.

1. Queue-operation endpoints used only `IsAuthenticated`, meaning a normal logged-in customer could potentially operate counters.
2. `call_next_ticket()` could crash when no waiting ticket existed because code accessed the ticket before safely handling `None`.
3. Call Next was not restricted strongly enough to today's live queue.
4. A counter could potentially call another customer while already serving someone.
5. QueueTicket status and Booking status could become inconsistent.
6. Completion and no-show operations updated the queue ticket but not necessarily the corresponding booking history.
7. Counter helper logic contained a misspelled relationship field (`assinged_counter`).
8. Counter summary logic mixed lists and numeric counts.
9. Queue statistics helpers used inconsistent function names.
10. `BookingCreateSerializer.validate_booking_date()` was incorrectly nested inside `Meta`, so Django REST Framework did not use it as a validator.
11. Booking/rescheduling time input was not checked against branch opening hours.
12. Booking cancellation/rescheduling used broad `except Exception` blocks that could hide genuine programming errors.
13. Customer/staff frontends had action endpoints but lacked the read APIs required to display current queue state.
14. The combined waiting queue claimed to prioritize Priority tickets but alphabetical ordering actually placed General first.
15. Existing automated test files were mostly empty, so queue regressions could reappear unnoticed.

Day 28 addresses these issues without replacing the existing domain model or project structure.

---

# 3. Staff Authorization Boundary

## File

`queues/permissions.py`

## New permission

```python
class IsQueueStaff(BasePermission):
```

Smart Q does not yet have a dedicated role/branch-assignment model, so Day 28 uses Django's existing `User.is_staff` field as an **interim authorization boundary**.

Current behavior:

```text
Unauthenticated user  -> denied
Normal customer       -> denied
Django staff user     -> allowed to use queue staff endpoints
```

This closes an important security gap compared with the previous `IsAuthenticated` rule.

### Why this is interim

`is_staff` is not a complete business-role system. The intended future role model remains:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Future authorization must also be branch scoped so a staff member assigned to one branch cannot operate another branch simply by knowing its database IDs.

---

# 4. Queue Lifecycle Hardening

## File

`queues/services.py`

### `call_next_ticket(counter)`

The function now:

1. Requires the counter to be `OPEN`.
2. Defaults to today's date.
3. Checks whether the counter is already serving someone.
4. Searches only today's waiting tickets.
5. Matches the counter's branch.
6. Matches the counter's queue type.
7. Excludes tickets whose bookings are no longer active.
8. Uses FIFO ordering inside the matching queue.
9. Safely returns `None` when nobody can be called.
10. Assigns the selected ticket to the counter.
11. Changes QueueTicket from `WAITING` to `SERVING`.
12. Aligns the Booking lifecycle by moving `PENDING` to `CONFIRMED`.

Simplified flow:

```text
Counter OPEN?
    ├── No -> stop
    └── Yes
         ↓
Already serving someone?
    ├── Yes -> stop
    └── No
         ↓
Find today's matching WAITING ticket
         ↓
Assign counter
         ↓
QueueTicket WAITING -> SERVING
         ↓
Booking PENDING -> CONFIRMED
```

---

# 5. Transaction and Concurrency Safety

Critical queue state changes now use:

```python
@transaction.atomic
```

Important ticket selections also use:

```python
select_for_update()
```

### In simpler terms

Queue operations often change more than one database value at once.

For example:

```text
Ticket becomes SERVING
+ Counter becomes assigned
+ Booking becomes CONFIRMED
```

A transaction treats that workflow as one database operation rather than several unrelated changes.

`select_for_update()` also prepares the system for production databases such as PostgreSQL where multiple staff members may press **Call Next** at nearly the same time.

### Remaining concurrency work

Queue-number generation itself still needs stronger production-grade protection against simultaneous number generation. That is intentionally listed as future hardening rather than falsely claimed as solved.

---

# 6. Booking and QueueTicket Synchronization

Before Day 28, the two related state machines could contradict one another.

Example of an invalid history:

```text
Booking: pending
QueueTicket: completed
```

Day 28 aligns important transitions.

## Call Next

```text
QueueTicket: WAITING -> SERVING
Booking:     PENDING -> CONFIRMED
```

## Complete

```text
QueueTicket: SERVING -> COMPLETED
Booking:     -> COMPLETED
assigned_counter -> None
```

## No Show

```text
QueueTicket: SERVING -> NO_SHOW
Booking:     -> NO_SHOW
assigned_counter -> None
```

## Cancel

```text
Booking:     -> CANCELLED
QueueTicket: -> CANCELLED
assigned_counter -> None
```

This gives customer history, staff operations and future reports a single consistent truth.

---

# 7. Customer Live Queue API

## Endpoint

```http
GET /api/v1/queues/my-current/
```

## Permission

Authenticated customer.

## Purpose

This endpoint powers the customer Queue Tracker screen.

It finds the logged-in customer's active ticket for today and combines it with Smart Q's existing rule-based waiting-time logic.

Conceptual response:

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

This is an important product milestone because the waiting-time engine is no longer just internal Python logic; it can now directly power the frontend.

When a ticket is already `SERVING`, remaining wait values are returned as zero.

---

# 8. Staff Current-Customer API

## Endpoint

```http
GET /api/v1/queues/counters/<counter_id>/current/
```

## Permission

Staff only.

## Purpose

A staff dashboard needs to know who is currently being served at the selected counter.

This endpoint supports a frontend view such as:

```text
COUNTER 3

Currently Serving
A014
ID Application
Customer Name
```

If the counter is free, the API returns a clear not-found/free-counter response instead of fabricating state in the frontend.

---

# 9. Staff Waiting-Queue API

## Endpoint

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
```

Optional filters:

```text
?queue_type=general
?queue_type=priority
```

## Permission

Staff only.

## Purpose

This endpoint provides today's waiting queue for staff/reception dashboards.

Invalid queue types are rejected with `400 Bad Request`.

### Priority ordering correction

During Day 28 verification, an additional bug was found.

The code comment said Priority tickets should appear before General tickets in a combined waiting-room view, but this ordering:

```python
order_by("queue_type", ...)
```

would alphabetically place `general` before `priority`.

Day 28 now uses an explicit database sort rank so the combined list is intentionally:

```text
Priority
then
General
```

while FIFO ordering is preserved inside each queue type.

---

# 10. Queue Serializer Expansion

## File

`queues/serializers.py`

The queue ticket serializer was expanded with frontend-useful booking context such as:

```text
booking_id
branch_name
service_name
booking_date
booking_time
customer_name
```

This reduces unnecessary frontend requests when one queue row/card needs basic booking context.

The serializer remains read-only.

---

# 11. Booking Validation Fixes

## File

`bookings/serializers.py`

### Past-date validation

The original creation validator was accidentally nested inside the serializer's `Meta` class.

DRF therefore would not use it as a field validator.

Day 28 moves it to the correct serializer level.

Now:

```text
booking_date < today
```

is rejected.

### Branch operating hours

Booking creation and rescheduling now validate that the requested time is inside:

```text
branch.opening_time
branch.closing_time
```

Example:

```text
Branch hours: 08:00 - 16:30
Request: 23:00
Result: validation error
```

This is **not yet** the final availability engine. Capacity-aware appointment slots remain future work.

---

# 12. Safer Cancellation and Rescheduling

## File

`bookings/api_views.py`

Cancellation and rescheduling now use database transactions.

Broad handling such as:

```python
except Exception:
```

was replaced with explicit missing-related-object handling.

### Why this matters

Catching every exception can hide real programming errors and allow inconsistent state to survive silently.

### Rescheduling rules

The endpoint now explicitly rejects rescheduling when a booking is:

```text
COMPLETED
CANCELLED
NO_SHOW
```

A successful reschedule:

```text
validates date/time
      ↓
updates booking
      ↓
recalculates queue type
      ↓
generates new queue number
      ↓
QueueTicket -> WAITING
      ↓
clears assigned counter
      ↓
Booking -> PENDING
```

---

# 13. Counter Service Fixes

## File

`counters/services.py`

Fixed the misspelled relation:

```text
assinged_counter
```

to:

```text
assigned_counter
```

Counter summary output now uses integer counts consistently:

```json
{
  "queue_type": "general",
  "open_counters": 4,
  "free_counters": 2,
  "busy_counters": 2
}
```

---

# 14. Statistics Fixes

## File

`queues/statistics.py`

The module contained inconsistent helper naming around:

```text
get_queue_branch_statistics
get_branch_queue_statistics
```

Day 28 normalizes the internal usage so report helpers call the function that actually exists.

---

# 15. Automated Regression Tests

## File

`queues/tests.py`

Day 28 replaces the almost-empty queue test file with meaningful API regression coverage.

Verified scenarios include:

### Authorization

```text
Normal authenticated customer
        ↓
POST Call Next
        ↓
403 Forbidden
```

### Closed counter protection

```text
Counter CLOSED
      ↓
Call Next
      ↓
409 Conflict
```

### Staff Call Next lifecycle

```text
QueueTicket WAITING -> SERVING
Counter assigned
Booking PENDING -> CONFIRMED
```

### Future booking protection

A booking for tomorrow remains waiting and is not called into today's queue.

### Busy counter protection

A counter already serving one customer cannot call a second waiting customer.

### Completion synchronization

```text
QueueTicket -> COMPLETED
Booking -> COMPLETED
Counter released
```

### No-show synchronization

```text
QueueTicket -> NO_SHOW
Booking -> NO_SHOW
Counter released
```

### Current counter read API

Staff can retrieve the ticket currently being served.

### Customer current queue API

Customer receives their active ticket plus queue prediction fields.

### Priority ordering

Combined branch waiting view returns Priority before General.

### Invalid queue type

Unsupported values such as:

```text
?queue_type=vip
```

return `400 Bad Request`.

---

# 16. Continuous Integration Added

## File

`.github/workflows/django-tests.yml`

Day 28 introduces automated GitHub Actions verification.

The workflow:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Installs `requirements.txt`.
4. Runs Django system checks.
5. Runs queue tests.
6. Runs booking tests.
7. Runs the complete Django test suite.

Verification result for the final Day 28 code change:

```text
Django system checks     PASS
Queue regression tests  PASS
Booking tests           PASS
Full test suite          PASS
```

This is an important process improvement because future regressions can be detected automatically on relevant branch pushes and pull requests.

---

# 17. New/Updated API Surface

## Customer

```http
GET /api/v1/queues/my-current/
```

## Staff read

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

## Staff operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

---

# 18. What Day 28 Does NOT Claim to Finish

The following remain deliberate future work:

- dedicated business-role model
- branch-level staff assignments
- authentication/token API for a separate production frontend
- customer arrival/check-in
- walk-in registration
- branch-to-service availability mapping
- capacity-aware booking slots
- counter open/pause/resume/close APIs
- staff-to-counter assignment
- manager dashboard APIs
- manager-facing disruption/rescheduling APIs
- historical queue event timestamps
- external SMS/WhatsApp/email/push delivery
- real-time updates
- production PostgreSQL deployment
- queue-number concurrency hardening
- production monitoring/logging/backups
- genuine AI/ML wait-time forecasting

These should be implemented in controlled slices instead of being rushed into one unsafe change.

---

# 19. Engineering Lessons

## Authentication is not authorization

`IsAuthenticated` proves a person is logged in. It does not prove they are allowed to operate a counter.

## State machines must agree

Booking and QueueTicket represent different parts of the same service journey. Their final states must not contradict one another.

## Frontend read APIs matter as much as action APIs

A staff interface cannot function with only "Call Next" and "Complete" actions. It also needs to read the current customer and waiting queue.

## Tests should cover negative paths

A useful test suite checks not only whether an operation works, but whether invalid operations are blocked.

Examples:

```text
customer tries staff action
closed counter calls next
future booking is called early
busy counter serves two customers
invalid filter is submitted
```

## Comments must match behavior

The Priority-before-General bug showed that comments can become misleading if they describe intended behavior rather than verified behavior.

## CI turns testing into a repeatable engineering process

Instead of relying only on memory and shell testing, the repository now has an automated verification path.

---

# 20. Day 28 Completion Summary

Day 28 significantly strengthens Smart Q's transition from a collection of backend features into an operational queue platform.

Before Day 28, Smart Q could already create bookings, generate priority-aware queue tickets and perform basic queue actions. However, authorization, state consistency, read APIs and automated regression protection were incomplete.

After Day 28:

```text
Customer booking
      ↓
Queue ticket
      ↓
Live queue tracker API
      ↓
Staff waiting-queue API
      ↓
Staff Call Next
      ↓
Current-counter API
      ↓
Complete / No Show
      ↓
Booking + QueueTicket stay synchronized
      ↓
Automated CI verifies the workflow
```

This does not make Smart Q production-ready, but it gives the project a much stronger operational core and a safer foundation for the next backend slices.

## Next major objective

The next phase should focus on closing the operational-MVP gap through:

```text
authentication API
role + branch permissions
customer check-in
walk-ins
booking availability/capacity
counter lifecycle
manager APIs
historical queue events
```

Only after those foundations are stable should Smart Q move aggressively into production infrastructure, real-time delivery and genuine machine-learning wait-time forecasting.
