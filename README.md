# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework Queue Intelligence Platform designed to make queues more predictable, transparent, fair, and operationally efficient.

> **Current development state:** Backend v1 is complete through Day 40 and the frontend roadmap is implemented through Day 50. Day 50 closes the frontend milestone with cross-role integration, responsive/accessibility contract verification, safer session-return behavior, last-System-Admin protection, a JavaScript syntax gate, and a dedicated release-audit regression suite.

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
Django Templates + Vanilla JS ES Modules
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

| Role | Operational scope |
|---|---|
| Customer | Own account, booking/rescheduling, live queue, booking history, security, disruption recovery options |
| Receptionist | Own-branch booking search, assisted check-in, guest walk-ins, branch queue visibility |
| Counter Staff | Assigned-counter serving lifecycle and matching waiting queue visibility |
| Branch Manager | Own-branch dashboard, staffing, historical reporting, audit history and disruption control |
| System Admin | Global staff/branch/service/capacity administration plus global branch reporting/audit inspection |

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

Public registration always creates a Customer account. Browser login is CSRF-protected, password changes reuse Django password validators, and the current trusted session is preserved after successful password rotation.

Day 50 shares one in-flight `/accounts/me/` restoration result across page modules, clears/refetches that cache at explicit identity boundaries, and safely returns users to approved secondary workspaces after sign-in.

## Frontend roadmap and workspaces

```text
Day 41 -> shared design system + frontend foundation
Day 42 -> authentication + session restoration + role-aware app shell
Day 43 -> live Customer Dashboard
Day 44 -> booking + availability + normal rescheduling
Day 45 -> Receptionist Workspace
Day 46 -> Counter Staff Workspace
Day 47 -> Branch Manager Workspace
Day 48 -> System Admin control plane
Day 49 -> historical reporting + audit + disruption/recovery UX
Day 50 -> full frontend integration + responsive/release audit
```

Frontend routes:

```text
/                       public Smart Q entry
/login/                 sign in
/register/              customer registration
/app/                   role-routing entry
/app/customer/          customer dashboard + booking workflow
/app/reception/         receptionist operations workspace
/app/counter/           Counter Staff serving workspace
/app/manager/           Branch Manager operations workspace
/app/admin/             System Admin control plane
/app/history/           Manager/Admin history and reporting workspace
/app/recovery/          Customer disruption recovery workspace
```

The browser presents backend state and coordinates requests. It does not recreate server-owned rules such as queue priority, queue numbering, slot generation, capacity, disruption impact or rescheduling validity.

## Day 50 release integration safeguards

The final frontend audit adds cross-product protections rather than another feature surface.

```text
Shared account restoration
        ↓
Role-aware primary + secondary workspace routing
        ↓
Safe allowlisted login return paths
        ↓
Mid-session-expiry redirect through shared shell
        ↓
Primary role security/password-change parity
        ↓
Last active System Admin protected across deactivation AND role demotion
        ↓
JavaScript syntax gate + Day 50 integration regression suite
```

Approved secondary login-return routes are role constrained. For example, Customer may return to `/app/recovery/`, while Branch Manager or System Admin may return to `/app/history/`. Arbitrary external `next` destinations are not accepted.

When an authenticated session expires after a workspace has already loaded, the shared API client distinguishes the explicit unauthenticated DRF response from an ordinary permission-denied 403 and sends the user back to sign-in with the current workspace path preserved.

The System Admin invariant now applies to every relevant mutation path: Smart Q rejects both deactivation and role demotion when either would remove the last active System Admin. If another active admin remains and an admin legitimately changes their own role, the browser refreshes `/accounts/me/` and immediately routes away from the admin control plane.

## Customer booking and check-in

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
POST  /api/v1/bookings/<id>/staff-check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Availability is generated by the backend and revalidated on the final write. Check-in opens exactly six hours before appointment time. Rescheduling returns the ticket to `SCHEDULED`, clears check-in state and requires a fresh check-in.

## Priority policy

Queue type is backend-controlled:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The same policy applies to registered customers and guest walk-ins. Reception and customers never manually select General/Priority.

## Reception APIs

```http
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
POST /api/v1/bookings/<id>/staff-check-in/
GET  /api/v1/queues/branches/<branch_id>/waiting/
```

Reception remains branch-scoped. Guest walk-ins do not need a Smart Q account and enter `WAITING` immediately after the backend determines queue type and queue number.

## Counter lifecycle

```http
GET  /api/v1/counters/my/
GET  /api/v1/counters/branches/<branch_id>/
GET  /api/v1/counters/branches/<branch_id>/counter-staff/
POST /api/v1/counters/<counter_id>/assign/
POST /api/v1/counters/<counter_id>/unassign/
POST /api/v1/counters/<counter_id>/open/
POST /api/v1/counters/<counter_id>/pause/
POST /api/v1/counters/<counter_id>/resume/
POST /api/v1/counters/<counter_id>/close/
```

Serving APIs:

```http
GET  /api/v1/queues/counters/<counter_id>/current/
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Counter Staff operate only their assigned counter. The waiting table is read-only; the backend chooses the next eligible customer.

## Queue number and live ETA contracts

Queue numbers are allocated by the database-backed sequence scoped by:

```text
branch + booking date + queue type
```

The live wait estimate remains deterministic:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Counter count does **not** divide the ETA formula.

## Branch Manager dashboard

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Branch Manager sees only the assigned branch. System Admin may inspect any active branch. Historical customer metrics and live counter state remain explicitly separate concepts.

## Historical reporting and QueueEvent audit — Day 49

Historical reporting reads append-only `QueueEvent` facts rather than live dashboard state.

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
GET /api/v1/queues/branches/<branch_id>/reports/operational/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
GET /api/v1/queues/branches/<branch_id>/events/
```

Reports include check-ins, calls, completions, no-shows, cancellations, actual wait time, actual service time, completion/no-show rates, service breakdowns, daily activity, queue-type mix and source mix. The default period is 30 days and the maximum accepted range is 366 days.

`QueueEvent` remains the historical source of truth for lifecycle/audit facts including:

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

Customer-owned lifecycle history is available at:

```http
GET /api/v1/queues/bookings/<booking_id>/timeline/
```

## Disruption and customer recovery — Day 49

```text
Branch Manager pauses a service
        ↓
Pause is persisted and can be restored after refresh
        ↓
Backend reports current impact
        ↓
Manager resumes the service
        ↓
Backend finalizes affected/risk records
        ↓
Notifications + future replacement options are generated
        ↓
Affected customer reviews own recommendation
        ↓
Customer chooses a replacement slot
        ↓
Backend revalidates slot/capacity atomically
        ↓
Booking becomes PENDING
Ticket becomes SCHEDULED + Priority
        ↓
Fresh check-in required
```

Manager disruption APIs:

```http
GET  /api/v1/rescheduling/branches/<branch_id>/pauses/
POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET  /api/v1/rescheduling/pauses/<pause_id>/
POST /api/v1/rescheduling/pauses/<pause_id>/resume/
```

The branch-scoped pause `GET` is the Day 49 restoration contract that makes persistent disruption state recoverable after page refresh. Active pauses are returned before ended history.

Customer disruption APIs:

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<option_id>/select/
```

A stale/full/invalid replacement slot is rejected by the server. The browser cannot force an outdated option through.

## Day 49 frontend engineering safeguards

The history workspace uses independent request sequence guards for reports, audit events, branch services and pause history. An older asynchronous response cannot overwrite a newer branch/date selection.

The branch-service serializer exposes both a mapping `id` and the actual `service_id`. Day 49 deliberately sends `service_id` when creating a disruption and has regression coverage protecting that contract.

The audit table displays at most the most recent 100 matching rows after client-side filtering so a large event history does not produce an uncontrolled DOM render.

## System Admin control plane

Protected System Admin APIs include:

```http
GET/POST   /api/v1/accounts/admin/staff/
GET/PATCH  /api/v1/accounts/admin/staff/<id>/
PATCH      /api/v1/accounts/admin/staff/<id>/activation/

GET/POST   /api/v1/branches/admin/
GET/PATCH  /api/v1/branches/admin/<id>/

GET/POST   /api/v1/services/admin/
GET/PATCH  /api/v1/services/admin/<id>/

GET/POST   /api/v1/services/admin/branch-services/
GET/PATCH  /api/v1/services/admin/branch-services/<id>/
```

Core operational configuration uses deactivation rather than destructive hard delete so historical references remain intact.

## Branch-service mapping and capacity

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

Public service APIs:

```http
GET /api/v1/services/
GET /api/v1/services/branches/<branch_id>/
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

The backend rejects unoffered services, invalid generated times, past slots and fully-booked slots.

## Check-in reminders

Advance online appointments receive hourly in-app reminders during the six-hour check-in window until check-in.

```powershell
python manage.py process_check_in_reminders
```

The processor also cancels unchecked appointments after appointment time passes.

## Production and SQLite3 hardening

Smart Q currently uses SQLite3 for development, testing and the current deployment scope.

Production mode requires environment-driven settings such as:

```text
SMARTQ_ENV=production
DJANGO_SECRET_KEY
DJANGO_DEBUG=false
ALLOWED_HOSTS
SMARTQ_SQLITE_PATH=/app/data/db.sqlite3
CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
SECURE_SSL_REDIRECT
```

SQLite3 must live on persistent storage in deployment, with regular backup copies and a tested restore process.

## Responsive and accessibility release contract

Day 50 verified the shared shell and every shipped role/workflow stylesheet retain phone-width responsive rules. Dense management tables remain readable by preserving minimum widths inside horizontal `.table-wrap` overflow instead of compressing columns into unusable layouts.

The shared design system retains:

```text
visible :focus-visible outlines
keyboard skip links
prefers-reduced-motion handling
semantic main targets
status/error live regions in operational workflows
```

This is a verified engineering baseline, not a claim of formal WCAG certification.

## Automated verification

GitHub Actions uses the SQLite3 regression path. The pipeline runs missing-migration checks, Django system checks, app-specific suites, historical reporting/audit tests, frontend milestone suites, JavaScript syntax validation and the complete Smart Q test suite.

Day 49 retains its focused gate:

```powershell
python manage.py test smartq.test_day49_history_recovery
```

Day 50 adds two release gates:

```bash
find static/js -name '*.js' -print0 | xargs -0 -n1 node --check
```

```powershell
python manage.py test smartq.test_day50_frontend_release
```

The Day 50 release suite covers all frontend entry routes, viewport contracts, skip-link/main targets, primary-role shell/security parity, responsive/accessibility CSS contracts, role-route registry, shared identity restoration, safe secondary return routing, mid-session expiry, router-shell stale-copy prevention, Customer recovery navigation placement, System Admin self-role convergence and the last-active-System-Admin backend invariant.

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
docs/DAY47_BRANCH_MANAGER_WORKSPACE.md
docs/DAY48_SYSTEM_ADMIN_WORKSPACE.md
docs/DAY49_HISTORY_REPORTING_RECOVERY.md
docs/DAY50_FRONTEND_RELEASE_AUDIT.md
```

## Frontend capabilities through Day 50

Smart Q now includes a public entry page, customer registration/sign-in, CSRF-protected session restoration, role-aware primary and approved-secondary workspace routing, live customer queue tracking, server-authoritative booking/check-in/cancellation/rescheduling, a branch-scoped Receptionist Workspace, an assigned-counter Counter Staff Workspace, an own-branch Branch Manager Workspace, a global System Admin control plane, a historical reporting/audit workspace, branch disruption controls with refresh-safe restoration, customer-owned disruption recovery, unified account-security access across primary role workspaces, and final integration safeguards for session expiry, role transitions and release regression detection.

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
Day 47  Branch Manager Workspace                  COMPLETE / MERGED
Day 48  System Admin Workspace                    COMPLETE / MERGED
Day 49  Reporting + Disruption/Rescheduling UX    COMPLETE / MERGED
Day 50  Full Frontend Integration + Release Audit COMPLETE
```

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Frontend | Django templates + HTML5 + CSS3 + vanilla JavaScript ES modules |
| Authentication | Django sessions + CSRF |
| Authorization | Profile roles + branch/counter/ownership scope |
| Database | SQLite3 |
| Browser origin policy | django-cors-headers + Django CSRF |
| Tests | Django + DRF APITestCase/TransactionTestCase |
| CI | GitHub Actions: SQLite3 regression + frontend JavaScript syntax/release gates |

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

Optional frontend parse verification when Node.js is installed:

```bash
find static/js -name '*.js' -print0 | xargs -0 -n1 node --check
```

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
