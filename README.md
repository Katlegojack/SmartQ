# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Days 28-32 are integrated into `main`. Day 33 counter lifecycle and staff-to-counter assignment are implemented on `feature/day33-counter-lifecycle`.

## Product principle

Smart Q exists so customers do not need to stand physically in a queue just to hold a place in it.

A check-in means **live-queue activation**. It may happen online or in person.

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

If appointment time passes without check-in, the booking becomes `CANCELLED` because the customer never entered the live queue.

## Architecture

```text
Frontend / API Client
        ↓
Django REST Framework APIs
        ↓
Authentication + Role/Branch/Counter Permissions
        ↓
Serializers
        ↓
Business Logic / Service Layer
        ↓
Django ORM
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

## Roles

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

| Role | Current operational scope |
|---|---|
| Customer | Own account, bookings and live queue |
| Receptionist | Branch queue reads, booking search, staff check-in, guest walk-ins |
| Counter Staff | Branch queue reads + mutations on their assigned counter |
| Branch Manager | Own-branch counter assignment and operational override |
| System Admin | Global operational access |

## Authentication APIs

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

Public registration always creates a normal Customer account.

## Branch-service mapping and capacity

A service must be explicitly offered by a branch through `BranchService`.

```text
BranchService
├── branch
├── service
├── max_bookings_per_slot
└── is_active
```

Approved scheduling rules:

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

### Service availability APIs

```http
GET /api/v1/services/
GET /api/v1/services/branches/<branch_id>/
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

The backend rejects unoffered services, non-generated times, past slots and fully-booked slots.

Cancelled appointments release future slot capacity. Guest walk-ins do not reserve future appointment capacity.

## Booking and check-in APIs

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
POST  /api/v1/bookings/<id>/staff-check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Check-in opens exactly six hours before appointment time.

## Reception APIs

```http
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
```

Guest walk-ins require no Smart Q account and enter `WAITING` immediately.

## Priority policy

Queue type is backend-controlled.

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The same rules apply to registered customers and guest walk-ins.

## Day 33: Counter lifecycle

A Counter now has explicit staff ownership.

```text
Counter
├── branch
├── counter_number
├── queue_type
├── assigned_staff
├── status
└── created_at
```

`assigned_staff` is a OneToOne relationship. This enforces one staff member -> at most one counter.

### Counter lifecycle

```text
UNASSIGNED
    ↓ Manager/Admin assigns Counter Staff
CLOSED
    ↓ OPEN
OPEN
  ├── Call Next
  ├── PAUSE
  │      ↓ RESUME
  │     OPEN
  └── CLOSE
         ↓
       CLOSED
```

Rules:

- Counter Staff cannot assign themselves.
- Branch Manager assigns same-branch Counter Staff.
- System Admin can assign globally.
- Assigned user must have `COUNTER_STAFF` role.
- Staff and counter must belong to the same branch.
- One staff user cannot be assigned to two counters.
- An unassigned counter cannot open.
- Assignment changes require a CLOSED, idle counter.
- PAUSE blocks Call Next but the current customer may still be completed/no-show.
- CLOSE is blocked while a customer is currently being served.
- Counter Staff can mutate only their assigned counter.
- Branch Manager/System Admin retain their authorised override.

### Counter APIs

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

## Live queue APIs

```http
GET  /api/v1/queues/my-current/
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/queues/counters/<counter_id>/current/
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Counter Staff queue mutations are now assignment-aware.

## Waiting-time estimate

Current waiting time is deterministic, not ML:

```text
Estimated Wait ≈
(People Ahead × Average Service Time) ÷ Active Counters
```

Day 33 strengthens `Active Counters` to mean:

```text
Counter.status = OPEN
AND Counter.assigned_staff IS NOT NULL
```

An unstaffed counter therefore cannot artificially reduce a customer's ETA.

## Check-in reminders

Advance online appointments receive hourly in-app reminders during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The same processor cancels unchecked appointments after their appointment time passes.

## Automated verification

GitHub Actions runs:

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

Day 33 adds explicit counter lifecycle tests while retaining all earlier regression suites.

## Permanent engineering documentation

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
docs/DAY31_RECEPTION_WALKINS.md
docs/DAY32_BRANCH_SERVICE_CAPACITY.md
docs/DAY33_COUNTER_LIFECYCLE.md
```

## Current backend capabilities

Smart Q now includes:

- authentication and customer registration;
- role + branch authorization;
- branch/service catalogues;
- BranchService mapping;
- capacity-aware appointment slots;
- appointment creation/rescheduling validation;
- six-hour online/in-person check-in;
- hourly reminder engine;
- automatic unchecked-appointment cancellation;
- branch-scoped reception search;
- guest walk-ins without accounts;
- backend General/Priority assignment;
- live waiting queues;
- rule-based queue position and ETA;
- explicit staff-to-counter assignment;
- counter OPEN/PAUSE/RESUME/CLOSE lifecycle;
- assignment-aware Call Next/Complete/No Show;
- in-app notifications;
- automated tests and GitHub Actions CI.

## Remaining major backend work

1. Manager live dashboard APIs.
2. Manager disruption/rescheduling APIs.
3. Historical QueueEvent timeline/audit data.
4. Account verification, password reset and throttling.
5. External notification channels.
6. PostgreSQL and concurrency hardening.
7. Production secrets/HTTPS/logging/monitoring/backups.
8. Real-time delivery strategy.
9. Historical data collection and genuine ML wait forecasting.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment
Day 34  Manager Dashboard APIs
Day 35  Disruption + Rescheduling Manager APIs
Day 36  QueueEvent / Timeline / Audit
Day 37  Account Security + Notification Hardening
Day 38  PostgreSQL + Concurrency + Production Config
Day 39  Analytics / Performance
Day 40  Full Backend Integration + Security + Regression Audit
```

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication | Django sessions |
| Authorization | Profile roles + branch/counter scope |
| Development DB | SQLite |
| Target production DB | PostgreSQL |
| Admin | Django Admin |
| Tests | Django + DRF APITestCase |
| CI | GitHub Actions |

## Local setup

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

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

Day 33 makes the counter layer operationally trustworthy: an active counter now represents a real assigned staff member, and normal Counter Staff can mutate only the counter they actually own.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
