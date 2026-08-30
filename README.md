# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and operationally efficient.

The product is built around the full service journey: account creation, appointment booking, online/in-person check-in, live queue tracking, reception workflows, counter service, disruptions, rescheduling, notifications, management visibility, and eventually data-driven waiting-time prediction.

> **Current development state:** Days 28–31 are integrated into `main`. Day 32 branch-service mapping and capacity-aware appointment scheduling are implemented and under verification on `feature/day32-branch-service-capacity`.

---

## Product Principle

Smart Q exists so customers do not need to stand physically in a queue just to hold a place in it.

A **check-in means live-queue activation**. It may happen online or in person.

```text
ADVANCE APPOINTMENT
        ↓
SCHEDULED
        ↓
6 HOURS BEFORE APPOINTMENT
        ↓
CHECK-IN OPENS
        ↓
ONLINE CHECK-IN OR STAFF CHECK-IN
        ↓
WAITING
        ↓
CALL NEXT
        ↓
SERVING
   ├── COMPLETED
   └── NO_SHOW
```

If the appointment time passes and the customer never checked in, the booking becomes `CANCELLED`. The customer was never in the live queue, therefore that outcome is not a no-show.

---

## Architecture

Smart Q is currently a Django modular monolith:

```text
Frontend / API Client
        ↓
Django REST Framework APIs
        ↓
Authentication + Role/Branch Permissions
        ↓
Serializers
        ↓
Business Logic / Service Layer
        ↓
Django Models / ORM
        ↓
Database
```

Current apps:

```text
accounts
branches
services
bookings
queues
counters
notifications
rescheduling
```

Queue order, priority, check-in eligibility, appointment availability, capacity, expiry, and operational state transitions are backend decisions rather than frontend-controlled values.

---

## Smart Q Roles

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

| Role | Current authorization |
|---|---|
| Customer | Own account/bookings/queue only |
| Receptionist | Branch queue reads, search, customer check-in, guest walk-ins |
| Counter Staff | Branch queue reads/operations + reception-compatible check-in |
| Branch Manager | Branch operational access |
| System Admin | Global operational access |

---

## Authentication APIs

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

Public registration always creates a normal `CUSTOMER` account. Caller-supplied privilege fields cannot create staff/admin authority.

---

## Day 32: Branch-Service Mapping

Before Day 32, `Service` was global and a customer could theoretically submit any active service with any active branch.

Day 32 introduces `BranchService`:

```text
BranchService
├── branch
├── service
├── max_bookings_per_slot
├── is_active
└── created_at
```

The `(branch, service)` combination is unique.

This model answers two operational questions:

```text
Does this branch offer this service?
How many online appointments can it accept per slot?
```

A service can have different capacity at different branches.

---

## Day 32: Slot and Capacity Rules

Approved scheduling rules:

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

Example:

```text
Pretoria + ID Application
Service.average_service_time = 20 minutes
BranchService.max_bookings_per_slot = 4

08:00 -> 4 appointments
08:20 -> 4 appointments
08:40 -> 4 appointments
09:00 -> 4 appointments
...
```

Slots start at branch opening time and are emitted only when the full service duration fits before branch closing time.

The frontend does not invent booking times. It requests backend-generated availability.

---

## Service and Availability APIs

### Global service catalogue

```http
GET /api/v1/services/
```

### Services offered by a branch

```http
GET /api/v1/services/branches/<branch_id>/
```

Only active mappings with active branches/services are returned.

### Capacity-aware appointment slots

```http
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

Response includes:

```text
slot duration
max bookings per slot
booked count
remaining capacity
is_available
```

Example slot:

```json
{
  "time": "08:20:00",
  "capacity": 4,
  "booked": 3,
  "remaining": 1,
  "is_available": true
}
```

---

## Capacity Accounting

Only **online appointments** reserve appointment capacity.

These states retain the historical/reserved slot:

```text
PENDING
CONFIRMED
COMPLETED
NO_SHOW
```

`CANCELLED` releases the appointment slot.

Guest walk-ins do not consume future appointment capacity because they enter the live queue immediately rather than reserving a future appointment slot.

---

## Backend Booking Enforcement

The availability endpoint is not trusted as the final authority. Booking creation and rescheduling validate the selected slot again.

The backend rejects:

- a service not offered at the branch;
- a past date;
- a time that is not a generated slot;
- a slot that has already passed today;
- a fully booked slot.

The final create/update runs inside `transaction.atomic()` and re-checks capacity with a `select_for_update()` lock on the BranchService mapping. This establishes the correct PostgreSQL row-lock design for later production hardening.

Guest walk-ins remain immediate but are also restricted to services offered by the selected branch.

---

## Booking and Check-In APIs

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
POST  /api/v1/bookings/<id>/staff-check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Check-in opens exactly **6 hours before the appointment datetime**.

Once the customer checks in:

```text
Booking.checked_in_at = activation timestamp
QueueTicket.status = WAITING
```

`checked_in_at` means live-queue activation, not necessarily physical presence.

---

## Reception APIs

```http
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
```

A guest walk-in does not require a Smart Q account.

The backend creates:

```text
GuestCustomer
Booking.source = WALK_IN
Booking.checked_in_at = now
QueueTicket.status = WAITING
```

Guest walk-ins use the same automatic General/Priority rules as registered customers.

---

## Priority Policy

Queue type is assigned by the backend.

Current priority conditions:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The customer/receptionist does not manually select General or Priority.

---

## Live Queue APIs

```http
GET  /api/v1/queues/my-current/
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/queues/counters/<counter_id>/current/
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Live queue order uses check-in time rather than booking creation time.

---

## Waiting-Time Estimate

Current waiting-time calculation is deterministic:

```text
Estimated Wait ≈
(People Ahead × Average Service Time) ÷ Active Counters
```

It is **not yet ML**.

---

## Check-In Reminders

Advance online appointments receive an in-app reminder every hour during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The same background service cancels appointments whose time passed without check-in.

---

## Django Admin

Administrators can configure BranchService mappings through Django Admin, including:

```text
branch
service
max_bookings_per_slot
is_active
```

This operational configuration is not customer-controlled input.

---

## Automated Verification

GitHub Actions currently runs:

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

Day 32 adds explicit service/capacity and booking-capacity regression coverage while preserving earlier authentication, queue, reception, walk-in, and reminder tests.

---

## Documentation

Permanent engineering records:

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
docs/DAY31_RECEPTION_WALKINS.md
docs/DAY32_BRANCH_SERVICE_CAPACITY.md
```

---

## Current Git State

Days 28–31 are integrated into `main`.

```text
main
  ↑
feature/day32-branch-service-capacity
```

---

## Current Backend Capabilities

Smart Q now includes:

- customer accounts and session authentication;
- Smart Q roles and branch authorization;
- branches and global services;
- explicit BranchService availability mapping;
- per-branch/per-service appointment capacity;
- service-duration-based appointment slot generation;
- public branch-service discovery;
- public capacity-aware availability lookup;
- backend enforcement of valid booking slots;
- booking create/list/detail/cancel/reschedule;
- online and staff check-in;
- six-hour check-in opening window;
- hourly check-in reminder engine;
- automatic cancellation of expired unchecked appointments;
- reception booking/customer search;
- guest walk-ins without accounts;
- shared guest/registered priority rules;
- live waiting queues;
- queue position and rule-based ETA;
- counter Call Next / Complete / No Show;
- Booking ↔ QueueTicket state synchronization;
- disruption/rescheduling backend foundation;
- in-app notifications;
- queue statistics foundation;
- automated DRF regression tests;
- GitHub Actions CI.

---

## Important Remaining Operational Gaps

Next major backend work:

1. Counter lifecycle APIs and staff-to-counter assignment.
2. Manager live dashboard APIs.
3. Manager disruption/rescheduling APIs.
4. Historical QueueEvent timestamps for analytics and ML.
5. Branch/service blackout periods, closure calendars, and capacity overrides.
6. External notification channels.
7. Password reset/account verification and throttling.
8. PostgreSQL and queue-number concurrency hardening.
9. Production secrets, HTTPS, logs, monitoring, and backups.
10. Real-time delivery strategy.
11. Genuine trained/evaluated ML waiting-time forecasting.

---

## Roadmap

### Operational MVP foundation

```text
Profiles
Accounts / Login
Roles + Branch Permissions
Branches
Services
Branch-Service Mapping
Booking Availability / Capacity
Bookings
Queue Tickets
Priority Logic
Online / Staff Check-In
Reception Search
Guest Walk-Ins
Hourly Check-In Reminders
Expiry Cancellation
Queue Operations
Live Queue Reads
Notifications
Automated Tests
CI
```

### Next operational phase

```text
Counter Lifecycle
Staff Assignment
Manager APIs
Historical Queue Events
Advanced branch calendars/capacity overrides
```

### Production phase

```text
PostgreSQL
Secure configuration
Authentication deployment policy
External notifications
Real-time delivery
Monitoring
Backups
Audit/compliance
```

### Analytics + AI phase

```text
Historical queue-event dataset
Actual wait/service-duration measurement
Demand and peak-hour analysis
Model training
Model evaluation
ML wait prediction
Operational recommendations
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication | Django sessions |
| Authorization | Profile roles + object-level branch permissions |
| Language | Python |
| Development DB | SQLite |
| Target production DB | PostgreSQL |
| Internal administration | Django Admin |
| Tests | Django + DRF APITestCase |
| CI | GitHub Actions |
| Background-job foundation | Scheduler-agnostic Django command |
| Future AI | Trained/evaluated wait-time forecasting |

---

## Local Setup

```powershell
git clone https://github.com/Katlegojack/SmartQ.git
cd SmartQ
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Verify:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

---

## Product Maturity

| Stage | Meaning | Current position |
|---|---|---|
| Pitch prototype | Product journey can be demonstrated | Strong foundation |
| Pilot operational MVP | Real customer/reception/staff workflow at one branch | In progress, significantly advanced |
| Production platform | Secure, monitored, scalable, enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

Day 32 makes appointment booking substantially more realistic: the system now knows what each branch offers, generates valid service-duration slots, and enforces actual per-slot capacity on the backend.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
