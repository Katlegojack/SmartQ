# Smart Q

**Where Time Meets Priority**

Smart Q is a queue-intelligence platform built with Django, Django REST Framework, React and TypeScript. It is designed to make appointments and live queues more predictable for customers while giving service teams clear operational control across Reception, Counters, Branch Management and System Administration.

## Product principle

Smart Q exists so customers do not need to stand physically in a queue just to hold a place in it.

A check-in means **live-queue activation**.

```text
ADVANCE APPOINTMENT
        |
        v
SCHEDULED
        |
        v
CHECK-IN WINDOW OPENS
        |
        v
ONLINE OR STAFF CHECK-IN
        |
        v
WAITING
        |
        v
CALL NEXT
        |
        v
SERVING
   +----+----+
   |         |
COMPLETED  NO_SHOW
```

A registered customer may also join a live queue without an appointment. That creates the same authoritative `Booking + QueueTicket` lifecycle used by Reception and Counter Staff.

---

## Current architecture

Day 53 reengineers the runtime frontend around React + TypeScript without replacing the backend built and hardened through the earlier milestones.

```text
React 18 + TypeScript
React Router + TanStack Query
        |
        | same-origin HTTP + CSRF/session security
        v
Django REST Framework /api/v1/*
        |
        v
Authentication + role/branch/counter/ownership permissions
        |
        v
Serializers + read models + workflow APIs
        |
        v
Domain services + transactions + reporting
        |
        v
Django ORM
        |
        v
SQLite3
```

Django still owns the application URL entry points and backend authority. Vite builds the React runtime into Django static assets:

```text
static/react/app.js
static/react/app.css
```

The browser does **not** recreate server-owned rules such as queue priority, queue numbering, slot generation, capacity, check-in eligibility, staff scope, disruption impact or rescheduling validity.

---

## Technology stack

| Layer | Technology |
|---|---|
| Runtime frontend | React 18 + TypeScript |
| Frontend build | Vite 5 |
| Routing | React Router 6 |
| Server-state management | TanStack Query 5 |
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication | Django sessions + CSRF |
| Authorization | Profile role + branch/counter/ownership scope |
| Database | SQLite3 |
| Browser origin policy | django-cors-headers + Django CSRF |
| Tests | Django / DRF + Day 53 React contract tests |
| CI | GitHub Actions + Node 22 + React build + full Django regression |

Current Django apps:

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

---

## Roles

| Role | Operational responsibility |
|---|---|
| Customer | Appointments, rescheduling, check-in, live queue, history, security and recovery options |
| Receptionist | Today's branch workload, assisted check-in, guest walk-ins and live queue handoff |
| Counter Staff | Assigned-counter lifecycle and serving customers |
| Branch Manager | Own-branch live operations, staffing, history, reporting and disruptions |
| System Admin | Global staff, branch, service and capacity configuration plus reporting access |

`SYSTEM_ADMIN` is a Smart Q business role. It is intentionally separate from Django `is_superuser`.

---

## Frontend routes

The Day 53 React migration preserves the existing product URLs.

```text
/                       public Smart Q entry
/login/                 customer sign in
/staff-login/           staff role sign in
/register/              customer registration
/app/                   authenticated role router
/app/customer/          customer experience
/app/reception/         Receptionist operations
/app/counter/           Counter Staff console
/app/manager/           Branch Manager operations
/app/admin/             System Admin console
/app/history/           Manager/Admin reporting + disruptions
/app/recovery/          customer disruption recovery
```

All frontend routes now boot one React runtime through the thin Django host template.

---

# Authentication and security

Core account APIs:

```http
POST /api/v1/accounts/register/
GET  /api/v1/accounts/csrf/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
POST /api/v1/accounts/change-password/
```

Public registration always creates a Customer account and does not silently log the new account in.

Staff sign-in explicitly selects the intended role. The backend verifies that the selected role matches the authenticated Smart Q profile before starting the session.

Protected React workspaces restore `/api/v1/accounts/me/`, verify the exact expected role and redirect mismatched roles to their own approved workspace.

The shared React shell includes Account Security for every operational role. Password rotation continues to use Django password validation and preserves the current trusted session after success.

Safe secondary routes are allowlisted. Customer can return to `/app/recovery/`; Branch Manager and System Admin can return to `/app/history/`. Arbitrary external `next` destinations are not accepted.

---

# Customer workflow

Customer APIs:

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
POST  /api/v1/bookings/walk-ins/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
GET   /api/v1/queues/my-current/
GET   /api/v1/queues/bookings/<booking_id>/timeline/
```

### Appointments

Availability is generated by the backend and revalidated during the final write.

```http
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

Smart Q uses South African local time (`Africa/Johannesburg`). Same-day appointment times that have already passed are not offered and are rejected if submitted manually.

### Check-in

Check-in opens according to the server-owned check-in rule. After a successful check-in, the React Customer workspace no longer renders a Check in action for that booking. Cancel remains available while the booking is non-final.

Customer booking and active queue state refresh every 5 seconds. Same-day appointment availability refreshes every 15 seconds while being selected.

### Rescheduling

Normal rescheduling uses the backend contract:

```http
PATCH /api/v1/bookings/<id>/reschedule/
```

The booking returns to `PENDING`, its ticket returns to `SCHEDULED`, check-in is cleared and a fresh check-in is required.

### Live queue entry

A registered customer may join one live branch queue without an appointment:

```http
POST /api/v1/bookings/walk-ins/
```

The backend prevents multiple simultaneous `WAITING`/`SERVING` queue tickets.

---

## Priority policy

Queue type remains backend-controlled.

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

Reception and customers do not manually choose General or Priority.

---

# Reception workflow

Reception APIs:

```http
GET  /api/v1/bookings/reception/today/
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
POST /api/v1/bookings/<id>/staff-check-in/
GET  /api/v1/queues/branches/<branch_id>/waiting/
```

The React Reception workspace is deliberately task-first:

```text
Search
Today's customers
Live queue
Add customer
```

Today's workload and the branch waiting queue refresh every 5 seconds. Search remains an exception workflow rather than the default screen.

Guest-walk-in forms reset only after a successful server write. Failed submissions keep their values so Reception can correct the issue instead of retyping the customer.

Customer-to-Reception coordination still uses shared backend state:

```text
Customer books OR joins queue
        |
        v
Booking + QueueTicket
        |
        v
Reception sees branch workload
        |
        v
Check in if required
        |
        v
WAITING
        |
        v
Counter Staff calls next
```

---

# Counter Staff workflow

Counter APIs:

```http
GET  /api/v1/counters/my/
POST /api/v1/counters/<counter_id>/open/
POST /api/v1/counters/<counter_id>/pause/
POST /api/v1/counters/<counter_id>/resume/
POST /api/v1/counters/<counter_id>/close/

GET  /api/v1/queues/counters/<counter_id>/current/
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Counter Staff operate only their assigned counter. The backend chooses the next eligible customer.

The React Counter workspace is a serving console, not an analytics dashboard. Current counter/customer/waiting state refreshes every 5 seconds and backend operation failures are shown directly to the operator.

---

# Branch Manager workflow

Manager APIs:

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/counters/branches/<branch_id>/counter-staff/
GET /api/v1/counters/branches/<branch_id>/
POST /api/v1/counters/<counter_id>/assign/
POST /api/v1/counters/<counter_id>/unassign/
```

Branch Manager sees only the assigned branch.

The React manager view emphasizes operational state:

```text
Customers today
Waiting
Serving
Open counters
Busy counters
Counter / Staff / Status / Current customer / Controls
Service demand
```

The dashboard refreshes every 5 seconds. Historical reporting and disruption control remain on `/app/history/`.

---

# System Admin control plane

Protected administration APIs:

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

The React System Admin console provides real create/update workflows for:

```text
Branches
Services
BranchService capacity mappings
Staff accounts
```

Branch operating hours are editable. The browser performs an early `closing_time > opening_time` check and the backend independently enforces the invariant.

BranchService identity is locked while editing an existing mapping; capacity and active state can be updated safely.

Staff creation includes the full required account/profile fields. Staff edit exposes only fields supported truthfully by the current read/write contract. Branch-scoped roles require an active branch; System Admin uses no branch.

Operational configuration uses deactivation rather than hard delete so historical references remain intact.

---

# Historical reporting and audit

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
GET /api/v1/queues/branches/<branch_id>/events/
```

Historical reporting reads append-only `QueueEvent` facts rather than pretending current live state is historical data.

Reports include check-ins, calls, completions, no-shows, cancellations, actual wait time, service time, completion/no-show rates, service breakdown and daily activity.

---

# Disruptions and customer recovery

Manager/Admin disruption APIs:

```http
GET/POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET      /api/v1/rescheduling/pauses/<pause_id>/
POST     /api/v1/rescheduling/pauses/<pause_id>/resume/
```

Customer recovery APIs:

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<option_id>/select/
```

The backend revalidates stale/full/invalid replacement slots during selection.

---

# Queue number and live ETA contracts

Queue numbers are allocated by database-backed sequence scoped by:

```text
branch + booking date + queue type
```

The approved live estimate remains:

```text
Estimated Wait = People Ahead x Service.average_service_time
```

Counter count does not divide the ETA formula.

---

# Live frontend state strategy

Day 53 uses TanStack Query to manage server state and query invalidation.

Current polling cadence:

```text
Customer bookings / active queue   5 seconds
Reception workload / live queue    5 seconds
Counter / current / waiting         5 seconds
Manager dashboard                   5 seconds
Same-day availability              15 seconds
```

Successful local writes invalidate the related queries immediately, so the initiating browser does not wait for the next polling interval.

WebSockets or Server-Sent Events remain a future option if sub-second cross-client updates become operationally necessary. Day 53 deliberately avoids adding that infrastructure while the existing HTTP contracts satisfy the current scale.

---

# Responsive and accessibility baseline

The React design system includes:

```text
keyboard-visible focus outlines
skip link and semantic main target
prefers-reduced-motion handling
responsive <=760px layouts
horizontal preservation for dense operational tables
status/error live feedback
```

This is an engineering baseline, not a claim of formal WCAG certification.

---

# Build and run

## Codespaces / Linux / macOS

```bash
git pull
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..

python manage.py migrate
python manage.py bootstrap_demo
python manage.py runserver 0.0.0.0:8000
```

The React build is required before Django can serve `static/react/app.js` and `static/react/app.css`.

## Windows PowerShell

```powershell
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python manage.py migrate
python manage.py bootstrap_demo
python manage.py runserver
```

## Frontend development server

Terminal 1:

```bash
python manage.py runserver 0.0.0.0:8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to Django at `127.0.0.1:8000`.

---

# Verification

Local React checks:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

Django checks:

```bash
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day53_react_frontend
python manage.py test
```

GitHub Actions performs the React build before the Django suites and then runs every major historical Smart Q regression gate plus the complete test suite.

Legacy Day 41–52 frontend source remains temporarily in the repository as migration evidence, but the primary runtime routes now target the React host. Removal of obsolete legacy assets should happen only after live validation of the React runtime.

---

# Engineering documentation

Permanent milestone documents live in `docs/`.

Current major documents include:

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
docs/DAY51_RECEPTIONIST_WORKFLOW.md
docs/DAY53_REACT_FRONTEND_REENGINEERING.md
```

Day 52 is protected by `smartq/test_day52_live_admin_controls.py` and covers South African local-time availability, live Customer state and System Admin configuration controls.

---

# Milestone roadmap

```text
Day 28-40 Backend/API/security foundation                 COMPLETE
Day 41-50 Planned frontend roadmap                       COMPLETE
Day 51    Reception workflow + customer handoff          COMPLETE
Day 52    Live customer state + admin controls           COMPLETE
Day 53    React + TypeScript frontend reengineering      CURRENT RELEASE
```

Day 53 is considered complete only after React build/type-check, the focused Day 53 suite, every historical regression gate, the full suite, PR verification, merge and post-merge main verification succeed.

---

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
