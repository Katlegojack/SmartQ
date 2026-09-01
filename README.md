# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Days 28-37 are integrated into `main`. Day 38 adds PostgreSQL production configuration, concurrency-safe queue-number allocation, PostgreSQL capacity verification, explicit browser CSRF login bootstrap, environment-based secrets/settings, HTTPS/cookie/CORS policy, production logging and deployment/backup requirements on `feature/day38-production-hardening`.

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
HTTPS + CORS/CSRF/session security
        ↓
Django REST Framework APIs
        ↓
Authentication + Role/Branch/Counter/Ownership Permissions
        ↓
Serializers / Read Models / Workflow APIs
        ↓
Business Logic / Aggregation / Transaction Services
        ↓
Django ORM + database constraints/row locks
        ↓
SQLite (development) / PostgreSQL (production)
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
| System Admin | Global operational/audit access plus staff, branch, service and BranchService configuration |

Smart Q's `SYSTEM_ADMIN` business role is intentionally separate from Django `is_superuser`.

## Authentication and account APIs

```http
POST /api/v1/accounts/register/
GET  /api/v1/accounts/csrf/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
POST /api/v1/accounts/change-password/
```

Public registration always creates a normal Customer account. Password changes reuse Django password validators and preserve the current trusted session after successful rotation.

Login and password-security endpoints use scoped DRF throttling.

### Browser session login / CSRF flow

Smart Q uses Django session authentication. A browser client should bootstrap CSRF before login:

```text
GET /api/v1/accounts/csrf/
        ↓
CSRF cookie + token
        ↓
POST /api/v1/accounts/login/
with X-CSRFToken
        ↓
Django session established
```

The login endpoint is explicitly CSRF-protected. CORS and CSRF are separate controls: an origin being allowed by CORS does not bypass CSRF validation.

## System Admin control plane

### Staff management

```http
GET  /api/v1/accounts/admin/staff/
POST /api/v1/accounts/admin/staff/
GET  /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/activation/
```

System Admin can provision Receptionist, Counter Staff, Branch Manager and additional System Admin accounts. Branch-scoped roles require an active branch; System Admin remains branchless. Deactivation uses `User.is_active=False` rather than deleting operational identity/history.

### Branch management

```http
GET  /api/v1/branches/admin/
POST /api/v1/branches/admin/
GET  /api/v1/branches/admin/<id>/
PATCH /api/v1/branches/admin/<id>/
```

The public branch catalogue returns active branches only.

### Service management

```http
GET  /api/v1/services/admin/
POST /api/v1/services/admin/
GET  /api/v1/services/admin/<id>/
PATCH /api/v1/services/admin/<id>/
```

### BranchService/capacity management

```http
GET  /api/v1/services/admin/branch-services/
POST /api/v1/services/admin/branch-services/
GET  /api/v1/services/admin/branch-services/<id>/
PATCH /api/v1/services/admin/branch-services/<id>/
```

Active mappings require an active branch and active service. Core operational configuration uses deactivation rather than destructive hard delete so historical context remains intact.

## Branch-service mapping and capacity

A service must be explicitly offered by a branch through `BranchService`.

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

### Public service APIs

```http
GET /api/v1/services/
GET /api/v1/services/branches/<branch_id>/
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

The backend rejects unoffered services, invalid generated times, past slots and fully-booked slots. Guest walk-ins do not consume scheduled appointment capacity.

For capacity-critical booking writes, Smart Q locks the relevant `BranchService` configuration row before the final reservation count. PostgreSQL concurrency tests verify that two simultaneous requests cannot both consume the same final slot.

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

## Concurrency-safe queue-number allocation

Queue numbers are scoped by:

```text
branch + booking date + queue type
```

Day 38 introduces `QueueNumberSequence` as the database-backed allocation record for each scope.

```text
QueueNumberSequence
├── branch
├── booking_date
├── queue_type
└── last_number
```

Allocation uses a conflict-tolerant first insert, a database uniqueness constraint, `transaction.atomic()` and `select_for_update()` before incrementing the surviving sequence row.

This prevents simultaneous production requests from both receiving the same queue number. The migration also backfills the highest existing historical number so an upgraded installation does not restart from `A001`/`P001`.

Queue numbers are allowed to have gaps. The required invariant is uniqueness/order within a successful operational allocation, not gapless accounting-style numbering.

## Waiting-time estimate

Smart Q's current ETA is deterministic, not ML.

Approved formula:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Counter count does **not** divide the ETA formula.

The QueueEvent audit trail and Day 38 sequence allocator do **not** replace or alter this ETA calculation.

## Manager dashboard

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Branch Manager sees only the assigned branch. System Admin can inspect any active branch. Customer, Receptionist and Counter Staff are denied.

The dashboard derives operational data from source-of-truth models rather than maintaining a duplicate Dashboard table.

## Disruption and rescheduling

Day 35 provides a capacity-safe disruption workflow:

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

## QueueEvent lifecycle audit

Smart Q has append-only history for queue, booking and counter transitions.

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

Customer access is ownership-scoped.

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

## Check-in reminders and scheduler decision

Advance online appointments receive hourly in-app reminders during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The same processor cancels unchecked appointments after appointment time passes.

Production strategy:

```text
Keep the Django management command as the business entry point.
Invoke it hourly with the deployment platform's scheduler/cron facility.
Do not add Celery/Redis before backend v1 is complete.
```

## Day 38 production configuration

Local development remains simple:

```text
SMARTQ_ENV=development
DATABASE_URL absent
→ SQLite
```

Production is fail-fast:

```text
SMARTQ_ENV=production
→ DJANGO_SECRET_KEY required
→ DJANGO_DEBUG must be false
→ ALLOWED_HOSTS required
→ DATABASE_URL required
→ database engine must be PostgreSQL
```

Important deployment variables are documented in `.env.example`. Real `.env` files and secrets are ignored by Git.

### CORS, CSRF and cookies

Production supports explicit:

```text
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SAMESITE
CSRF_COOKIE_SAMESITE
```

Session and CSRF cookies are `Secure` in production; the session cookie is `HttpOnly`.

The final SameSite value must match the actual frontend/API domain topology. `Lax` is the simple default; a genuinely cross-site frontend may require `None` and therefore HTTPS.

### HTTPS / reverse proxy

Production supports:

```text
SECURE_SSL_REDIRECT
USE_X_FORWARDED_PROTO
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
```

Forwarded-protocol trust must only be enabled behind infrastructure that correctly strips/replaces client-provided forwarding headers.

HSTS `includeSubDomains` and preload are deliberate infrastructure commitments, not unconditional defaults.

### Logging

Smart Q emits production-friendly console logs so the deployment platform can handle log collection, retention and search. Application logs should not contain passwords, session cookies, CSRF tokens, pregnancy/disability data or other unnecessary sensitive information.

### Backup requirement

Day 38 defines the production PostgreSQL requirement; it does not falsely claim a cloud backup already exists before a provider is chosen.

A real production deployment must provide:

```text
automated backups at least daily
encrypted backup storage
known retention
point-in-time recovery when supported
restore procedure
restore test before trusting real customer data
```

The first launch target is at least seven days of recoverability, increased when organisational/legal requirements demand it.

## Automated verification

GitHub Actions now uses two complementary CI jobs.

### SQLite regression

Protects local-development behavior and the established Smart Q business regression suites.

### PostgreSQL production

Starts a clean PostgreSQL 17 service and verifies:

```text
missing migrations check
fresh database migration from empty
Django production deployment security checks
queue-number concurrency
last-slot appointment-capacity concurrency
full Smart Q test suite on PostgreSQL
```

PostgreSQL-only concurrency tests use separate threads/database connections because SQLite cannot prove row-level PostgreSQL locking behavior.

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
docs/DAY37_ADMIN_SECURITY.md
docs/DAY38_PRODUCTION_HARDENING.md
```

## Current backend capabilities

Smart Q now includes:

- Customer registration and Django session authentication;
- explicit CSRF bootstrap + CSRF-protected browser login;
- secure password rotation and scoped login/account throttling;
- role + branch + counter + ownership authorization;
- System Admin staff provisioning, role/branch updates and safe deactivation;
- System Admin branch/service/BranchService configuration;
- public active branch/service catalogues;
- capacity-aware appointment slots and PostgreSQL last-slot locking verification;
- booking/rescheduling validation;
- six-hour online/in-person check-in;
- hourly reminder business logic and an approved external scheduler strategy;
- automatic unchecked-appointment cancellation;
- reception search and guest walk-ins;
- backend General/Priority assignment;
- live queues, queue position and deterministic ETA;
- PostgreSQL-safe database-backed queue-number allocation;
- staff-to-counter assignment and lifecycle;
- Call Next / Complete / No Show;
- branch manager operational dashboard;
- disruption pause/resume and rescheduling recovery;
- capacity-safe customer-selected replacement appointments;
- in-app notifications for registered customers;
- append-only queue/booking/counter lifecycle events;
- customer-owned booking timelines;
- manager/System Admin branch audit history;
- environment-driven production settings;
- HTTPS/CORS/CSRF/cookie/logging configuration contract;
- fresh PostgreSQL migration/deployment checks in CI;
- automated abuse-case, regression and production-concurrency tests.

## Remaining major backend work to Day 40

1. **Day 39 - Reporting/performance:** approved historical operational reports using QueueEvent, query/performance review and evidence-based index/query tuning. Do not change the approved ETA formula without explicit product approval.
2. **Day 40 - Final backend audit:** full role journeys, cross-user/cross-branch attacks, duplicate submissions, stale capacity, fresh database/release checks, security review and complete regression verification.

Optional future enhancements such as ML forecasting, SMS/WhatsApp, WebSockets and broader external integrations are not required to call Smart Q backend v1 complete.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment       COMPLETE / MERGED
Day 34  Manager Dashboard APIs                    COMPLETE / MERGED
Day 35  Disruption + Rescheduling Repair          COMPLETE / MERGED
Day 36  QueueEvent / Timeline / Audit             COMPLETE / MERGED
Day 37  Admin + Account/Security Hardening        COMPLETE / MERGED
Day 38  PostgreSQL + Concurrency + Production     IMPLEMENTED / FINAL VERIFY
Day 39  Historical Reporting + Performance
Day 40  Full Backend Integration + Security Audit
```

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication | Django sessions + CSRF |
| Authorization | Profile roles + branch/counter/ownership scope |
| Account abuse protection | DRF scoped throttling |
| Development DB | SQLite |
| Production DB | PostgreSQL via Psycopg 3 |
| Database configuration | `DATABASE_URL` via dj-database-url |
| Browser origin policy | django-cors-headers + Django CSRF |
| Admin/control plane | Protected Smart Q System Admin APIs + Django Admin for development |
| Tests | Django + DRF APITestCase/TransactionTestCase |
| CI | GitHub Actions: SQLite regression + PostgreSQL production |

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

`runserver` is for development only. A real deployment must use a production WSGI/ASGI server behind the chosen hosting/reverse-proxy setup.

Local verification:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

Production configuration reference:

```text
.env.example
docs/DAY38_PRODUCTION_HARDENING.md
```

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer, clearer and increasingly production-ready operational control.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
