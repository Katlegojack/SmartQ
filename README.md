# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework + React + TypeScript queue-intelligence platform. It combines appointments, walk-ins, live queue state, reception operations, counter service, branch management, administration, audit history and forecasting-ready operational data in one backend-owned workflow.

The product principle remains simple:

> Customers should not need to stand physically in a queue just to keep their place in it.

---

## Current product state

Smart Q supports five explicit roles:

| Role | Responsibility |
|---|---|
| Customer | Book/reschedule visits, check in, join a live queue, track position/ETA, cancel, view history/recovery |
| Receptionist | See today's arrivals, search customers, staff check-in, create guest walk-ins, hand work to the live queue |
| Counter Staff | Operate an assigned counter, call next, complete service, mark no-show, open/pause/resume/close |
| Branch Manager | Own-branch live operations, counter staffing, reporting, disruptions and forecasting-data quality |
| System Admin | Global branch/service/capacity/staff/counter configuration and reporting access |

`SYSTEM_ADMIN` is a Smart Q business role and is intentionally separate from Django `is_superuser`.

---

## Authoritative queue lifecycle

Appointments and walk-ins converge on one `Booking + QueueTicket` lifecycle.

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

Registered Customer walk-ins and Reception guest walk-ins enter the same `WAITING -> SERVING -> COMPLETED/NO_SHOW` state machine.

Queue ordering, queue numbering, priority policy, counter ownership and lifecycle validity remain backend-owned. The browser does not recreate these rules.

---

## Architecture

```text
React 18 + TypeScript
React Router + TanStack Query
        |
        | same-origin session + CSRF HTTP
        v
Django REST Framework /api/v1/*
        |
        v
Role / branch / counter / ownership permissions
        |
        v
Serializers + workflow APIs + read models
        |
        v
Domain services + transactions + QueueEvent audit
        |
        +-----------------------------+
        |                             |
        v                             v
Django ORM                    Forecast observations
        |                       (Day 59 foundation)
        v                             |
SQLite3 / future DB                   v
                               later model research
```

Django owns the public entry points and API authority. Vite compiles the React runtime into:

```text
static/react/app.js
static/react/app.css
```

Those build artifacts are generated and are not committed. A frontend build is required after pulling frontend changes.

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

## Technology stack

| Layer | Technology |
|---|---|
| Runtime frontend | React 18 + TypeScript |
| Frontend build | Vite 5 |
| Client routing | React Router 6 |
| Server-state management | TanStack Query 5 |
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication | Django sessions + CSRF |
| Authorization | Smart Q Profile role + object scope |
| Database | SQLite3 in the current development environment |
| Browser origin policy | django-cors-headers + Django CSRF |
| Tests | Django/DRF regression + frontend source/build contracts |
| CI | GitHub Actions, Python 3.12, Node 22, React build, migrations check, focused gates, full suite |

---

# Authentication and session reliability

Core account APIs:

```http
POST /api/v1/accounts/register/
GET  /api/v1/accounts/csrf/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
POST /api/v1/accounts/change-password/
```

Important contracts:

- Public registration creates a Customer account and does not silently log it in.
- Staff sign-in explicitly selects Receptionist, Counter Staff, Branch Manager or System Admin.
- The backend verifies that the selected role matches the account's Smart Q Profile before opening the session.
- Protected workspaces restore `/api/v1/accounts/me/` and verify the expected role.
- Stale CSRF tokens are refreshed and unsafe requests retry once instead of exposing raw Django HTML errors.
- Login/logout/session-transition races are guarded so an older request cannot incorrectly expire a newer session.
- Auth/account entry responses are non-cacheable and compiled frontend assets are versioned.
- Logout destroys the server session first, clears client query state and hard-navigates to the correct Django login page.

When testing multiple roles at the same time, use separate browser profiles/incognito sessions because one browser profile shares one Django session cookie for the Smart Q hostname.

---

# Frontend routes

```text
/                       approved public landing page
/login/                 Customer sign in
/staff-login/           staff role sign in
/register/              Customer registration
/app/                   authenticated role router
/app/customer/          Customer workspace
/app/reception/         Receptionist workspace
/app/counter/           Counter Staff workspace
/app/manager/           Branch Manager workspace
/app/admin/             System Admin workspace
/app/admin/counters/    System Admin counter configuration
/app/history/           Manager/Admin history, disruptions + forecasting data quality
/app/recovery/          Customer disruption recovery
```

The approved public landing page remains Django-rendered. Authenticated operational workspaces use the React runtime.

---

# Customer workflow

Customer APIs include:

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

### Appointment availability

```http
GET /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
```

Smart Q currently defaults to South African local time:

```text
Africa/Johannesburg
```

Same-day times that already passed are removed from generated availability and are rejected again by the backend if submitted manually.

### Check-in

Check-in opens according to the server-owned rule. Successful check-in activates the booking into the live queue and creates/updates its `QueueTicket` to `WAITING`.

### Walk-ins

A registered Customer can join a live queue without a future appointment:

```http
POST /api/v1/bookings/walk-ins/
```

The backend prevents one Customer from having multiple simultaneous `WAITING`/`SERVING` tickets.

---

# Reception workflow

```http
GET  /api/v1/bookings/reception/today/
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
POST /api/v1/bookings/<id>/staff-check-in/
GET  /api/v1/queues/branches/<branch_id>/waiting/
```

The Reception workspace is task-first:

```text
Search
Today's customers
Live queue
Add walk-in
```

Customer check-ins, assisted check-ins and guest walk-ins all converge on the same authoritative queue state used by Counter Staff.

---

# Counter Staff workflow

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

Counter Staff can operate only their assigned counter. The backend selects the next eligible Customer.

When **Call next** succeeds, Smart Q starts the service clock and snapshots the expected service duration for that visit. When **Complete service** is pressed, Smart Q records the real service duration and the signed difference between expected and actual duration.

---

# Branch Manager workflow

Branch Managers are restricted to their assigned branch.

Relevant APIs include:

```http
GET  /api/v1/dashboard/branches/<branch_id>/
GET  /api/v1/counters/branches/<branch_id>/counter-staff/
GET  /api/v1/counters/branches/<branch_id>/
POST /api/v1/counters/<counter_id>/assign/
POST /api/v1/counters/<counter_id>/unassign/
POST /api/v1/counters/<counter_id>/open/
POST /api/v1/counters/<counter_id>/pause/
POST /api/v1/counters/<counter_id>/resume/
POST /api/v1/counters/<counter_id>/close/
```

Manager counter staffing follows the real lifecycle:

```text
Counter CLOSED
      |
      v
Assign Counter Staff
      |
      v
Open Counter
      |
      v
Staff can serve
```

Staff assignment changes are allowed while the counter is closed. This keeps ownership changes away from a customer already being served.

---

# System Admin control plane

System Admin can configure:

```text
Branches
Services
Branch-service capacity mappings
Staff accounts
Physical counters
```

Protected APIs include:

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

GET/POST   /api/v1/counters/admin/
GET/PATCH  /api/v1/counters/admin/<id>/
```

Operational configuration is generally deactivated/closed rather than hard-deleted so historical relationships remain usable.

---

# Priority policy

Queue lane assignment remains backend-controlled.

Current policy:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

Customers and Reception do not manually choose General/Priority.

The future forecasting export does not expose the raw personal/protected attributes above. It may retain the resulting operational queue lane because General/Priority lanes use different counter pools, but the underlying attributes are not exported as model features.

---

# Day 58 live ETA and service timing

The old static rule:

```text
people ahead x average service time
```

is no longer the whole live ETA calculation.

The current deterministic ETA considers:

- Customers already being served in the same branch/queue lane;
- remaining target time on those active services;
- Customers waiting ahead;
- matching OPEN counters;
- idle counters that can accept work immediately;
- parallel counter availability.

Waiting work is projected onto whichever matching counter becomes available first.

### User-facing unit

Smart Q displays time in **minutes**:

```text
Estimated wait: 15 min
Service elapsed: 7 min
Target remaining: 13 min
```

It does not show an `M:SS` countdown.

### Internal precision

Smart Q retains exact timestamps and integer seconds internally for measurement and later modelling:

```text
service_started_at
service_completed_at
service_target_seconds
actual_service_seconds
service_variance_seconds
```

For a 20-minute target completed in 15 minutes:

```text
target internally     1200 s
actual internally      900 s
variance internally   -300 s
minutes saved            5.0
```

The counter becomes free immediately when service is completed; the unused five minutes do not keep another Customer waiting. The residual remains historical evidence.

---

# Day 59 forecasting observation foundation

Day 59 begins the forecasting work by collecting labelled operational observations. **No machine-learning model is active yet.**

New model:

```text
QueueForecastObservation
```

At `CHECKED_IN`, it snapshots information known at queue entry:

```text
branch
service
queue lane
booking source
check-in time
people ahead
open matching counters
customers already serving
baseline deterministic ETA
```

At `CALLED`, it records:

```text
actual wait
wait prediction residual
service target
```

At `COMPLETED`, it records:

```text
actual service duration
service-duration residual
```

The observation pipeline subscribes to append-only `QueueEvent` creation. That means Customer, Reception and Counter flows share one data-collection boundary instead of maintaining separate analytics code.

### Forecasting quality endpoint

Branch Manager (own branch) and System Admin can inspect collection quality:

```http
GET /api/v1/queues/branches/<branch_id>/reports/forecasting/
```

It reports:

```text
observation count
wait labels
service labels
baseline wait MAE
baseline wait bias
service target MAE
service target bias
model_status = data_collection
machine_learning_enabled = false
```

The `/app/history/` workspace surfaces the main collection-quality metrics without exposing raw customer data.

### Forecasting dataset export

```bash
python manage.py export_forecasting_dataset \
  --branch-id <id> \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --output data/smartq_forecasting.csv
```

Approved export columns:

```text
observation_id
ticket_id
branch_id
service_id
queue_type
booking_source
checked_in_at
checked_in_weekday
checked_in_hour
people_ahead
open_counter_count
serving_count
baseline_estimated_wait_seconds
actual_wait_seconds
wait_variance_seconds
service_target_seconds
actual_service_seconds
service_variance_seconds
```

The export intentionally excludes names, usernames, email addresses, phone numbers, date of birth, gender, disability status and pregnancy state.

This dataset is the foundation for later statistical/ML evaluation; it is not a claim that Smart Q already uses AI for live ETA.

---

# Historical reporting and audit

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
GET /api/v1/queues/branches/<branch_id>/events/
```

Historical reporting reads append-only `QueueEvent` facts rather than treating current mutable queue state as history.

Operational reports include lifecycle counts, actual wait/service timing, completion/no-show rates, service breakdown and daily activity.

---

# Disruptions and recovery

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

Replacement choices are revalidated on write so stale/full slots cannot be accepted just because they were previously displayed.

---

# Live state strategy

Smart Q currently uses normal HTTP polling plus immediate query invalidation after local writes.

Relevant cadence:

```text
Customer active queue authoritative state   2 seconds
Customer bookings                           5 seconds
Counter current customer                    2 seconds
Counter assigned-counter/waiting state      5 seconds
Reception workload/live queue               5 seconds
Manager dashboard/staffing                  5 seconds
Same-day appointment availability          15 seconds
```

A Customer/Counter service clock may use a local internal timer so a minute boundary changes promptly, but visible time remains minute-based.

This is **not a WebSocket implementation**. WebSockets or Server-Sent Events remain future options if the operational scale justifies them.

---

# Queue numbering

Queue numbers use a database-backed allocator scoped by:

```text
branch + booking date + queue type
```

The sequence row is transactionally locked during allocation, preventing concurrent callers from receiving the same next queue number.

---

# Responsive/accessibility baseline

The React design system includes:

```text
keyboard-visible focus outlines
skip link + semantic main target
prefers-reduced-motion handling
responsive layouts
horizontal preservation for dense operational tables
status/error live feedback
```

This is an engineering baseline, not a formal WCAG certification claim.

---

# Build and run

## Codespaces / Linux / macOS

```bash
git checkout main
git pull origin main
pip install -r requirements.txt

cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Use the forwarded **Django port 8000** as the product entry point.

The React build is required because `static/react/` is generated and gitignored.

Optional demo data:

```bash
python manage.py bootstrap_demo
```

## Windows PowerShell

```powershell
git checkout main
git pull origin main
pip install -r requirements.txt
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..
python manage.py migrate
python manage.py runserver
```

---

# Verification

Local high-level verification:

```bash
cd frontend
npm run build
cd ..

python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day58_realtime_service_timing
python manage.py test smartq.test_day59_forecasting_observations
python manage.py test
```

GitHub Actions additionally runs the major historical Smart Q regression gates before the complete Django suite.

---

# Engineering documentation

Permanent milestone engineering documents live under `docs/`.

Key recent documents include:

```text
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
docs/DAY58_REALTIME_SERVICE_TIMING.md
docs/DAY59_FORECASTING_OBSERVATIONS.md
```

Day 52 is protected by `smartq/test_day52_live_admin_controls.py`; Days 54–57 are protected by their focused regression gates and the repository history. A consolidated Day 52–58 engineering document also exists outside the runtime repo as project documentation.

---

# Milestone roadmap

```text
Day 28-40  Backend/API/security foundation                  COMPLETE
Day 41-50  Planned frontend roadmap                        COMPLETE
Day 51     Reception workflow + Customer handoff           COMPLETE
Day 52     Live Customer state + Admin controls            COMPLETE
Day 53     React + TypeScript runtime reengineering        COMPLETE
Day 54     Approved public UI + workspace cleanup          COMPLETE
Day 55     Auth/CSRF/logout reliability                    COMPLETE
Day 56     CSRF/session stability hardening                COMPLETE
Day 57     Counter creation + Manager staffing lifecycle   COMPLETE
Day 58     Live ETA + service timing observations          COMPLETE
Day 59     Forecasting observation/data foundation         IN DEVELOPMENT
```

Day 59 is complete only when its focused regression suite, all historical gates, full suite, PR verification, merge and post-merge `main` CI have succeeded.

---

# Forecasting way forward

The intended modelling sequence is deliberately evidence-driven:

```text
1. collect real labelled observations
2. inspect missingness and distributions
3. measure deterministic baseline MAE/bias
4. split data by time into train/validation/test periods
5. build simple statistical / classical ML baselines
6. compare them against the deterministic system
7. test a neural network only if data volume/non-linearity justify it
8. deploy only if the model improves real accuracy and remains operationally safe
```

Smart Q should become AI-assisted because the data demonstrates value, not because an AI label looks good in a presentation.

---

## Final project statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
