# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Days 28-34 are integrated into `main`. Day 35 disruption and rescheduling repair is implemented on `feature/day35-disruption-rescheduling` and is under final regression/documentation verification.

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
Authentication + Role/Branch/Counter/Ownership Permissions
        ↓
Serializers / Read Models / Workflow APIs
        ↓
Business Logic / Aggregation / Transaction Services
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
| Customer | Own account, bookings, live queue and own disruption reschedule options |
| Receptionist | Branch queue reads, booking search, staff check-in, guest walk-ins |
| Counter Staff | Branch queue reads + mutations on their assigned counter |
| Branch Manager | Own-branch counter assignment, disruption control, operational override and manager dashboard |
| System Admin | Global operational, disruption and dashboard access |

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

Day 35 reuses this same availability engine for disruption replacement slots so normal booking and rescheduling cannot disagree about capacity.

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

A Counter has explicit staff ownership.

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

### Manager dashboard API

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Access rules:

- Branch Manager: own branch only.
- System Admin: any active branch.
- Counter Staff, Receptionist and Customer: denied.

The dashboard returns branch information, customer activity, General/Priority lifecycle counts, booking sources, check-in totals, service distribution and live counter/staff/free/busy state.

Date-scoped queue, booking and service metrics use the requested report date. Counter state is explicitly labelled `live_current_state` because historical counter transitions are not yet persisted.

Smart Q deliberately does **not** claim a historical average actual waiting time yet. A trustworthy value requires the future queue-event timeline.

## Day 35: Disruption and rescheduling repair

Day 35 replaces unfinished legacy disruption/rescheduling logic with a workflow aligned to current Smart Q invariants.

### Approved disruption flow

```text
Branch Manager pauses branch service
        ↓
Live disruption preview
        ↓
Manager resumes service
        ↓
Final lost-capacity calculation
        ↓
Persist AFFECTED + RESCHEDULE_RISK impacts
        ↓
Generate up to 5 capacity-safe future options
        ↓
Affected customer chooses replacement slot
        ↓
Fresh capacity check under transaction/lock
        ↓
Apply new appointment atomically
        ↓
PENDING booking + SCHEDULED Priority ticket
        ↓
Customer must check in again
```

Rules:

- only `WAITING` customers in the paused branch + service + booking date are affected;
- lost capacity is approximated from pause duration / `Service.average_service_time`;
- risk customers are selected from the back of the affected queue;
- risk is finalized when the pause ends, not continuously persisted during an active outage;
- each at-risk customer receives up to five available future options beginning the next day;
- replacement options reuse the Day 32 `BranchService` capacity engine;
- stored option availability is only a snapshot and is revalidated at confirmation time;
- affected registered customers choose their own replacement slot;
- customer option selection and booking application happen atomically;
- disruption compensation changes the future ticket to Priority and regenerates a `P###` queue number;
- Priority compensation does not bypass check-in;
- after apply, `checked_in_at=None`, booking is `PENDING`, ticket is `SCHEDULED` and has no assigned counter;
- retrying disruption finalization is idempotent.

### Manager disruption APIs

```http
POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET  /api/v1/rescheduling/pauses/<pause_id>/
POST /api/v1/rescheduling/pauses/<pause_id>/resume/
```

Branch Managers are restricted to their assigned branch. System Admin is global.

### Customer disruption-reschedule APIs

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<option_id>/select/
```

The selection endpoint enforces recommendation booking ownership, rechecks capacity, and returns `409 Conflict` when an option became stale or unavailable.

### Day 35 schema repair

`RescheduleOption.option_time` is now a real `TimeField` rather than `TextField` so persisted times round-trip with the type required by the availability engine.

Migration:

```text
rescheduling/migrations/0003_alter_rescheduleoption_option_time.py
```

## Waiting-time estimate

Current waiting time is deterministic, not ML:

```text
Estimated Wait ≈
(People Ahead × Average Service Time) ÷ Active Counters
```

An active counter means:

```text
Counter.status = OPEN
AND Counter.assigned_staff IS NOT NULL
```

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
python manage.py test rescheduling
python manage.py test
```

Verified Day 35 customer-selection implementation run:

```text
33367663442
```

Observed results:

```text
accounts: 6/6 PASS
services: 8/8 PASS
counters: 11/11 PASS
queues: 15/15 PASS
bookings: 22/22 PASS
notifications: 6/6 PASS
dashboard: 7/7 PASS
rescheduling: 12/12 PASS
full suite: 87/87 PASS
```

Full suite:

```text
Ran 87 tests in 91.979s
OK
```

## Permanent engineering documentation

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
docs/DAY31_RECEPTION_WALKINS.md
docs/DAY32_BRANCH_SERVICE_CAPACITY.md
docs/DAY33_COUNTER_LIFECYCLE.md
docs/DAY34_MANAGER_DASHBOARD.md
docs/DAY35_DISRUPTION_RESCHEDULING.md
```

## Current backend capabilities

Smart Q now includes:

- authentication and customer registration;
- role + branch + counter + ownership authorization;
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
- branch-service disruption pause/resume and impact preview;
- idempotent disruption impact finalization;
- capacity-safe disruption replacement recommendations;
- customer-controlled replacement slot selection;
- transactional Priority compensation rescheduling;
- in-app disruption/reschedule notifications for registered customers;
- automated tests and GitHub Actions CI.

## Remaining major backend work

1. Historical QueueEvent timeline/audit data.
2. Account verification, password reset and throttling.
3. External notification channels and guest delivery strategy.
4. PostgreSQL and concurrency hardening.
5. Production secrets/HTTPS/logging/monitoring/backups.
6. Real-time delivery strategy.
7. Historical analytics/performance reporting.
8. Historical data collection and genuine ML wait forecasting.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment       COMPLETE / MERGED
Day 34  Manager Dashboard APIs                    COMPLETE / MERGED
Day 35  Disruption + Rescheduling Repair          IMPLEMENTED / VERIFYING
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
| Authorization | Profile roles + branch/counter/ownership scope |
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
python manage.py test rescheduling
python manage.py test
```

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

Day 33 made counter ownership trustworthy. Day 34 gave managers a truthful operational read model. Day 35 makes service disruption handling deterministic and capacity-safe while preserving customer control: the organisation identifies the disruption, but the affected customer chooses the replacement appointment that works for them.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
