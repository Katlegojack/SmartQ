# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Days 28-35 are integrated into `main`. Day 36 adds QueueEvent lifecycle history, audit APIs, and the explicitly approved deterministic ETA rule on `feature/day36-queue-event-audit`.

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

If a branch opens at 08:00, customer service starts at 08:00. Smart Q does not add an artificial staff-preparation buffer before branch opening time.

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
| Customer | Own account, bookings, live queue, own disruption options, own booking timeline |
| Receptionist | Branch queue reads, booking search, staff check-in, guest walk-ins |
| Counter Staff | Branch queue reads + mutations on assigned counter |
| Branch Manager | Own-branch counter assignment, disruption control, dashboard and branch audit history |
| System Admin | Global operational, disruption, dashboard and branch audit access |

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
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

### Service APIs

```http
GET /api/v1/services/
GET /api/v1/services/branches/<branch_id>/
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

The backend rejects unoffered services, invalid generated times, past slots and fully-booked slots. Guest walk-ins do not consume scheduled appointment capacity.

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

Queue type is backend-controlled:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The same rules apply to registered customers and guest walk-ins.

## Counter lifecycle

A Counter has explicit staff ownership and lifecycle state.

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

Rules include one staff -> one counter, same-branch assignment, no self-assignment, staffed counter required before opening, PAUSE blocks Call Next, CLOSE blocked while serving, and assignment-aware Counter Staff mutations.

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

## Waiting-time estimate

Smart Q's current ETA is deterministic, not ML.

Approved formula:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Counter count does **not** divide the ETA formula.

The QueueEvent audit trail does **not** replace this ETA calculation.

## Manager dashboard

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Branch Manager sees only the assigned branch. System Admin can inspect any active branch. Customer, Receptionist and Counter Staff are denied.

The dashboard derives operational data from source-of-truth models rather than maintaining a duplicate Dashboard table.

## Disruption and rescheduling

Day 35 provides a repaired capacity-safe disruption workflow:

```text
Branch Manager pauses service
        ↓
Live impact preview
        ↓
Manager resumes service
        ↓
Finalize affected/risk records
        ↓
Generate up to 5 future options
        ↓
Affected customer chooses option
        ↓
Fresh capacity validation under transaction/lock
        ↓
PENDING booking + SCHEDULED Priority ticket
        ↓
Fresh check-in required
```

### Manager disruption APIs

```http
POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET  /api/v1/rescheduling/pauses/<pause_id>/
POST /api/v1/rescheduling/pauses/<pause_id>/resume/
```

### Customer disruption APIs

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<option_id>/select/
```

## Day 36: QueueEvent lifecycle audit

Day 36 adds append-only history for queue, booking and counter transitions.

Tracked facts include:

```text
TICKET_SCHEDULED
CHECKED_IN
CALLED
COMPLETED
NO_SHOW
CANCELLED
RESCHEDULED
DISRUPTION_RESCHEDULED
COUNTER_STAFF_ASSIGNED
COUNTER_STAFF_UNASSIGNED
COUNTER_OPENED
COUNTER_PAUSED
COUNTER_RESUMED
COUNTER_CLOSED
```

Events snapshot operational context such as actor username/role, source, before/after statuses, queue number/type and timestamp. Sensitive priority inputs such as pregnancy/disability must not be written to audit metadata.

### Customer timeline

```http
GET /api/v1/queues/bookings/<booking_id>/timeline/
```

Customer access is ownership-scoped. A customer cannot read another customer's booking history.

### Branch audit

```http
GET /api/v1/queues/branches/<branch_id>/events/
```

Access:

```text
Branch Manager -> own branch only
System Admin   -> any active branch
Receptionist   -> denied
Counter Staff  -> denied
Customer       -> denied
```

Customer responses intentionally omit management actor/metadata fields. Manager/System Admin responses contain the operational audit context needed to trace actions.

## Check-in reminders

Advance online appointments receive hourly in-app reminders during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The same processor cancels unchecked appointments after the appointment time passes. Production scheduler execution remains a Day 37 infrastructure decision.

## Automated verification

GitHub Actions runs migration checks, Django system checks, app-specific regression suites, Day 36 audit tests and the full Django suite.

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
python manage.py test queues.test_day36_events queues.test_day36_audit_api
python manage.py test
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
docs/DAY36_QUEUE_EVENT_AUDIT.md
```

## Current backend capabilities

Smart Q now includes:

- authentication and Customer registration;
- role + branch + counter + ownership authorization;
- branch/service catalogues and BranchService mappings;
- capacity-aware appointment slots;
- booking/rescheduling validation;
- six-hour online/in-person check-in;
- hourly reminder business logic;
- automatic unchecked-appointment cancellation;
- reception search and guest walk-ins;
- backend General/Priority assignment;
- live queues, queue position and deterministic ETA;
- staff-to-counter assignment and lifecycle;
- Call Next / Complete / No Show;
- branch manager operational dashboard;
- disruption pause/resume and rescheduling recovery;
- capacity-safe customer-selected replacement appointments;
- in-app notifications for registered customers;
- append-only queue/booking/counter lifecycle events;
- customer-owned booking timelines;
- manager/System Admin branch audit history;
- automated tests and GitHub Actions CI.

## Remaining major backend work to Day 40

1. **Day 37 - Admin/account/security:** real System Admin CRUD for branches/services/BranchService/staff, password/account security, throttling, account deactivation, reminder scheduler decision.
2. **Day 38 - Production database/concurrency:** PostgreSQL, queue-number concurrency hardening, environment secrets, production settings, CORS/CSRF/cookies, HTTPS/logging/backups.
3. **Day 39 - Reporting/performance:** approved historical operational reports using QueueEvent, query/performance review. Do not change ETA formula without explicit product approval.
4. **Day 40 - Final backend audit:** full role journeys, cross-user/cross-branch attacks, duplicate submissions, stale capacity, migrations-from-empty-db, security and complete regression verification.

Optional future enhancements such as ML forecasting, SMS/WhatsApp, WebSockets and broader external integrations are not required to call Smart Q backend v1 complete.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment       COMPLETE / MERGED
Day 34  Manager Dashboard APIs                    COMPLETE / MERGED
Day 35  Disruption + Rescheduling Repair          COMPLETE / MERGED
Day 36  QueueEvent / Timeline / Audit             IMPLEMENTED / FINAL VERIFY
Day 37  Admin + Account/Security Hardening
Day 38  PostgreSQL + Concurrency + Production Config
Day 39  Historical Reporting + Performance
Day 40  Full Backend Integration + Security Audit
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
| Admin | Django Admin + planned System Admin APIs |
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
python manage.py test queues.test_day36_events queues.test_day36_audit_api
python manage.py test
```

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
