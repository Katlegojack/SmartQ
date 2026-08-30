# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair and operationally efficient.

The platform is being built around the complete service journey rather than appointment booking alone: customers create bookings and receive queue tickets, the backend applies priority rules, customers can track their live queue state and estimated wait, staff operate counters, and managers will eventually use disruption, rescheduling and analytics tools to keep queues moving.

> **Current status:** Day 28 operational-core hardening is implemented and verified by GitHub Actions. Django system checks, queue regression tests, booking tests and the full project test suite pass on `feature/day28-operational-core`.

---

## Vision

Smart Q aims to move queue management from passive physical waiting to an intelligent operational system.

The long-term platform should help organisations answer:

```text
Who is waiting?
Who should be served next?
What is the customer's current position?
How long might they wait?
Which counters are available?
What happens when service is disrupted?
Which customers may need rescheduling?
Has the customer been notified?
How is the branch performing?
```

The product is intended to evolve toward use in environments such as government service centres, municipalities, banks, hospitals, clinics, universities, embassies, retail service desks and other high-volume service organisations.

A core product principle is:

> **Every Smart Q workflow should reduce uncertainty for customers, staff and managers.**

---

## Architecture

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

Business rules remain in backend service functions so the frontend does not become responsible for queue state, priority rules or operational decisions.

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

Cancellation and rescheduling are controlled alternate paths around this lifecycle.

A future operational phase will introduce explicit **arrival/check-in** so a scheduled booking does not automatically become part of the live queue before the customer arrives.

---

## Current Backend Capabilities

### Accounts and priority information

`Profile` stores information used by queue-priority rules, including date of birth, gender and disability status.

Current automatic priority logic can classify a booking as Priority when:

```text
Age >= 55
OR disability_status = True
OR pregnancy-related priority applies
```

Queue number examples:

```text
A001 -> General
P001 -> Priority
```

### Branches

Branches store:

- branch code
- name
- address
- city
- opening time
- closing time
- active status

### Services

Services store:

- service code
- name
- description
- average service time
- active status

`average_service_time` supports the current waiting-time estimator and disruption-capacity calculations.

### Bookings

Booking states:

```text
pending
confirmed
completed
cancelled
no_show
```

Implemented customer booking operations:

- create booking
- list own bookings
- retrieve own booking
- cancel booking
- reschedule booking
- automatically create/update the connected queue ticket

Day 28 also fixes past-date validation and validates booking/reschedule times against branch operating hours.

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

Each counter also has a queue type so General and Priority queues can be handled independently where required.

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
Estimated Wait = (People Ahead x Average Service Time) / Active Counters
```

The backend can currently calculate:

- people ahead
- queue position
- estimated wait time

This provides a baseline for later ML-based forecasting.

### Disruption and Rescheduling Foundation

Smart Q already contains backend foundations for:

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

### Notifications

The in-app notification system supports:

- notification records
- notification type
- message body
- related queue ticket/disruption impact
- read/unread state
- unread count
- mark-as-read workflow

External SMS, WhatsApp, email and push delivery remain future work.

---

## REST API Status

### Public catalogue

```http
GET /api/v1/branches/
GET /api/v1/services/
```

### Customer bookings

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

Customer booking queries are scoped to `request.user` so one customer cannot read or modify another customer's booking by guessing an ID.

### Notifications

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

### Queue operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Day 28 protects these operations with an interim staff permission boundary using Django `User.is_staff`.

### Day 28 live queue read APIs

```http
GET /api/v1/queues/my-current/
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

These allow the frontend to answer:

```text
Customer -> What is my live queue state, position and estimated wait?
Staff    -> Who is waiting at this branch?
Staff    -> Who is currently being served at this counter?
```

---

## Day 28 - Operational Core Hardening

Day 28 focused on making the existing queue engine safer, consistent and frontend-ready.

Implemented and verified:

- staff-only permission boundary for counter operations using `User.is_staff` as an interim solution
- normal customers receive `403 Forbidden` when attempting staff queue operations
- `call_next_ticket()` safely handles an empty queue
- closed/paused counters cannot call customers
- Call Next only selects today's bookings
- a busy counter cannot call a second customer
- critical queue transitions use database transactions
- `select_for_update()` added around critical ticket selection/state transitions
- Booking and QueueTicket lifecycle states are synchronized
- completion updates both Booking and QueueTicket to completed
- no-show updates both Booking and QueueTicket to no-show
- cancellation clears any counter assignment
- rescheduling rejects completed/cancelled/no-show bookings
- rescheduling resets the ticket to waiting with a new queue number
- booking past-date validation fixed
- branch operating-hour validation added
- broad `except Exception` handling removed from important booking flows
- counter field/counting bugs fixed
- queue statistics helper naming fixed
- combined waiting queue explicitly places Priority before General
- queue serializer expanded with frontend-useful context
- customer current-queue API added
- branch waiting-queue API added
- counter current-customer API added
- automated regression tests expanded
- GitHub Actions CI workflow added

Detailed engineering documentation:

```text
docs/DAY28_OPERATIONAL_CORE.md
```

### Day 28 verification

The branch was verified automatically using GitHub Actions with:

```powershell
python manage.py check
python manage.py test queues
python manage.py test bookings
python manage.py test
```

All four verification stages passed on the Day 28 branch.

The expanded queue regression tests cover:

- customer authorization rejection
- closed counter protection
- staff Call Next lifecycle
- future booking protection
- prevention of double-serving at one counter
- completion lifecycle synchronization
- no-show lifecycle synchronization
- current-counter read API
- customer queue tracker API
- Priority-before-General combined waiting queue
- invalid queue-type validation

---

## Security Direction

Authentication and authorization are different:

```text
Authentication -> Who are you?
Authorization  -> What are you allowed to do?
```

Customer-owned booking and notification APIs scope data to the logged-in user.

Day 28 adds an interim staff authorization boundary:

```python
user.is_staff
```

This is not the final Smart Q role system. The target design remains:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

The future system must also enforce branch-scoped authorization so staff assigned to Branch A cannot operate Branch B simply by knowing a counter ID.

---

## Known Operational Gaps

Smart Q has a strong backend foundation but is not production-ready yet.

Important remaining work:

1. Authentication API strategy for the separate production frontend.
2. Dedicated role and branch-assignment model instead of relying on `is_staff`.
3. Customer check-in so scheduled appointments enter the live queue after arrival.
4. Walk-in/reception workflow.
5. Booking availability and capacity engine.
6. Branch-to-Service availability mapping.
7. Counter lifecycle APIs for open/pause/resume/close and staff assignment.
8. Manager dashboard APIs and branch-level operational metrics.
9. Manager-facing disruption/rescheduling REST APIs.
10. Historical queue timestamps/events such as check-in, called, service-start and completed times.
11. Real-time updates, initially feasible through polling and later WebSockets where justified.
12. External SMS/WhatsApp/email/push notifications.
13. Broader automated testing, especially concurrency and branch-level permissions.
14. Production PostgreSQL and secure deployment configuration.
15. Genuine AI/ML wait-time forecasting trained and evaluated on suitable data.

---

## Roadmap

### Phase 1 - Core Domain Foundation

Profiles, branches, services, bookings, queue tickets, queue numbers and priority rules.

**Status:** foundation implemented.

### Phase 2 - Booking API

Create, My Bookings, Detail, Cancel and Reschedule.

**Status:** implemented and hardened further on Day 28.

### Phase 3 - Operational Queue Engine

Call Next, Serving, Complete, No Show, counter assignment and queue read APIs.

**Status:** core implemented and Day 28 verification passed.

### Phase 4 - Queue Intelligence

People ahead, queue position, rule-based ETA and counter capacity.

**Status:** foundation implemented and live customer API exposed.

### Phase 5 - Disruption and Recovery

Queue pauses, lost capacity, affected customers, reschedule risk, recommendations and notifications.

**Status:** backend foundation implemented; manager-facing APIs remain.

### Phase 6 - Operational MVP Completion

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
Expanded Automated Tests
```

**Status:** next major backend stage.

### Phase 7 - Real-Time and Production Readiness

Polling/WebSockets, external notifications, PostgreSQL, secure environment configuration, logging, monitoring, backups and deployment.

**Status:** planned.

### Phase 8 - Analytics and AI

Historical queue dataset, actual wait measurement, demand patterns, peak analysis, model training/evaluation, ML wait-time prediction and operational recommendations.

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
| Internal Administration | Django Admin |
| Version Control | Git + GitHub |
| Automated Verification | Django tests + GitHub Actions |
| Future Real-Time | Polling initially; WebSockets/Channels where justified |
| Future Notifications | In-app + email/SMS/WhatsApp/push |
| Future AI | ML wait-time forecasting after data/evaluation work |

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

Project verification:

```powershell
python manage.py check
python manage.py test
```

---

## Development Workflow

Smart Q uses feature branches and pull requests rather than experimental work directly on `main`.

```text
main
 ↓
feature branch
 ↓
implement coherent slice
 ↓
comment + document important logic
 ↓
checks + automated tests
 ↓
push
 ↓
pull request
 ↓
CI verification
 ↓
review
 ↓
squash merge
```

The Day 28 branch also introduces `.github/workflows/django-tests.yml` so future relevant pushes/PRs can be verified automatically.

---

## Documentation Standard

Major development slices should document:

- aim and business problem
- architecture and data flow
- code responsibilities
- state transitions
- security decisions
- API contract
- tests and expected behaviour
- bugs fixed
- known limitations
- future improvements

Day 28 detailed documentation:

```text
docs/DAY28_OPERATIONAL_CORE.md
```

---

## Product Maturity

| Stage | Meaning | Current Position |
|---|---|---|
| Pitch prototype | Complete product story can be demonstrated | Strong foundation |
| Pilot operational MVP | Real customers/staff can safely operate one branch | In progress |
| Production platform | Secure, monitored, scalable, tested and enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give people greater control over time normally lost in uncertain physical queues.

The backend now combines booking management, automatic priority decisions, queue ticket generation, queue movement, live queue read APIs, rule-based waiting-time estimation, disruption impact analysis, rescheduling workflows, notifications and automated regression verification.

The next objective is to connect these foundations into a complete operational MVP through authentication/roles, check-in, walk-ins, capacity-aware booking, counter lifecycle management and manager-facing APIs before moving into production infrastructure and genuine ML forecasting.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
