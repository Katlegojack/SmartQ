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
| Receptionist | See today's arrivals, search customers, staff check-in, create guest walk-ins, hand work to the live queue |
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

Reception APIs include today's workload, customer search, assisted check-in, guest walk-in creation and branch waiting-queue visibility.

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

At `CHECKED_IN`, Smart Q snapshots information known before the outcome: branch, service, queue lane, booking source, check-in time, people ahead, open matching counters, serving count and baseline deterministic ETA.

At `CALLED`, it records actual wait, wait residual and service target. At `COMPLETED`, it records actual service duration and service residual.

Forecasting quality:

```http
GET /api/v1/queues/branches/<branch_id>/reports/forecasting/
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

## Scenario

```text
Branch: ML01 - Smart Q Training Branch
Customers: 80
General: 72
Priority: 8
Counters: 3
  Counter 1 - General
  Counter 2 - General
  Counter 3 - Priority
Services: Collections, ID Applications, Passport Applications
Appointments: 08:00 through 15:45
```

| Service | Baseline target |
|---|---:|
| Collections | 10 min |
| ID Applications | 15 min |
| Passport Applications | 20 min |

Actual synthetic service duration intentionally varies below, above and exactly on target. The variation is deterministic for a scenario date so the workload stays reproducible.

## Live operating loop

```text
scheduled booking becomes due
        |
        v
CHECKED_IN / WAITING
        |
        v
free matching counter calls next
        |
        v
SERVING + target snapshot
        |
        v
planned actual duration elapses
        |
        v
COMPLETED
        |
        v
actual duration + signed variance stored
        |
        v
counter immediately becomes available
```

If a service is targeted at 15 minutes but actually takes 8 minutes, the counter is free at minute 8. Smart Q does not wait for the unused seven minutes to expire.

## Commands used

Seed/rebuild the scenario:

```bash
python manage.py seed_busy_day \
  --date 2026-09-07 \
  --customers 80 \
  --reset
```

Mandatory preflight:

```bash
python manage.py verify_busy_day \
  --date 2026-09-07 \
  --customers 80
```

Django terminal:

```bash
python manage.py runserver 0.0.0.0:8000
```

Simulator terminal:

```bash
python manage.py run_busy_day --date 2026-09-07
```

## Verified live result - 7 September 2026

The full real-time workload completed successfully:

```text
Busy-day simulation complete: all 80 customers processed.
```

The terminal confirmed early, exact and late service outcomes, including:

```text
A066 - actual 22.0 min, target 15 min, variance +7.0 min
A068 - actual  8.0 min, target 10 min, variance -2.0 min
A067 - actual 27.0 min, target 20 min, variance +7.0 min
A069 - actual 14.0 min, target 15 min, variance -1.0 min
A070 - actual 17.0 min, target 20 min, variance -3.0 min
A071 - actual 11.0 min, target 10 min, variance +1.0 min
A072 - actual 15.0 min, target 15 min, variance +0.0 min
```

This validates that the runner can process the complete workload through real queue operations while preserving the distinction between **baseline prediction** and **measured outcome**.

Export the completed day:

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-07 \
  --end-date 2026-09-07 \
  --output smartq_training_2026-09-07.csv
```

**Important:** Day 61 does not mean a machine-learning model is active in production. It creates and validates labelled operational data for later statistical/ML evaluation.

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
```

Day 61 was closed after the live simulator successfully processed all 80 synthetic customers on 7 September 2026.

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
