# Smart Q - Day 33: Counter Lifecycle + Staff Assignment

## Objective

Day 33 connects Smart Q queue operations to the actual counter and staff member serving customers.

Before Day 33, Counter already had OPEN/CLOSED/PAUSED states, but no staff assignment existed. Any authorised Counter Staff user in the branch could therefore operate any branch counter. Day 33 makes counter ownership explicit and operational state trustworthy.

## Confirmed product rules

- Branch Manager assigns Counter Staff within their own branch.
- System Admin can assign globally.
- Counter Staff cannot self-assign.
- One counter has at most one assigned staff user.
- One staff user can be assigned to at most one counter.
- Assigned user must have COUNTER_STAFF role.
- Assigned Counter Staff must belong to the same branch as the counter.
- Assigned Counter Staff may OPEN, PAUSE, RESUME, and CLOSE their own counter.
- Branch Manager/System Admin may control counters in their authorised scope.
- PAUSE stops Call Next but the current customer may still be completed/no-show.
- CLOSE is blocked while a customer is currently SERVING.
- Assignment/reassignment is changed only while the counter is CLOSED and idle.
- An unassigned counter cannot be opened.

## Counter lifecycle

```text
UNASSIGNED
    ↓ manager/admin assigns Counter Staff
CLOSED
    ↓ OPEN
OPEN
  ├── Call Next
  ├── PAUSE
  │      ↓ RESUME
  │     OPEN
  └── CLOSE (only if idle)
         ↓
       CLOSED
```

## Model change

`Counter.assigned_staff` is a nullable `OneToOneField` to the Django user model.

The OneToOne relationship provides a database-level guarantee that one staff user cannot be assigned to multiple counters simultaneously.

Role and same-branch validation are enforced by the counter assignment service.

## Active counter semantics

An active counter now means:

```text
status = OPEN
AND assigned_staff IS NOT NULL
```

This matters because Smart Q uses active counter counts in wait-time estimation. An accidentally OPEN but unstaffed counter must not reduce a customer's ETA.

## APIs

```http
GET  /api/v1/counters/my/
GET  /api/v1/counters/branches/<branch_id>/
POST /api/v1/counters/<counter_id>/assign/
POST /api/v1/counters/<counter_id>/unassign/
POST /api/v1/counters/<counter_id>/open/
POST /api/v1/counters/<counter_id>/pause/
POST /api/v1/counters/<counter_id>/resume/
POST /api/v1/counters/<counter_id>/close/
```

Assignment request:

```json
{
  "staff_user_id": 12
}
```

## Queue operation hardening

Existing queue actions remain:

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Day 33 adds an assignment check for normal Counter Staff. A same-branch Counter Staff user can no longer operate another counter simply by knowing its ID.

Branch Manager and System Admin retain their approved operational override.

## Pause behavior

PAUSED means:

- Call Next is blocked because the counter is not OPEN.
- If a customer is already SERVING, Complete and No Show remain available.
- The counter can later RESUME to OPEN.

This lets a staff member stop accepting new customers without abandoning the customer already at the counter.

## Close behavior

CLOSE is rejected while a SERVING ticket is assigned to the counter.

The current customer must first become COMPLETED or NO_SHOW, which releases `assigned_counter` on the ticket. The counter may then close safely.

## Assignment safety

Assignment/reassignment requires:

```text
counter.status = CLOSED
current SERVING ticket = none
staff role = COUNTER_STAFF
staff branch = counter branch
staff not assigned elsewhere
```

## Migration

```text
counters/migrations/0003_counter_assigned_staff.py
```

## Tests

Day 33 counter tests cover:

- Branch Manager can assign same-branch Counter Staff.
- Counter Staff cannot self-assign.
- Cross-branch staff assignment is rejected.
- One staff user cannot be assigned to two counters.
- Unassigned counter cannot open.
- Assigned staff can open/pause/resume/close their counter.
- Counter Staff cannot operate another same-branch counter.
- Paused counter cannot Call Next but can finish the current customer.
- Busy counter cannot close or change assignment.
- Only staffed OPEN counters count as active capacity.
- Counter Staff can read their current assignment.

Existing queue regression fixtures were updated so OPEN counters are explicitly assigned to the staff user operating them.

## CI workflow

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test services
python manage.py test counters
python manage.py test queues
python manage.py test bookings
python manage.py test notifications
python manage.py test
```

## Security reasoning

Day 33 strengthens least privilege:

```text
COUNTER_STAFF
    ↓
assigned branch
    ↓
assigned counter
    ↓
queue mutation
```

A Counter Staff role alone is no longer enough to mutate every counter in the branch.

## Known limitations

- Counter creation/configuration still relies primarily on Django Admin.
- Shift scheduling/history is not yet modeled.
- Staff replacement history/audit events are not yet persisted as QueueEvent records.
- Service-specific counter capability is not modeled yet; counters remain General/Priority queue-type based.
- PostgreSQL production concurrency hardening remains future work.

## Day 34 recommendation

Manager Dashboard APIs should be next. Day 33 now gives the manager layer trustworthy data about:

- open/paused/closed counters,
- assigned staff,
- free/busy counters,
- live waiting queues,
- queue type capacity.

That is the operational foundation required for a meaningful live branch dashboard.
