# Day 35 — Disruption and Rescheduling Repair

## Objective

Day 35 rebuilds Smart Q's unfinished disruption/rescheduling domain around the current operational architecture. The goal is not to add a second scheduling system; it is to make service disruptions produce deterministic, auditable customer impacts and capacity-safe replacement appointments.

## Approved Product Rules

1. Only WAITING customers in the paused branch + service + booking date are affected.
2. Lost service capacity determines how many customers at the back of the affected queue are marked `RESCHEDULE_RISK`.
3. At-risk customers receive up to five future replacement options starting from the next day.
4. Replacement options use the same Day 32 `BranchService` capacity engine as normal bookings.
5. A disruption-rescheduled customer receives Priority queue treatment as compensation.
6. Priority compensation does not bypass check-in: after rescheduling, the booking returns to `PENDING`, the ticket returns to `SCHEDULED`, and `checked_in_at` is cleared.
7. The affected registered customer chooses their own replacement slot.
8. Customer selection immediately applies the reschedule atomically after a fresh capacity check.
9. Risk is finalized when the pause ends. While the pause is active the manager sees a live preview; resume freezes the final impact snapshot.

## Why Day 35 Is a Rebuild

The pre-Day-35 code contained multiple independent defects:

- `RescheduleRecommendation` fields were referenced as `suggest_booking_date` / `suggest_booking_time` even though the model defines `suggested_booking_date` / `suggested_booking_time`.
- `RescheduleOption.objects.filter(...).update(recommendation=False)` attempted to place a Boolean into a ForeignKey.
- stale code referenced `slot['booked_capacity']` although the slot payload did not define that key.
- recommendation counters checked `result['created'] is None` instead of checking truthiness.
- `get_reschedule_risk_impacts(queue_pause=None)` incorrectly filtered `queue_pause=None` when no pause filter was requested.
- `queues/disruptions.py` defined `get_disruption_report` twice.
- risk impact creation was nested inside the affected-ticket loop, repeatedly processing the same risk tickets.
- `get_unnotified_disruption_impact(queue_pause=None)` had the same incorrect `queue_pause=None` filter behavior.
- `rescheduling/slots.py` hard-coded 08:00–16:00 hours.
- the old slot engine derived appointment capacity from active counters rather than `BranchService.max_bookings_per_slot`.
- the old slot engine therefore disagreed with the Day 32 source of truth for normal bookings.
- `RescheduleOption.option_time` was a `TextField`, so persisted times did not round-trip as Python `time` objects expected by the current availability validator.
- model `__str__` methods assumed every booking had a registered Django user and were unsafe for guest identities.

The correct repair was to preserve useful domain records while rebuilding service logic around current Smart Q invariants.

## Architecture

```text
Branch Manager
    |
    | pause service
    v
QueuePause (active)
    |
    | live preview only
    v
get_disruption_report()
    |
    | manager resumes
    v
QueuePause (finished)
    |
    +--> QueueDisruptionImpact(AFFECTED)
    |
    +--> QueueDisruptionImpact(RESCHEDULE_RISK)
              |
              v
      RescheduleRecommendation
              |
              +--> up to 5 RescheduleOption rows
                        |
                        | customer selects
                        v
           fresh BranchService capacity validation
                        |
                        v
              atomic booking/ticket move
```

## One Scheduling Source of Truth

The old `rescheduling/slots.py` had its own operating hours and capacity rules. Day 35 replaces that with an adapter over `services.availability.get_slot_availability()`.

That means normal booking and disruption rescheduling now agree on:

- active branch/service mapping
- branch opening and closing time
- `Service.average_service_time` slot duration
- `BranchService.max_bookings_per_slot`
- reserved booking statuses
- online-booking capacity consumption
- past date / past slot rules
- current remaining capacity

This is the Single Source of Truth principle applied to business rules.

## Disruption Scope

`get_affected_waiting_tickets(queue_pause)` filters exactly:

```text
booking.branch      == queue_pause.branch
booking.service     == queue_pause.service
booking.booking_date== queue_pause.booking_date
ticket.status       == WAITING
```

SCHEDULED, SERVING, COMPLETED, NO_SHOW and CANCELLED tickets are not included in this affected waiting set.

## Lost Capacity and Risk

Current Smart Q does not map individual counters to individual services. Day 35 therefore does not invent a counter multiplier.

Lost capacity remains a rule-based approximation:

```text
pause duration minutes / service average_service_time
```

The tail of the affected queue is selected because those customers are furthest from service and most likely to fall outside recovered capacity.

Example:

```text
4 WAITING customers
10-minute average service time
30-minute disruption
lost capacity ~= 3
risk tickets = last 3 waiting customers
```

## Preview vs Finalization

During an active pause, duration changes every minute. Persisting risk continuously would make the recommendation set unstable.

Day 35 separates:

- **preview** — dynamic manager read while pause is active;
- **finalization** — persistent impact records after resume using the final pause duration.

This creates a deterministic audit boundary.

## Idempotency

`QueueDisruptionImpact` already has a uniqueness rule across:

```text
queue_pause + ticket + impact_type
```

Day 35 uses `get_or_create()` correctly against that constraint. Reprocessing resume cannot duplicate the same impact.

Recommendations are also one-to-one with `QueueDisruptionImpact`. Pending recommendations may refresh their option list, but finalized recommendations are not silently rewritten.

## Schema Repair

Day 35 changes:

```python
option_time = models.TextField()
```

to:

```python
option_time = models.TimeField()
```

Migration:

```text
rescheduling/migrations/0003_alter_rescheduleoption_option_time.py
```

This is not cosmetic. The Day 32 availability service compares appointment times using Python `datetime.time`; persisted option values must retain the same type after an ORM round trip.

## Capacity-Safe Recommendation Generation

`get_available_reschedule_slots()` searches from the day after the disrupted booking and returns at most five currently available slots.

Stored option capacity values are a snapshot for UI/display. They are not trusted when the user confirms the option.

## Stale Data Protection

Capacity can change after recommendations are generated. A customer may view an option while other customers consume that slot.

Therefore selection performs a fresh call to:

```python
validate_booking_slot(..., lock=True)
```

inside `transaction.atomic()`.

A stale option can return errors such as:

```text
slot_full
past_slot
past_date
invalid_slot
service_not_offered
```

The API returns `409 Conflict` for these state conflicts.

## Atomic Customer Selection

Approved workflow:

```text
customer selects option
        |
        v
lock option / recommendation
        |
        v
fresh slot validation + BranchService lock
        |
        v
mark selected + APPROVED
        |
        v
lock booking + ticket
        |
        v
revalidate destination
        |
        v
move booking + reset check-in
        |
        v
Priority SCHEDULED ticket + new P### number
        |
        v
recommendation APPLIED
        |
        v
confirmation notification
```

The outer orchestration function `select_and_apply_reschedule_option()` raises `RescheduleWorkflowError` on any business failure so Django rolls back the whole transaction.

This prevents a partial state such as:

```text
Recommendation = APPROVED
Booking = still on old date
```

## Queue Lifecycle Preservation

A disruption reschedule is still a future appointment.

After apply:

```text
Booking.status       = PENDING
Booking.checked_in_at= None
QueueTicket.status   = SCHEDULED
QueueTicket.queue_type = PRIORITY
QueueTicket.queue_number = P###
QueueTicket.assigned_counter = None
```

The customer must check in again before the ticket can become WAITING.

This preserves the global Smart Q invariant:

> No check-in means the customer is not in the live queue.

## Priority Compensation

The organisation caused the disruption, so approved Day 35 behavior gives the displaced customer Priority on the replacement appointment.

Queue type and queue-number prefix are updated together. A Priority reschedule cannot keep an `A###` number; Day 35 regenerates a `P###` ticket number for the destination date.

## Manager APIs

```http
POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET  /api/v1/rescheduling/pauses/<pause_id>/
POST /api/v1/rescheduling/pauses/<pause_id>/resume/
```

Manager access uses `IsBranchManager` plus object-level branch authorization. Branch Managers remain scoped to their assigned branch; System Admin remains global.

## Customer APIs

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<option_id>/select/
```

The list endpoint filters through `booking__user=request.user`.

The select endpoint resolves the option with:

```text
option.id
+
recommendation.booking.user == request.user
```

An authenticated customer cannot change another customer's booking by guessing an option ID.

## Notifications

Finished disruption impacts use the existing notification service for registered users.

After a successful replacement booking move, Smart Q creates the existing `Reschedule confirmed` notification with the new date, time and queue number.

Guest walk-ins do not have an account inbox. External/assisted guest notification remains a future channel decision and is not fabricated by Day 35.

## Testing Strategy

Day 35 uses integration-heavy regression tests because the repaired flow crosses queues, bookings, services, notifications and rescheduling.

Coverage includes:

- manager can pause an offered branch service;
- unmapped service is rejected;
- cross-branch manager access is denied;
- Counter Staff cannot create disruptions;
- a 30-minute outage on a 10-minute service produces 3 risk customers from 4 waiting customers;
- resume persists affected and risk impacts;
- recommendations generate five options;
- option times round-trip as `time` values;
- repeated resume processing is idempotent;
- direct selection applies Priority but returns the booking to SCHEDULED/PENDING;
- stale capacity is rejected;
- customer recommendation list returns only the authenticated customer's records;
- customer cannot select another customer's option;
- customer selection moves booking/ticket and creates confirmation notification;
- failed stale-slot customer selection rolls back selection and approval.

## CI

The GitHub Actions workflow now includes:

```powershell
python manage.py test rescheduling
```

and triggers on:

```text
feature/day35-disruption-rescheduling
```

The first Day 35 implementation CI run (`33366488282`) completed successfully before customer-selection APIs were added. Final customer-selection CI is verified separately at the final Day 35 head.

## Engineering Concepts

Day 35 demonstrates:

- legacy-code forensic audit
- preserving domain models while replacing unsafe service logic
- Single Source of Truth
- adapters around reusable domain services
- schema/type correctness
- database migrations
- idempotent processing
- deterministic event finalization
- live preview vs persisted audit state
- transactional orchestration
- row locking
- stale-read protection
- optimistic UI snapshot vs authoritative revalidation
- ownership authorization
- lifecycle invariants
- cross-domain integration testing
- business error codes
- rollback semantics

## Known Limitations

- lost service capacity is still an approximation based on pause duration and average service time because counters are not mapped per service;
- no external SMS/email/WhatsApp delivery for guest identities;
- queue-number generation is still vulnerable to concurrency races until the planned PostgreSQL/concurrency hardening milestone;
- no full QueueEvent timeline exists yet;
- historical actual wait/service-time analytics remain unavailable until event history is persisted.

## Day 36 Handoff

Day 36 should introduce queue lifecycle event history / timestamps. That will provide an auditable transition timeline and unlock truthful historical waiting-time and service-time analytics.
