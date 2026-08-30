# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based **Queue Intelligence Platform** being built to make queues more predictable, transparent, fair, and operationally efficient.

The platform is designed around the complete service journey rather than only appointment booking: customers book or eventually check in, receive a queue ticket, track their position and estimated wait, staff operate counters and move the queue, managers respond to disruptions, and the system records the information needed for future analytics and AI-assisted wait-time forecasting.

> **Current development state:** backend operational core in active development. Day 28 work is isolated on `feature/day28-operational-core` and is awaiting local/CI verification before merge into `main`.

---

## Project Vision

Smart Q is not intended to be a basic booking application.

The long-term objective is an intelligent queue-management platform capable of supporting environments such as government service centres, municipalities, banks, hospitals, clinics, universities, embassies, retail service desks and other high-volume organisations.

Smart Q aims to help answer questions such as:

```text
Who is waiting?
Who should be served next?
What is the customer's current position?
How long might the customer wait?
Which counters are available?
What happens when a queue is disrupted?
Which customers may need to be rescheduled?
Has the customer been notified?
How is the branch performing?
```

The core product principle is simple:

> **Every Smart Q screen and backend workflow should reduce uncertainty for customers, staff and managers.**

---

## Current Architecture

Smart Q is currently a **Django modular monolith**.

```text
Frontend / API Client
        ↓
Django URL Routing
        ↓
Django REST Framework API Views
        ↓
Serializers
        ↓
Business Logic / Service Layer
        ↓
Django Models / ORM
        ↓
Database
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
```

The service layer is important: queue movement, priority decisions, waiting-time calculations and rescheduling rules belong in backend business logic rather than in the frontend.

---

## Core Domain Flow

```text
Customer
   ↓
Profile
   ↓
Branch + Service
   ↓
Booking
   ↓
Priority Decision
   ↓
Queue Ticket
   ↓
WAITING
   ↓
Call Next
   ↓
SERVING
   ├── COMPLETED
   └── NO_SHOW
```

Cancellation and rescheduling form controlled alternate paths around this lifecycle.

The future operational flow will add an explicit **arrival/check-in** stage so a scheduled booking is not treated as an active live-queue customer before arrival.

---

## Current Backend Capabilities

### Accounts and priority information

`Profile` stores customer information used by priority rules, including date of birth, gender and disability status.

Current automatic priority rules can classify a booking as priority when:

```text
Age >= 55
OR disability_status = True
OR pregnancy-related priority applies
```

This produces either:

```text
A001 → General
P001 → Priority
```

### Branches

Branches currently store:

- branch code
- name
- address
- city
- opening time
- closing time
- active status

### Services

Services currently store:

- service code
- name
- description
- average service time
- active status

`average_service_time` is used by the current rule-based waiting-time estimator and disruption-capacity calculations.

### Bookings

Booking lifecycle states:

```text
pending
confirmed
completed
cancelled
no_show
```

Implemented customer booking operations include:

- create booking
- list own bookings
- retrieve own booking
- cancel booking
- reschedule booking
- automatically create/update the connected queue ticket

### Queue Tickets

Queue ticket states:

```text
waiting
serving
completed
no_show
cancelled
```

A ticket stores its queue number, queue type, booking relationship, status, assigned counter and creation time.

### Counters

Counters represent branch service points and currently support:

```text
open
closed
paused
```

Counters also have a queue type so General and Priority queues can be operated independently where required.

### Waiting-Time Intelligence

The current estimator is **rule based**, not yet machine learning.

It uses:

```text
people ahead
average service time
active counters
```

Conceptually:

```text
Estimated Wait = (People Ahead × Average Service Time) ÷ Active Counters
```

The backend can calculate:

- people ahead
- queue position
- estimated wait time

This is the baseline that can later be compared with a trained ML predictor.

### Disruption and Rescheduling Foundation

Smart Q already contains backend work for:

- queue pauses
- pause duration
- lost service capacity
- affected customers
- reschedule-risk customers
- persisted disruption impacts
- reschedule recommendations
- reschedule options
- approval/application workflows
- queue-number regeneration after rescheduling
- reschedule confirmation notifications

This is one of the system's key differentiators beyond ordinary appointment booking.

### Notifications

The in-app notification system supports:

- notification records
- notification type
- full message body
- related queue ticket / disruption impact
- read/unread state
- unread count
- mark-as-read workflow

External SMS, WhatsApp, email and push delivery remain future work.

---

## REST API Status

### Public catalogue APIs

```http
GET /api/v1/branches/
GET /api/v1/services/
```

Only active branches/services are returned.

### Customer booking APIs

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Customer booking queries are scoped to `request.user` so one customer cannot read or modify another customer's booking by guessing an ID.

### Notification APIs

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

Notification data is user scoped.

### Queue operation APIs

Existing operational actions:

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

### Day 28 queue read APIs

The Day 28 branch adds the frontend-facing read operations that were missing from the operational workflow:

```http
GET /api/v1/queues/my-current/
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

These allow the frontend to answer:

```text
Customer: What is my live queue state, position and estimated wait?
Staff: Who is waiting at this branch?
Staff: Who is currently being served at this counter?
```

---

## Day 28 — Operational Core Hardening

Day 28 does not redesign Smart Q. It hardens the existing queue engine and exposes the information required by the future real frontend.

Current Day 28 work includes:

- staff-only permission boundary for queue operations using Django `User.is_staff` as an interim solution
- prevention of normal customers operating counters
- safer `call_next_ticket()` behaviour when no waiting customer exists
- restriction of operational queue selection to today's bookings
- prevention of a counter calling another customer while already serving one
- requirement for a counter to be open before it calls a customer
- database transactions around critical queue state changes
- `select_for_update()` groundwork for stronger PostgreSQL concurrency behaviour
- Booking and QueueTicket status synchronisation
- booking past-date validator fix
- branch operating-hour validation for booking/rescheduling
- targeted missing-object exception handling instead of broad `except Exception`
- counter helper bug fixes
- queue statistics naming/logic fixes
- expanded queue serializer data for frontend use
- customer live queue tracker API
- branch waiting-queue API
- staff current-counter API
- initial automated queue API regression tests
- detailed Day 28 engineering documentation

Detailed documentation:

```text
docs/DAY28_OPERATIONAL_CORE.md
```

### Day 28 verification status

The GitHub-connected editing environment can inspect and modify the repository but cannot execute the Django project. Therefore Day 28 is **not considered complete until the branch is verified locally or in CI**.

Run:

```powershell
python manage.py check
python manage.py test queues
python manage.py test bookings
python manage.py test
```

Only after these pass should the Day 28 pull request be marked ready and merged.

---

## Security Direction

Authentication and authorization are different:

```text
Authentication → Who are you?
Authorization  → What are you allowed to do?
```

Customer-owned booking and notification endpoints already scope data to the logged-in user.

Day 28 introduces an interim staff authorization boundary for queue operations using:

```python
user.is_staff
```

This is intentionally temporary. The target role model is:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

The future system must also enforce **branch-scoped authorization**, e.g. a staff member assigned to Branch A must not operate Branch B's counters simply by knowing their IDs.

---

## Known Operational Gaps

Smart Q has a strong backend foundation, but it is not production-ready yet.

The most important remaining gaps are:

1. **Authentication API strategy** for the separate production frontend.
2. **Dedicated role and branch-assignment system** instead of relying on `is_staff`.
3. **Customer check-in** so scheduled appointments join the live queue only after arrival.
4. **Walk-in/reception workflow** for customers without appointments.
5. **Booking availability and capacity engine** rather than accepting arbitrary times within opening hours.
6. **Branch ↔ Service mapping** so not every service is automatically assumed to exist at every branch.
7. **Counter lifecycle APIs** for open/pause/resume/close and staff assignment.
8. **Manager APIs** for live branch metrics and disruption workflows.
9. **Rescheduling/disruption REST APIs** for manager-facing approval and recovery operations.
10. **Historical queue timestamps/events** such as checked-in, called, started and completed times.
11. **Real-time updates**, initially feasible through polling and later WebSockets where justified.
12. **External notifications** such as SMS, WhatsApp, email or push.
13. **Broader automated test coverage**, especially security, concurrency and state transitions.
14. **Production infrastructure** including PostgreSQL, environment-based secrets, monitoring and backups.
15. **AI/ML wait-time prediction**, trained and evaluated on suitable historical/synthetic data rather than claimed before it exists.

---

## Roadmap

### Phase 1 — Core Domain Foundation

```text
Profiles
Branches
Services
Bookings
Queue Tickets
Priority Rules
Queue Numbers
```

**Status:** implemented foundation.

### Phase 2 — Booking API

```text
Create
My Bookings
Detail
Cancel
Reschedule
```

**Status:** implemented; being hardened as required.

### Phase 3 — Operational Queue Engine

```text
Call Next
Serving
Complete
No Show
Counter Assignment
Queue Read APIs
```

**Status:** core implemented; Day 28 hardening awaiting verification.

### Phase 4 — Queue Intelligence

```text
People Ahead
Queue Position
Rule-Based ETA
Counter Capacity
```

**Status:** foundation implemented; live customer API added on Day 28 branch.

### Phase 5 — Disruption and Recovery

```text
Queue Pause
Lost Capacity
Affected Customers
Reschedule Risk
Reschedule Recommendations
Notifications
```

**Status:** backend foundation implemented; manager-facing APIs still required.

### Phase 6 — Operational MVP Completion

```text
Auth API
Roles
Branch Permissions
Check-In
Walk-Ins
Availability
Counter Lifecycle
Manager Dashboard APIs
Historical Events
Automated Tests
```

**Status:** next major backend stage after the current operational-core work.

### Phase 7 — Real-Time and Production Readiness

```text
Polling/WebSockets
External Notifications
PostgreSQL
Secure Environment Configuration
Logging
Monitoring
Backups
Deployment
```

**Status:** planned.

### Phase 8 — Analytics and AI

```text
Historical Queue Dataset
Actual Wait-Time Measurement
Demand Patterns
Peak-Hour Analysis
Model Training
Model Evaluation
AI Wait-Time Prediction
Operational Recommendations
```

**Status:** planned. Current wait prediction remains rule based.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django |
| API | Django REST Framework |
| Language | Python |
| Development Database | SQLite |
| Target Production Database | PostgreSQL |
| Admin / Internal Testing | Django Admin |
| Version Control | Git + GitHub |
| API Tests | Django/DRF test tooling |
| Future Real-Time | Polling initially; WebSockets/Channels where justified |
| Future Notifications | In-app + email/SMS/WhatsApp/push |
| Future AI | ML-based wait-time forecasting after data/evaluation work |

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

Create an admin user when required:

```powershell
python manage.py createsuperuser
```

Run project checks/tests:

```powershell
python manage.py check
python manage.py test
```

---

## Development Workflow

Smart Q uses feature branches and pull requests rather than making experimental changes directly on `main`.

```text
main
 ↓
create feature branch
 ↓
implement one coherent slice
 ↓
comment/document important logic
 ↓
run checks and automated tests
 ↓
push
 ↓
pull request
 ↓
review
 ↓
squash merge
 ↓
pull updated main
```

Example:

```powershell
git checkout main
git pull origin main
git checkout -b feature/example

# develop + test
python manage.py check
python manage.py test

git add .
git commit -m "Implement example feature"
git push -u origin feature/example
```

---

## Documentation Standard

Smart Q development should document not only **what** changed but **why** it changed.

Important feature documentation should include:

- aim and business problem
- architecture and data flow
- code responsibilities
- state transitions
- security decisions
- API contract
- test cases and commands
- expected behaviour
- known limitations
- future improvements

Current Day 28 documentation is available at:

```text
docs/DAY28_OPERATIONAL_CORE.md
```

A final Day 28 PDF will be produced only after the branch passes the required Django verification, so the documentation does not falsely describe unverified work as complete.

---

## Product Maturity

| Stage | Meaning | Current Position |
|---|---|---|
| Pitch prototype | Product journey can be demonstrated, mock frontend data allowed | Strong foundation |
| Pilot operational MVP | Real customer/staff workflow works safely at a branch | In progress |
| Production platform | Secure, monitored, scalable, tested and enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give people greater control over time that is normally lost in uncertain physical queues.

Its backend already combines booking management, automatic priority decisions, queue ticket generation, queue movement, waiting-time estimation, disruption impact analysis, rescheduling workflows, notifications and a growing REST API.

The current engineering priority is to turn these foundations into one safe end-to-end operational workflow before adding production infrastructure and genuine ML forecasting.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
