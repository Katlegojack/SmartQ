# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and operationally efficient.

The system is being built around the full service journey: account creation, booking, arrival/check-in, live queue tracking, counter service, disruptions, rescheduling, notifications, management visibility, and eventually data-driven waiting-time prediction.

> **Current development state:** Day 30 customer arrival/check-in is implemented and verified on `feature/day30-check-in`. GitHub Actions passes the migration-drift check, Django system check, accounts tests, queue regression tests, booking/check-in tests, and the complete project test suite.

---

## Vision

Smart Q aims to replace uncertain physical waiting with a digital operational system that can answer:

```text
Who has an appointment?
Who has actually arrived?
Who is actively waiting?
Who should be served next?
What is the customer's queue position?
How long might they wait?
Which staff member may operate this branch?
What happens when the queue is disrupted?
How is the branch performing?
```

A core principle is:

> **Every Smart Q workflow should reduce uncertainty for customers, staff, and managers.**

---

## Architecture

Smart Q is currently a Django modular monolith:

```text
Frontend / API Client
        ↓
Django URL Routing
        ↓
Django REST Framework API Views
        ↓
Authentication + Role/Branch Permissions
        ↓
Serializers
        ↓
Business Logic / Service Layer
        ↓
Django Models / ORM
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
```

Business rules remain in backend service functions so the frontend does not decide priority, queue order, check-in eligibility, or service state transitions.

---

## Smart Q Roles

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

| Role | Current authorization |
|---|---|
| Customer | Customer-owned APIs only |
| Receptionist | Read queue + check in customers at assigned branch |
| Counter Staff | Read/operate queue + check in customers at assigned branch |
| Branch Manager | Read/operate queue + check in customers at assigned branch |
| System Admin | Global operational access |

Branch-scoped staff must have a branch. Customers and System Admin do not.

---

## Authentication APIs

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

Public registration always creates a normal `CUSTOMER` account. Caller-supplied staff/admin privilege fields cannot promote the user.

Django sessions are the current authentication foundation. A separately hosted production frontend will still require a deliberate CORS/CSRF/secure-cookie or token strategy.

---

## Day 30: Scheduled Appointment vs Live Queue

Before Day 30, booking creation immediately placed the ticket in `WAITING`. That incorrectly treated an appointment as if the customer had already arrived.

Day 30 introduces the correct lifecycle:

```text
BOOKING CREATED
    ↓
QueueTicket = SCHEDULED
checked_in_at = null
    ↓
CUSTOMER ARRIVES / RECEPTION CHECK-IN
    ↓
checked_in_at = timestamp
QueueTicket = WAITING
    ↓
CALL NEXT
    ↓
SERVING
   ├── COMPLETED
   └── NO_SHOW
```

### QueueTicket states

```text
scheduled
waiting
serving
completed
no_show
cancelled
```

### Check-in rules

A booking can join the live queue only when:

- it is for today;
- it has not already been checked in;
- it is not cancelled, completed, or no-show;
- the customer owns it, or authorised staff belong to the booking's branch.

A successful check-in stores `Booking.checked_in_at` and moves the ticket from `SCHEDULED` to `WAITING`.

Rescheduling clears `checked_in_at` and returns the ticket to `SCHEDULED`, requiring a fresh arrival on the new date.

---

## Booking APIs

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
POST  /api/v1/bookings/<id>/staff-check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Customer self check-in is ownership-scoped. Staff check-in reuses Day 29 role and branch object permissions.

---

## Live Queue APIs

### Customer

```http
GET /api/v1/queues/my-current/
```

Returns the checked-in customer's active ticket, queue position, people ahead, and rule-based estimated wait.

### Staff reads

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

### Counter operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

`Call Next` now selects only customers who have actually checked in.

---

## Queue Ordering and ETA

Live queue order now uses **check-in time**, not ticket creation time.

```text
Customer A books 5 days early, checks in at 09:10
Customer B books today, checks in at 09:00

Live FIFO order:
B before A
```

Queue position and people-ahead calculations use checked-in `WAITING` tickets only.

The current estimator remains rule-based:

```text
Estimated Wait ≈
(People Ahead × Average Service Time) ÷ Active Counters
```

A trained ML model remains future work.

---

## Queue Statistics

Daily queue statistics distinguish:

```text
scheduled
waiting
serving
completed
no_show
cancelled
```

Scheduled appointments are expected customers but are not counted as customers physically waiting at the branch.

---

## Notifications

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

External SMS, WhatsApp, email, and push delivery remain future work.

---

## Automated Verification

GitHub Actions runs:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test
```

**Day 30 final result: all stages PASS.**

Day 30 regression coverage includes:

- successful customer self check-in;
- wrong-date rejection;
- cross-customer ownership protection;
- duplicate check-in conflict;
- final-state rejection;
- reception check-in at assigned branch;
- wrong-branch staff denial;
- reschedule resets check-in;
- booking creation creates `SCHEDULED`, not `WAITING`;
- Call Next ignores un-checked-in appointments;
- Day 28/29 queue and authorization regressions.

---

## Documentation

Permanent engineering records:

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
```

Smart Q daily documentation records the objective, architecture, code, API contract, security decisions, test commands, bugs/fixes, CI results, limitations, and next step.

---

## Current Git Dependency Chain

```text
main
  ↑
PR #16 - Day 28 (verified; GitHub still marks Draft)
  ↑
feature/day28-operational-core
  ↑
PR #17 - Day 29 (verified; Draft)
  ↑
feature/day29-auth-roles
  ↑
PR #18 - Day 30 (verified; Draft)
  ↑
feature/day30-check-in
```

The chained branches preserve verified work while the connected GitHub action cannot change PR #16's Draft flag. After PR #16 is manually marked Ready and merged, later PRs can be retargeted toward `main` in order.

---

## Current Backend Capabilities

Smart Q now includes:

- customer accounts and login/logout;
- Smart Q roles and branch authorization;
- branches and services;
- booking create/list/detail/cancel/reschedule;
- automatic General/Priority classification;
- digital queue numbers;
- explicit scheduled vs checked-in lifecycle;
- customer and reception check-in;
- live waiting queues;
- queue position and rule-based ETA;
- counter Call Next / Complete / No Show;
- Booking ↔ QueueTicket state synchronization;
- disruption/rescheduling backend foundation;
- in-app notifications;
- queue statistics foundation;
- automated DRF regression tests;
- GitHub Actions CI.

---

## Important Remaining Operational Gaps

The next major work includes:

1. Reception booking search / customer lookup.
2. Walk-in customer + ticket workflow.
3. Booking availability/capacity engine.
4. Branch ↔ Service availability mapping.
5. Counter lifecycle APIs and staff-to-counter assignment.
6. Manager live dashboard APIs.
7. Manager disruption/rescheduling APIs.
8. Historical QueueEvent timestamps for analytics and ML.
9. External notifications.
10. Password reset/account verification and throttling.
11. PostgreSQL and queue-number concurrency hardening.
12. Production secrets, HTTPS, logs, monitoring, and backups.
13. Real-time delivery strategy.
14. Genuine trained/evaluated ML waiting-time forecasting.

---

## Roadmap

### Implemented foundation

```text
Profiles
Accounts / Login
Roles + Branch Permissions
Branches
Services
Bookings
Queue Tickets
Priority Logic
Notifications
Disruption / Rescheduling Foundation
DRF APIs
Queue Operations
Live Queue Reads
Customer / Reception Check-In
Automated Tests
CI
```

### Next operational-MVP phase

```text
Reception Search
Walk-Ins
Booking Availability
Branch-Service Mapping
Counter Lifecycle
Staff Assignment
Manager APIs
Historical Queue Events
```

### Production phase

```text
PostgreSQL
Secure configuration
Authentication deployment policy
External notifications
Real-time delivery
Monitoring
Backups
Audit/compliance
```

### Analytics + AI phase

```text
Historical queue-event dataset
Actual wait/service-duration measurement
Demand and peak-hour analysis
Model training
Model evaluation
ML wait prediction
Operational recommendations
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication foundation | Django sessions |
| Authorization | Profile roles + DRF object permissions |
| Language | Python |
| Development DB | SQLite |
| Target production DB | PostgreSQL |
| Internal administration | Django Admin |
| Tests | Django + DRF APITestCase |
| CI | GitHub Actions |
| Future real-time | Polling first; WebSockets where justified |
| Future AI | Trained/evaluated wait-time forecasting |

---

## Local Setup

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
python manage.py test
```

---

## Product Maturity

| Stage | Meaning | Current position |
|---|---|---|
| Pitch prototype | Full product journey can be demonstrated | Strong foundation |
| Pilot operational MVP | Real customer/staff workflow safely works at one branch | In progress |
| Production platform | Secure, monitored, scalable, enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer, clearer operational control.

Day 30 makes the live queue materially more truthful: **an appointment is no longer the same thing as a customer who has actually arrived.**

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
