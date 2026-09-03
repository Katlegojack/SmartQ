# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Backend v1 is complete and merged through Day 40. Frontend Days 41-46 are complete and merged into `main`. Day 46 replaces the generic Counter Staff shell with an assigned-counter serving workspace for lifecycle controls, backend-owned Call Next, current-customer resolution and queue-type-specific waiting visibility. Day 47 Branch Manager Workspace is the next frontend milestone.

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
Django ORM
        ↓
SQLite3
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
| Customer | Own account, appointment booking/rescheduling, bookings, live queue, own disruption options, own booking timeline |
| Receptionist | Branch queue reads, booking search, staff check-in, guest walk-ins |
| Counter Staff | Assigned-counter lifecycle, matching waiting queue visibility, Call Next, Complete and No-show |
| Branch Manager | Own-branch counter assignment, disruption control, dashboard, branch audit history and historical reports |
| System Admin | Global operational/audit/reporting access plus staff, branch, service and BranchService configuration |

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

The login endpoint is explicitly CSRF-protected. CORS and CSRF remain separate controls.

## Frontend foundation

The frontend uses Django templates, CSS and vanilla JavaScript ES modules.

```text
Day 41 -> shared design system + frontend foundation
Day 42 -> authentication + session restoration + role-aware app shell
Day 43 -> live Customer Dashboard
Day 44 -> appointment booking + availability + rescheduling experience
Day 45 -> live Receptionist Workspace
Day 46 -> assigned-counter Counter Staff serving workspace
```

The browser presents backend state and coordinates API requests. It does not recreate Smart Q business rules.

Frontend routes currently include:

```text
/                       public Smart Q entry
/login/                 sign in
/register/              customer registration
/app/                   role-routing entry
/app/customer/          customer dashboard + booking workflow
/app/reception/         receptionist operations workspace
/app/counter/           Counter Staff serving workspace
/app/manager/           branch manager shell
/app/admin/             system admin shell
```

### Day 44 customer booking flow

```text
Customer dashboard
        ↓
Choose Branch
        ↓
Load branch-specific Services
        ↓
Choose Date
        ↓
Load backend-generated availability
        ↓
Choose available Time
        ↓
Review
        ↓
POST /api/v1/bookings/
        ↓
backend revalidates capacity
        ↓
Booking + SCHEDULED QueueTicket
```

The frontend never generates queue numbers, appointment slots, priority state or capacity. Availability is treated as advisory until the final server write revalidates the slot.

Upcoming customer appointments can also be rescheduled through fresh backend availability. Rescheduling returns the queue ticket to `SCHEDULED`, clears check-in state and requires a fresh check-in.

### Day 45 receptionist flow

```text
Receptionist session
        ↓
Assigned branch from /accounts/me/
        ↓
Search branch bookings
        ↓
Staff-assisted check-in when backend allows it
        ↓
WAITING live queue refresh

or

Register guest walk-in
        ↓
Choose branch-offered service
        ↓
Backend derives General/Priority
        ↓
Backend allocates queue number
        ↓
WAITING immediately
```

Reception never selects another branch, queue type, queue number or live-queue state. Those values remain authenticated/backend-owned.

### Day 46 Counter Staff serving flow

```text
Counter Staff session
        ↓
GET /api/v1/counters/my/
        ↓
Assigned counter only
        ↓
CLOSED -> OPEN
        ↓
CALL NEXT
        ↓
Backend selects next matching waiting ticket
        ↓
SERVING
   ├── COMPLETE -> COMPLETED
   └── NO-SHOW  -> NO_SHOW
        ↓
Counter free -> CALL NEXT
```

Counter Staff never choose their own counter, branch, queue type or a specific waiting customer. The waiting table is a read-only preview; the backend Call Next service owns allocation. A paused counter cannot call another customer, but it may finish the customer already in service.

## System Admin control plane

### Staff management

```http
GET  /api/v1/accounts/admin/staff/
POST /api/v1/accounts/admin/staff/
GET  /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/activation/
```

### Branch management

```http
GET  /api/v1/branches/admin/
POST /api/v1/branches/admin/
GET  /api/v1/branches/admin/<id>/
PATCH /api/v1/branches/admin/<id>/
```

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

Core operational configuration uses deactivation rather than destructive hard delete so historical context remains intact.

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

Pregnancy priority input is validated at the backend boundary: a booking cannot claim pregnancy priority unless the authenticated customer profile is female.

## Reception APIs

```http
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
POST /api/v1/bookings/<id>/staff-check-in/
GET  /api/v1/queues/branches/<branch_id>/waiting/
```

Guest walk-ins require no Smart Q account and enter `WAITING` immediately. Reception search, check-in and waiting-queue visibility remain branch-scoped.

## Priority policy

Queue type is backend-controlled:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The same rules apply to registered customers and guest walk-ins.

## Counter lifecycle

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

## Queue-number allocation

Queue numbers are scoped by:

```text
branch + booking date + queue type
```

`QueueNumberSequence` is the database-backed allocation record for each scope.

```text
QueueNumberSequence
├── branch
├── booking_date
├── queue_type
└── last_number
```

The migration seeds sequence state from historical tickets so existing data does not restart from `A001` or `P001`. Verified SQLite3 behavior covers sequential numbering, date reset, separate General/Priority sequences, existing sequence state, and historical seeding.

## Waiting-time estimate

Smart Q's live ETA is deterministic, not ML.

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Counter count does **not** divide the ETA formula.

## Manager dashboard

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Branch Manager sees only the assigned branch. System Admin can inspect any active branch.

## Historical operational reporting

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
GET /api/v1/queues/branches/<branch_id>/reports/operational/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Reporting reads the append-only `QueueEvent` history and returns historical operational facts such as check-ins, calls, completions, no-shows, cancellations, actual wait time, actual service time, completion/no-show rates, and service/daily/queue-type/source breakdowns.

The default period is the most recent 30 days and the maximum accepted range is 366 days. Branch Managers can read only their own branch; System Admin can inspect any active branch.

Historical actual wait is kept separate from the live ETA contract.

## Disruption and rescheduling

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
Fresh capacity validation
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

### Customer timeline

```http
GET /api/v1/queues/bookings/<booking_id>/timeline/
```

### Branch audit

```http
GET /api/v1/queues/branches/<branch_id>/events/
```

Access remains ownership/role/branch scoped.

## Check-in reminders

Advance online appointments receive hourly in-app reminders during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The same processor cancels unchecked appointments after appointment time passes. Deployment can invoke the command hourly using the platform scheduler/cron facility.

## SQLite3 production hardening

Smart Q uses SQLite3 as the project database in development, testing and the current deployment scope.

```text
SMARTQ_ENV=development or production
        ↓
SQLite3
```

Production mode requires:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG=false
ALLOWED_HOSTS
```

Optional persistent database path:

```text
SMARTQ_SQLITE_PATH=/app/data/db.sqlite3
```

### CORS, CSRF and cookies

Supported variables:

```text
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SAMESITE
CSRF_COOKIE_SAMESITE
```

Session and CSRF cookies are `Secure` in production; the session cookie is `HttpOnly`.

### HTTPS / reverse proxy

Supported variables:

```text
SECURE_SSL_REDIRECT
USE_X_FORWARDED_PROTO
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
```

### Logging and persistence

Smart Q emits console logs for deployment collection. SQLite3 must be stored on persistent storage for deployment. Keep regular backup copies, a known retention period and a tested restore procedure for important data.

## Automated verification

GitHub Actions uses one database path:

```text
SQLite3 regression
```

The job verifies dependencies, missing migrations, Django system checks, app-specific regression suites, QueueEvent audit tests, Day 39 reporting tests, Day 40 final audit tests, Day 41-46 frontend milestone tests and the complete Smart Q regression suite.

## Day 40 final backend audit

The final focused audit proves that separate backend features still agree when exercised together.

```text
cross-customer timeline denial
duplicate check-in conflict + single activation event
stale final-slot capacity rejection
Counter Staff Call Next -> Complete integration
counter-assignment isolation
Branch Manager report isolation
System Admin global reporting access
locked ETA contract
```

This audit complements the complete app-specific regression suite rather than replacing it.

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
docs/DAY39_REPORTING_PERFORMANCE.md
docs/DAY40_FINAL_BACKEND_AUDIT.md
docs/DAY41_FRONTEND_FOUNDATION.md
docs/DAY42_AUTH_APP_SHELL.md
docs/DAY43_CUSTOMER_DASHBOARD.md
docs/DAY44_BOOKING_EXPERIENCE.md
docs/DAY45_RECEPTION_WORKSPACE.md
docs/DAY46_COUNTER_STAFF_WORKSPACE.md
```

## Backend v1 capabilities

Smart Q backend v1 includes customer registration/session authentication, CSRF-protected browser login, password rotation, role/branch/counter/ownership authorization, System Admin control APIs, branch/service/capacity configuration, booking/check-in, reception walk-ins, General/Priority queues, deterministic ETA, queue-number sequence allocation, counter lifecycle, manager dashboard, disruption/rescheduling, in-app notifications, QueueEvent history, customer timelines, branch audit history, historical operational reporting, environment-driven security settings, SQLite3 persistence guidance and complete SQLite3 regression verification.

## Frontend capabilities through Day 46

Smart Q now includes a public entry page, customer registration/sign-in, CSRF-protected session restoration, role-aware workspace routing, a live Customer Dashboard, customer-owned appointment/history views, live queue position/ETA presentation, lifecycle history, server-authoritative check-in/cancellation, a full appointment booking/rescheduling workflow, a branch-scoped Receptionist Workspace, and an assigned-counter Counter Staff Workspace for lifecycle control, matching waiting visibility, backend-owned Call Next, Complete and No-show.

## Roadmap

```text
Day 33  Counter Lifecycle + Staff Assignment       COMPLETE / MERGED
Day 34  Manager Dashboard APIs                    COMPLETE / MERGED
Day 35  Disruption + Rescheduling Repair          COMPLETE / MERGED
Day 36  QueueEvent / Timeline / Audit             COMPLETE / MERGED
Day 37  Admin + Account/Security Hardening        COMPLETE / MERGED
Day 38  SQLite3 + Production Hardening            COMPLETE / MERGED
Day 39  Historical Reporting + Performance        COMPLETE / MERGED
Day 40  Full Backend Integration + Security Audit COMPLETE / MERGED
Day 41  Frontend Foundation + Design System       COMPLETE / MERGED
Day 42  Authentication + Role-Aware App Shell     COMPLETE / MERGED
Day 43  Customer Dashboard                        COMPLETE / MERGED
Day 44  Booking + Availability + Rescheduling     COMPLETE / MERGED
Day 45  Receptionist Workspace                    COMPLETE / MERGED
Day 46  Counter Staff Workspace                   COMPLETE / MERGED
Day 47  Branch Manager Workspace                  NEXT
Day 48  System Admin Workspace
```

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Frontend | Django templates + HTML5 + CSS3 + vanilla JavaScript ES modules |
| Authentication | Django sessions + CSRF |
| Authorization | Profile roles + branch/counter/ownership scope |
| Account abuse protection | DRF scoped throttling |
| Database | SQLite3 |
| Browser origin policy | django-cors-headers + Django CSRF |
| Admin/control plane | Protected Smart Q System Admin APIs + Django Admin for development |
| Tests | Django + DRF APITestCase/TransactionTestCase |
| CI | GitHub Actions: SQLite3 regression |

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

Local verification:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
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