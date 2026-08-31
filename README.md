# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Days 28-33 are integrated into `main`. Day 34 manager dashboard read-model APIs are implemented on `feature/day34-manager-dashboard` and are under final regression verification.

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
Serializers / Read Models
        ↓
Business Logic / Aggregation Services
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
dashboard
```

`dashboard` is intentionally a read-only aggregation app with no database model. It derives manager data from operational source-of-truth models instead of duplicating state.

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
| Branch Manager | Own-branch counter assignment, operational override and manager dashboard |
| System Admin | Global operational and dashboard access |

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

Counter Staff queue mutations are assignment-aware.

## Day 34: Manager dashboard read model

Day 34 adds a cross-domain, read-only manager view without introducing a `Dashboard` database table.

```text
Booking ---------+
QueueTicket -----+
Counter ---------+--> Dashboard aggregation service --> Manager API
Branch ----------+
Service ---------+
```

This avoids duplicated/stale dashboard state and keeps operational models as the source of truth.

### Manager dashboard API

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Access rules:

- Branch Manager: own branch only.
- System Admin: any active branch.
- Counter Staff, Receptionist and Customer: denied.

The dashboard returns:

- branch information and operating hours;
- customer activity totals;
- General/Priority lifecycle statistics;
- combined scheduled/waiting/serving/completed/no-show/cancelled totals;
- online vs walk-in booking counts;
- checked-in vs not-checked-in counts;
- service distribution;
- live counter totals;
- staffed/unstaffed counters;
- free/busy counters;
- assigned Counter Staff;
- current serving ticket/customer where applicable.

Date-scoped queue, booking and service metrics use the requested report date. Counter state is explicitly labelled `live_current_state` because historical counter transitions are not yet persisted.

Day 34 also optimises queue lifecycle counting with conditional aggregation and avoids N+1 counter-ticket queries by bulk-fetching serving tickets and indexing them by counter ID.

Smart Q deliberately does **not** claim a historical average actual waiting time yet. A trustworthy value requires the future queue-event timeline (`called_at`, completion/service events, etc.).

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
python manage.py test dashboard
python manage.py test
```

Day 34 adds explicit manager dashboard tests while retaining every earlier regression suite.

## Permanent engineering documentation

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
docs/DAY31_RECEPTION_WALKINS.md
docs/DAY32_BRANCH_SERVICE_CAPACITY.md
docs/DAY33_COUNTER_LIFECYCLE.md
docs/DAY34_MANAGER_DASHBOARD.md
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
- manager branch dashboard aggregation;
- daily queue/customer/service operational reporting;
- live counter/staff/free/busy manager visibility;
- in-app notifications;
- automated tests and GitHub Actions CI.

## Remaining major backend work

1. Manager disruption/rescheduling APIs and repair of older rescheduling logic.
2. Historical QueueEvent timeline/audit data.
3. Account verification, password reset and throttling.
4. External notification channels.
5. PostgreSQL and concurrency hardening.
6. Production secrets/HTTPS/logging/monitoring/backups.
7. Real-time delivery strategy.
8. Historical analytics/performance reporting.
9. Historical data collection and genuine ML wait forecasting.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment       COMPLETE / MERGED
Day 34  Manager Dashboard APIs                    IN PROGRESS
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
python manage.py test dashboard
python manage.py test
```

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

Day 33 made the counter layer operationally trustworthy. Day 34 adds the manager's operational read model without duplicating domain state, giving authorised managers one API view of queue demand, customer flow, services and live counter capacity.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
