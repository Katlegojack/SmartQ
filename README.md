# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework + React + TypeScript queue-intelligence platform. It combines appointments, walk-ins, live queue state, reception operations, counter service, branch management, administration, audit history and forecasting-ready operational data in one backend-owned workflow.

> Customers should not need to stand physically in a queue just to keep their place in it.

---

## Current product state

Smart Q supports five explicit roles:

| Role | Responsibility |
|---|---|
| Customer | Book/reschedule visits, check in, join a live queue, track position/ETA, cancel, view history/recovery |
| Receptionist | See today's arrivals, search customers, staff check-in, create guest walk-ins, watch live queues/counters and hand work to the queue |
| Counter Staff | Operate an assigned counter, call next, complete service, mark no-show, open/pause/resume/close |
| Branch Manager | Own-branch live operations, counter staffing, reporting, disruptions and forecasting-data quality |
| System Admin | Global branch/service/capacity/staff/counter configuration and reporting access |

`SYSTEM_ADMIN` is a Smart Q business role and is intentionally separate from Django `is_superuser`.

---

## Authoritative queue lifecycle

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

Registered Customer walk-ins and Reception guest walk-ins enter the same `WAITING -> SERVING -> COMPLETED/NO_SHOW` state machine. Queue ordering, numbering, priority policy, counter ownership and lifecycle validity remain backend-owned.

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
        +------------------------------+
        |                              |
        v                              v
Django ORM                     Forecast observations
        |                       (Day 59+ foundation)
        v                              |
SQLite3 / future DB                    v
                               statistical / ML research
```

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
| Tests | Django/DRF regression + frontend source/build contracts |
| CI | GitHub Actions, Python 3.12, Node 22, React build, migrations check, focused gates, full suite |

---

# Authentication and role entry

```http
POST /api/v1/accounts/register/
GET  /api/v1/accounts/csrf/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
POST /api/v1/accounts/change-password/
```

Public registration creates a Customer account without silently logging it in. Staff sign-in explicitly selects Receptionist, Counter Staff, Branch Manager or System Admin, and the backend verifies that the selected role matches the account profile.

When testing multiple roles simultaneously, use separate browser profiles/incognito sessions because one browser profile shares one Django session cookie for the Smart Q hostname.

---

# Main frontend routes

```text
/                       public landing page
/login/                 Customer sign in
/staff-login/           staff role sign in
/register/              Customer registration
/app/customer/          Customer workspace
/app/reception/         Receptionist workspace
/app/counter/           Counter Staff workspace
/app/manager/           Branch Manager workspace
/app/admin/             System Admin workspace
/app/admin/counters/    System Admin counter configuration
/app/history/           Manager/Admin history + forecasting quality
/app/recovery/          Customer disruption recovery
```

---

# Core workflows

Customer APIs include booking, own-booking retrieval, walk-ins, check-in, cancellation, rescheduling, current queue state and timeline APIs.

Reception APIs include today's workload, customer search, assisted check-in, guest walk-in creation, branch waiting-queue visibility and live counter visibility.

Counter Staff APIs include own-counter lookup, open/pause/resume/close, current customer, call-next, complete and no-show actions.

Branch Manager is restricted to the assigned branch and can inspect the branch dashboard, counters, staff assignment and forecasting-data quality. System Admin owns global branch/service/staff/counter configuration.

---

# Priority policy

Queue lane assignment remains backend-controlled:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

Customers and Reception do not manually choose General/Priority. Forecasting exports do not expose the underlying protected attributes.

---

# Day 58 live ETA and service timing

The old static `people ahead x average service time` rule is no longer the whole live ETA calculation. The deterministic ETA accounts for customers already being served, remaining target time, waiting customers ahead, matching open counters, idle counters and parallel counter availability.

Smart Q displays time in **minutes** to users while retaining exact internal timestamps and integer seconds:

```text
service_started_at
service_completed_at
service_target_seconds
actual_service_seconds
service_variance_seconds
```

A counter becomes free immediately when service completes. Saved/lost minutes become historical evidence rather than reserved counter time.

---

# Day 59 forecasting observation foundation

Day 59 introduced `QueueForecastObservation` and event-driven labelled operational data collection.

At `CHECKED_IN`, Smart Q snapshots information known before the outcome: branch, service, queue lane, booking source, check-in time, people ahead, open eligible counters, serving count and baseline deterministic ETA.

At `CALLED`, it records actual wait, wait residual and service target. At `COMPLETED`, it records actual service duration and service residual.

Forecasting quality:

```http
GET /api/v1/queues/branches/<branch_id>/reports/forecasting/
```

The current forecasting status remains explicit:

```text
model_status = data_collection
machine_learning_enabled = false
```

Dataset export:

```bash
python manage.py export_forecasting_dataset \
  --branch-id <id> \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --output data/smartq_forecasting.csv
```

The export intentionally excludes names, usernames, email addresses, phone numbers, date of birth, gender, disability status and pregnancy state.

---

# Day 61 busy-day forecasting simulation - LIVE RUN COMPLETE

Day 61 moved forecasting work from collection infrastructure to a controlled **real-time synthetic operating day** that exercised the actual Smart Q queue lifecycle.

```text
Branch: ML01 - Smart Q Training Branch
Customers: 80
General: 72
Priority: 8
Counters: 3 (2 General + 1 Priority)
Services: Collections, ID Applications, Passport Applications
Appointments: 08:00 through 15:45
```

| Service | Baseline target |
|---|---:|
| Collections | 10 min |
| ID Applications | 15 min |
| Passport Applications | 20 min |

Actual synthetic service duration intentionally varies below, above and exactly on target. The variation is deterministic for a scenario date so the workload stays reproducible.

Verified live result — 7 September 2026:

```text
Busy-day simulation complete: all 80 customers processed.
```

Day 61 validated that the live runner can process the complete workload through real queue operations while preserving the distinction between baseline prediction and measured outcome.

---

# Day 62 resilient live training - READY FOR LIVE RUN

Day 62 is the controlled follow-up to Day 61. It keeps the same ML01 training environment and forecasting event path while adding realistic operational disturbances.

**Target live date:** 9 September 2026  
**Operating window:** 09:00–18:00

```text
110 seeded appointments
99 General
11 Priority
10 deterministic-random seeded no-shows
100 seeded attendees expected

PLUS live extras:
- normal registered Customer joins
- Reception guest walk-ins
```

The extras are outside the seeded 110 and enter the same authoritative queue as everybody else.

## Day 62 routing changes

Counter 1 and Counter 2 remain General. Counter 3 remains Priority-first, but it is now work-conserving:

```text
Counter 3 free
    |
Priority waiting? ---- yes ---> serve Priority
    |
    no
    |
General waiting? ----- yes ---> help General
```

A General customer already being served is never interrupted when Priority demand later arrives. Priority gets first claim only when Counter 3 next becomes free.

The deterministic ETA calculation follows the same policy: General customers can benefit from an available Priority counter, while outstanding Priority work remains first in line for that shared counter.

## Day 62 no-show rule

Ten seeded bookings are selected through deterministic date/version-seeded randomness. They never enter `WAITING`. Ten minutes after their appointment time they become `NO_SHOW`, a `QueueEvent.NO_SHOW` is recorded, and the queue continues without consuming a counter.

## Reception live visibility

Reception keeps its task-first workflow and now polls live queue/counter state every two seconds. It can see General waiting, Priority waiting, customers currently serving, each counter's current state/customer, the full waiting queue, today's arrivals and the normal add-walk-in flow.

## Customer live queue experience

A normal Customer account can join ML01 during the training day as an extra. The Customer screen shows:

```text
queue number
people ahead
estimated wait
waiting so far
status
real counter number when called
```

The server refreshes authoritative queue/ETA state every two seconds. `Waiting so far` advances from the real check-in timestamp; ETA is recalculated from live queue/counter state rather than treated as a blind fixed countdown.

## Day 62 commands

Optional local-only observer passwords, set before seeding:

```bash
export SMARTQ_TRAINING_MANAGER_PASSWORD='choose-a-local-temporary-password'
export SMARTQ_TRAINING_RECEPTION_PASSWORD='choose-a-local-temporary-password'
```

Never commit those values.

Seed:

```bash
python manage.py seed_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10 \
  --reset
```

Mandatory preflight:

```bash
python manage.py verify_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10
```

Expected readiness line:

```text
READY: Day 62 is structurally ready for the 09:00 resilient live training run.
```

Terminal 1:

```bash
python manage.py runserver 0.0.0.0:8000
```

Terminal 2, before 09:00:

```bash
python manage.py run_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10
```

After the live day:

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-09 \
  --end-date 2026-09-09 \
  --output smartq_training_2026-09-09.csv
```

**Day 62 is not complete merely because the implementation is merged.** It closes only after the 9 September live run and resulting data are verified. No ML model is active yet.

---

# Build and run

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

Use forwarded Django port **8000** as the product entry point.

---

# Verification

```bash
cd frontend
npm run build
cd ..
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day58_realtime_service_timing
python manage.py test smartq.test_day59_forecasting_observations
python manage.py test smartq.test_day60_workspace_shell_cleanup
python manage.py test smartq.test_day61_busy_day_simulation
python manage.py test smartq.test_day61_busy_day_readiness
python manage.py test smartq.test_day62_resilient_live_training
python manage.py test
```

---

# Engineering documentation

Permanent milestone documents live under `docs/`.

Recent documents include:

```text
docs/DAY51_RECEPTIONIST_WORKFLOW.md
docs/DAY53_REACT_FRONTEND_REENGINEERING.md
docs/DAY58_REALTIME_SERVICE_TIMING.md
docs/DAY59_FORECASTING_OBSERVATIONS.md
docs/DAY61_BUSY_DAY_ML_SIMULATION.md
docs/DAY61_TOMORROW_RUNBOOK.md
docs/DAY61_FINAL_DOCUMENTATION.md
docs/DAY62_RESILIENT_LIVE_TRAINING.md
```

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
Day 59     Forecasting observation/data foundation         COMPLETE
Day 60     Workspace shell engineering-text cleanup        COMPLETE
Day 61     80-customer real-time busy-day simulation       COMPLETE
Day 62     110-customer resilient live training run        READY FOR LIVE RUN
```

---

# Forecasting way forward

```text
1. export and inspect labelled observations
2. audit missingness and feature distributions
3. measure deterministic baseline MAE/bias
4. split data chronologically into train/validation/test periods
5. build simple statistical / classical ML baselines
6. compare every model against the deterministic Smart Q baseline
7. test a neural network only if data volume/non-linearity justify it
8. deploy only if a model improves real accuracy and remains operationally safe
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
