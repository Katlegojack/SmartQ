# Smart Q

**Where Time Meets Priority**

Smart Q is a Django + Django REST Framework **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and operationally efficient.

The product is built around the full service journey: account creation, appointment booking, online/in-person check-in, live queue tracking, reception workflows, counter service, disruptions, rescheduling, notifications, management visibility, and eventually data-driven waiting-time prediction.

> **Current development state:** Days 28–30 are integrated into `main`. Day 31 reception search, guest walk-ins, six-hour online check-in, hourly reminder logic, and unchecked-appointment cancellation are implemented and verified on `feature/day31-reception-walkins`.

---

## Product Principle

Smart Q exists so customers do not need to stand physically in a queue just to hold a place in it.

A **check-in means live-queue activation**. It may happen online or in person.

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

If the appointment time passes and the customer never checked in:

```text
checked_in_at = NULL
appointment time elapsed
        ↓
CANCELLED
```

The customer was never in the live queue, therefore that outcome is **not** a no-show.

If the customer checked in, joined the live queue, was called, and then did not present:

```text
checked_in_at exists
        ↓
WAITING
        ↓
CALLED / SERVING
        ↓
customer absent
        ↓
NO_SHOW
```

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

Queue order, priority, check-in eligibility, expiry, and operational state transitions are backend decisions rather than frontend-controlled values.

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
| Customer | Own account/bookings/queue only |
| Receptionist | Branch queue reads, search, customer check-in, guest walk-ins |
| Counter Staff | Branch queue reads/operations + reception-compatible check-in |
| Branch Manager | Branch operational access |
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

Public registration always creates a normal `CUSTOMER` account. Caller-supplied privilege fields cannot create staff/admin authority.

Django sessions are the current authentication foundation. Final production deployment still requires an explicit CORS/CSRF/secure-cookie or token strategy.

---

## Booking and Check-In APIs

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
POST  /api/v1/bookings/<id>/check-in/
POST  /api/v1/bookings/<id>/staff-check-in/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

### Check-in timing

Check-in opens exactly **6 hours before the appointment datetime**.

Example:

```text
Appointment: 15:00
Check-in opens: 09:00
```

Before the window, the API rejects check-in and returns the opening time.

Once the customer checks in:

```text
Booking.checked_in_at = activation timestamp
QueueTicket.status = WAITING
```

`checked_in_at` does not prove physical branch presence.

---

## Reception APIs

### Search branch customers/bookings

```http
GET /api/v1/bookings/reception/search/?q=<query>
```

Search supports booking ID, username, first/last name, email, guest name, and guest phone number. Results are restricted to the authorised staff member's branch.

### Create guest walk-in

```http
POST /api/v1/bookings/reception/walk-ins/
```

A guest walk-in does **not** require a Smart Q account.

Minimum operational data:

```text
full name
optional phone number
date of birth
gender
disability status
pregnancy for the visit
service
```

The backend creates:

```text
GuestCustomer
Booking.source = WALK_IN
Booking.checked_in_at = now
QueueTicket.status = WAITING
```

Guest walk-ins use the same automatic General/Priority rules as registered customers.

---

## Customer Identity Model

A Booking now belongs to exactly one customer identity:

```text
Registered Django/Smart Q user
            OR
GuestCustomer
```

A database constraint prevents a booking from having both or neither.

Booking source is explicit:

```text
online
walk_in
```

---

## Live Queue APIs

### Customer

```http
GET /api/v1/queues/my-current/
```

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

Call Next selects only checked-in `WAITING` customers.

Live queue order uses check-in time rather than booking creation time.

---

## Priority Policy

Queue type is assigned by the backend.

Current priority conditions:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The customer/receptionist does not manually select General or Priority.

The same policy applies to registered customers and guest walk-ins.

---

## Waiting-Time Estimate

Current waiting-time calculation is deterministic:

```text
Estimated Wait ≈
(People Ahead × Average Service Time) ÷ Active Counters
```

It is **not yet ML**.

Queue position and people-ahead calculations use checked-in live customers only.

---

## Check-In Reminders

For advance online appointments, Smart Q creates an in-app reminder every hour during the six-hour check-in window until the customer checks in.

Example for a 15:00 appointment:

```text
09:00
10:00
11:00
12:00
13:00
14:00
```

Successful check-in stops future reminders.

Same-hour scheduler retries do not duplicate reminders because reminder slots are protected by a database uniqueness constraint.

The reminder engine does not backfill old missed reminders after scheduler downtime.

### Scheduler command

```powershell
python manage.py process_check_in_reminders
```

This command:

- creates the currently due hourly reminder;
- skips customers already checked in;
- cancels appointments whose time passed without check-in.

The business logic is scheduler-agnostic. Production may later use cron, Celery Beat, a cloud scheduler, or another approved mechanism.

---

## Notifications

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

Current delivery is in-app. SMS, WhatsApp, email, and push remain future external channels.

---

## Automated Verification

GitHub Actions currently runs:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test notifications
python manage.py test
```

**Day 31 implementation result: all stages PASS.**

Coverage includes six-hour check-in timing, appointment expiry cancellation, duplicate check-in protection, branch-scoped reception search, guest walk-ins, guest priority assignment, reminder timing/deduplication, reminder stop-after-check-in, and all earlier queue/authentication regressions.

---

## Documentation

Permanent engineering records:

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
docs/DAY30_CHECK_IN.md
docs/DAY31_RECEPTION_WALKINS.md
```

---

## Current Git State

Days 28–30 are already integrated into `main`.

```text
main
  ↑
feature/day31-reception-walkins
```

Day 31 branches directly from the clean merged `main` state.

---

## Current Backend Capabilities

Smart Q now includes:

- customer accounts and session authentication;
- Smart Q roles and branch authorization;
- branches and services;
- booking create/list/detail/cancel/reschedule;
- online and staff check-in;
- six-hour check-in opening window;
- hourly check-in reminder engine;
- automatic cancellation of expired unchecked appointments;
- reception booking/customer search;
- guest walk-ins without accounts;
- shared guest/registered priority rules;
- digital queue numbers;
- scheduled / waiting / serving / completed / no-show / cancelled lifecycle;
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

Next major backend work:

1. Booking availability/capacity engine.
2. Branch ↔ Service availability mapping.
3. Counter lifecycle APIs and staff-to-counter assignment.
4. Manager live dashboard APIs.
5. Manager disruption/rescheduling APIs.
6. Historical QueueEvent timestamps for analytics and ML.
7. External notification channels.
8. Password reset/account verification and throttling.
9. PostgreSQL and queue-number concurrency hardening.
10. Production secrets, HTTPS, logs, monitoring, and backups.
11. Real-time delivery strategy.
12. Genuine trained/evaluated ML waiting-time forecasting.

---

## Roadmap

### Operational MVP foundation

```text
Profiles
Accounts / Login
Roles + Branch Permissions
Branches
Services
Bookings
Queue Tickets
Priority Logic
Online / Staff Check-In
Reception Search
Guest Walk-Ins
Hourly Check-In Reminders
Expiry Cancellation
Queue Operations
Live Queue Reads
Notifications
Automated Tests
CI
```

### Next operational phase

```text
Branch-Service Mapping
Booking Availability / Capacity
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
| Authentication | Django sessions |
| Authorization | Profile roles + object-level branch permissions |
| Language | Python |
| Development DB | SQLite |
| Target production DB | PostgreSQL |
| Internal administration | Django Admin |
| Tests | Django + DRF APITestCase |
| CI | GitHub Actions |
| Background-job foundation | Scheduler-agnostic Django management command |
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

Process check-in reminders manually during development:

```powershell
python manage.py process_check_in_reminders
```

---

## Product Maturity

| Stage | Meaning | Current position |
|---|---|---|
| Pitch prototype | Product journey can be demonstrated | Strong foundation |
| Pilot operational MVP | Real customer/reception/staff workflow at one branch | In progress, significantly advanced |
| Production platform | Secure, monitored, scalable, enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

The customer can now activate a queue position remotely during the approved check-in window, while reception can serve people who arrive without a Smart Q account through a controlled guest walk-in workflow.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
