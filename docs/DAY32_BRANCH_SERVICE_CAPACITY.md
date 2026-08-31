# Day 32 - Branch-Service Mapping and Booking Capacity

## Objective

Day 32 makes Smart Q's appointment system operationally truthful by teaching the backend two things it did not previously know:

1. which services each branch actually offers; and
2. how many online appointments each branch/service can accept in one generated time slot.

The frontend is no longer expected to invent appointment times or assume that every service exists at every branch.

---

## Product rules confirmed

The approved rules are:

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

Example:

```text
Pretoria + ID Application
average service time = 20 minutes
max bookings per slot = 4

08:00 -> capacity 4
08:20 -> capacity 4
08:40 -> capacity 4
...
```

A different branch can configure a different capacity for the same service.

---

## New BranchService model

`services.models.BranchService` connects one branch to one service:

```text
BranchService
├── branch
├── service
├── max_bookings_per_slot
├── is_active
└── created_at
```

The `(branch, service)` pair is unique.

`max_bookings_per_slot` must be at least 1.

Slot duration is intentionally not duplicated on BranchService. The linked `Service.average_service_time` remains the single source of truth for duration.

---

## Service discovery flow

```text
Customer selects branch
        ↓
GET branch services
        ↓
Customer selects one offered service
        ↓
GET capacity-aware availability for date
        ↓
Customer selects one generated available slot
        ↓
POST booking
        ↓
Backend validates the slot again
```

---

## APIs

### Global service catalogue

```http
GET /api/v1/services/
```

### Services offered at a branch

```http
GET /api/v1/services/branches/<branch_id>/
```

This returns only active `BranchService` mappings whose branch and service are active.

### Availability

```http
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

Example response shape:

```json
{
  "branch": 1,
  "service": 2,
  "date": "2026-09-01",
  "slot_duration_minutes": 20,
  "max_bookings_per_slot": 4,
  "slots": [
    {
      "time": "08:00:00",
      "capacity": 4,
      "booked": 2,
      "remaining": 2,
      "is_available": true
    }
  ]
}
```

---

## Slot generation

Slots begin at the branch opening time.

The next slot starts after `Service.average_service_time` minutes.

A slot is included only when the full service duration fits before branch closing time.

Example:

```text
Branch hours: 08:00 - 10:00
Service duration: 20 minutes

Valid starts:
08:00
08:20
08:40
09:00
09:20
09:40
```

---

## Capacity accounting

Only online appointments reserve future appointment capacity.

The following online booking states reserve a slot:

```text
PENDING
CONFIRMED
COMPLETED
NO_SHOW
```

`CANCELLED` does not reserve capacity, so cancelling an appointment releases its slot.

Guest walk-ins do not consume future appointment capacity because they enter the live queue immediately rather than reserving an appointment slot.

---

## Backend enforcement

The availability API is advisory for the frontend, but the backend does not trust it as the final authority.

Booking creation validates again that:

- the branch is active;
- the service is active;
- an active BranchService mapping exists;
- the requested date is not in the past;
- the requested time is exactly one of the generated slots;
- today's slot has not passed;
- the slot still has remaining capacity.

Rescheduling applies the same validation to the destination slot.

Guest walk-in creation also rejects a service that the selected branch does not offer.

---

## Concurrency design

`BookingCreateSerializer.create()` and `BookingRescheduleSerializer.update()` run inside `transaction.atomic()` and re-check the slot using `select_for_update()` on the BranchService mapping.

This establishes the correct row-lock design for PostgreSQL so concurrent writes for the same branch/service are serialized before consuming final capacity.

SQLite remains the development database and is not treated as the final production concurrency guarantee.

---

## Django Admin

`BranchService` is registered in Django Admin so authorised administrators can configure:

- branch;
- service;
- `max_bookings_per_slot`;
- active/inactive state.

This is configuration, not customer-controlled input.

---

## Tests

Day 32 adds coverage for:

- service-duration slot generation;
- branch service filtering;
- unmapped service rejection;
- remaining-capacity calculations;
- full-slot behavior;
- cancelled booking releasing capacity;
- walk-ins not consuming appointment capacity;
- availability API metadata;
- valid booking creation;
- non-generated time rejection;
- full-slot booking rejection;
- reschedule-to-full-slot rejection;
- guest walk-in rejection for an unoffered service.

Day 31 booking fixtures were updated to create an explicit BranchService mapping rather than weakening the new production invariant.

---

## CI

The workflow now includes:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test services
python manage.py test queues
python manage.py test bookings
python manage.py test notifications
python manage.py test
```

---

## Known limitations

Day 32 intentionally does not yet model:

- different service hours from the branch's overall opening hours;
- lunch breaks or blackout intervals;
- public holidays / branch closure calendars;
- per-day capacity overrides;
- staff-driven dynamic capacity;
- PostgreSQL production deployment;
- database-level slot reservation rows.

Those can be layered on later without changing the current BranchService abstraction.

---

## Next objective

The next operational slice should focus on counter lifecycle and staff-to-counter assignment so branch capacity, queue demand, and actual service resources can eventually be connected.
