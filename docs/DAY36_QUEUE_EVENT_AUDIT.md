# Day 36 - QueueEvent Lifecycle History and Audit Trail

## Objective

Day 36 adds a durable, append-only operational history to Smart Q. Before this milestone, models such as `QueueTicket`, `Booking`, and `Counter` could tell the system their **current** state, but the backend could not reliably explain the sequence of transitions that produced that state.

The Day 36 goal is therefore not to replace current-state models. It is to persist the important lifecycle facts that happen beside those state changes and expose them through least-privilege audit APIs.

## Approved product rules

1. `QueueEvent` is audit/history data. It does not replace Smart Q's queue ETA calculation.
2. Estimated waiting time remains deterministic:

```text
estimated_wait_time = people_ahead * Service.average_service_time
```

3. Active counter count does not divide the approved ETA formula.
4. If a branch opens at 08:00, customer service starts at 08:00. Smart Q adds no staff-preparation buffer before opening time.
5. Customer audit access is limited to the customer's own booking.
6. Branch Manager audit access is limited to the manager's assigned branch.
7. System Admin can read the audit history for any branch.
8. Receptionist and Counter Staff do not receive the full historical audit trail; they keep their existing live operational views.
9. Event metadata must not contain protected priority inputs such as pregnancy/disability data.

## Why events are separate from current state

Current state answers:

```text
Where is this ticket now?
What is this booking status now?
Is this counter open now?
```

Event history answers:

```text
What happened?
When did it happen?
Which booking/ticket/counter was affected?
Who caused the transition?
What were the before/after states?
```

Keeping these concerns separate avoids turning operational tables into an unreliable mixture of current state and historical snapshots.

## QueueEvent model

Day 36 adds `QueueEvent` to `queues/models.py` and migration:

```text
queues/migrations/0007_queueevent.py
```

The model stores:

- event type;
- optional ticket reference;
- optional booking reference;
- optional counter reference;
- branch and service context;
- actor user reference;
- actor username snapshot;
- actor role snapshot;
- source (`system`, `customer`, `staff`);
- ticket status before/after;
- booking status before/after;
- queue number/type snapshots;
- non-sensitive JSON metadata;
- `occurred_at` timestamp.

Indexes support later audit/report queries by branch, booking, ticket, counter, event type and time.

## Event types

The first Day 36 event vocabulary includes:

```text
TICKET_SCHEDULED
CHECKED_IN
CALLED
COMPLETED
NO_SHOW
CANCELLED
RESCHEDULED
DISRUPTION_RESCHEDULED
COUNTER_OPENED
COUNTER_PAUSED
COUNTER_RESUMED
COUNTER_CLOSED
COUNTER_STAFF_ASSIGNED
COUNTER_STAFF_UNASSIGNED
```

The vocabulary records facts the backend can currently prove. New business events should be added only when there is a real state transition to support them.

## Event recorder

`queues/events.py` contains the reusable `record_queue_event(...)` service.

This avoids scattering raw `QueueEvent.objects.create(...)` calls across unrelated apps. The helper derives branch/service context, classifies the actor source, snapshots the actor username/role and creates one event record.

The recorder deliberately accepts `actor=None` so system jobs and older internal service callers remain compatible.

## Transaction rule

An event and the state change it describes must belong to the same transaction.

Unsafe pattern:

```text
1. change ticket state
2. commit
3. later try to write audit event
```

If step 3 fails, the audit trail lies by omission.

Also unsafe:

```text
1. write event
2. state change fails
```

The event would claim something happened when it did not.

Day 36 therefore appends lifecycle events inside the same transactional services that mutate the relevant operational state.

## Lifecycle coverage

### Booking / queue

Event writes now cover:

- scheduled ticket creation;
- registered customer check-in;
- staff/reception check-in;
- guest walk-in live activation;
- unchecked appointment expiry cancellation;
- Call Next (`WAITING -> SERVING`);
- completion;
- no-show;
- customer cancellation;
- ordinary customer rescheduling;
- disruption compensation rescheduling.

### Counter

Event writes also cover:

- Counter Staff assignment;
- Counter Staff unassignment;
- counter open;
- counter pause;
- counter resume;
- counter close.

This removes the old limitation where manager reporting could only state that counter information represented current live state and had no historical lifecycle source.

## Actor snapshots

`actor` references the current Django user, but Day 36 also stores:

```text
actor_username
actor_role
```

This matters because accounts evolve. A staff member can later be reassigned or have their role changed. The event should still explain who/what role performed the transition at that point in time.

## Privacy rule

The event audit must not become a second database for sensitive priority inputs.

Do not place the following in `QueueEvent.metadata`:

- pregnancy status;
- disability status;
- protected medical/priority reasoning.

Queue type may be snapshotted because it is an operational ticket fact. The private reasons used to derive it remain outside the audit metadata.

## ETA correction recorded during Day 36

Day 36 review found that `queues/waiting_time.py` still divided the waiting-time estimate by active counters.

The approved Smart Q rule is now encoded directly:

```python
def calculate_estimated_wait_time(ticket):
    people_ahead = get_people_ahead(ticket)
    estimated_wait_time = people_ahead * ticket.booking.service.average_service_time
    return round(estimated_wait_time)
```

This change was explicitly approved. QueueEvent timestamps do **not** replace this rule and no event-derived waiting-time calculation remains in the Day 36 branch.

## Audit APIs

### Customer-owned timeline

```http
GET /api/v1/queues/bookings/<booking_id>/timeline/
```

Authorization:

```text
authenticated user
AND Booking.user == request.user
```

Changing the booking ID cannot expose another customer's history; the lookup returns `404` when the booking is not owned by the authenticated customer.

The customer representation is intentionally narrower than management audit data. It includes lifecycle/status facts and counter identity where relevant, but does not expose actor usernames/roles or raw metadata.

### Branch management audit

```http
GET /api/v1/queues/branches/<branch_id>/events/
```

Authorization:

```text
Branch Manager -> assigned branch only
System Admin   -> any active branch
Receptionist   -> denied
Counter Staff  -> denied
Customer       -> denied
```

The manager representation contains the operational audit fields required to trace actor, source, booking, ticket, counter, service and before/after states.

## Ordering

Customer booking timelines are returned chronologically so the customer can read the lifecycle from beginning to current state.

Branch audit events are returned newest-first so managers see the most recent operational activity first.

## Tests

Day 36 adds:

```text
queues/test_day36_events.py
queues/test_day36_audit_api.py
```

The lifecycle suite verifies:

- scheduled and check-in events;
- customer actor snapshots;
- Call Next event counter/staff context;
- before/after ticket states;
- chronological ticket history;
- counter assignment/open/pause/resume/close reconstruction.

The audit API suite verifies:

- customer can read own booking timeline;
- customer receives 404 for another customer's booking;
- customer response excludes management actor/metadata fields;
- Branch Manager can read own branch;
- Branch Manager receives 403 for another branch;
- System Admin can read either branch;
- Receptionist cannot read the full branch audit;
- Counter Staff cannot read the full branch audit.

## CI

The GitHub Actions workflow now runs a dedicated Day 36 step:

```powershell
python manage.py test queues.test_day36_events queues.test_day36_audit_api
```

The full regression suite still runs afterward:

```powershell
python manage.py test
```

This provides a focused signal for the event/audit domain while continuing to protect all previously implemented Smart Q behavior.

## Engineering concepts demonstrated

### Append-only history

Operational history is represented as events rather than repeatedly overwriting an audit row.

### Snapshot + foreign key

The event keeps foreign-key references where useful but also snapshots human-readable actor/queue fields that could change later.

### Transactional consistency

Audit facts and operational state commit or roll back together.

### Least privilege

Historical visibility is narrower than live operational visibility. A Receptionist may need to search/check in customers without needing the full branch history.

### Ownership authorization

Customer audit access is based on record ownership, not merely authentication.

### Single responsibility

QueueEvent records history. `queues/waiting_time.py` calculates the approved ETA. Neither subsystem silently replaces the other's job.

## Known limitations

1. Events begin after the Day 36 migration; Smart Q does not fabricate historical events for old rows.
2. Event history improves future reporting but Day 39 will decide which aggregate reports are actually required.
3. Queue-number generation still needs Day 38 concurrency hardening.
4. Development configuration still uses SQLite and non-production settings until Day 38.
5. Full System Admin CRUD/account-security work remains for Day 37.

## Day 37 handoff

Day 37 should focus on backend management/security gaps rather than extending queue behavior:

- System Admin management APIs for branches/services/BranchService/staff;
- role and branch assignment controls;
- account deactivation;
- password reset/account-security decisions;
- login throttling/brute-force protection;
- automated execution strategy for reminder processing;
- final account/permission hardening.

The Day 40 backend deadline remains unchanged. Day 36 should be treated as the audit-history milestone, not a reason to expand the queue product scope.
