# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and operationally efficient.

The platform is being built around the complete service journey rather than appointment booking alone: customers create bookings, receive queue tickets and track queue progress; staff operate live counters; reception and managers receive role-appropriate operational visibility; and the backend provides the foundation for disruption recovery, analytics, and future ML-based waiting-time prediction.

> **Current development state:** Day 29 authentication + role-based branch authorization is implemented on `feature/day29-auth-roles` and is undergoing final CI verification. It builds on the verified Day 28 operational core. PR #17 is temporarily based on `feature/day28-operational-core` because Day 28 PR #16 is still marked Draft in GitHub.

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
Who is allowed to operate this branch?
What happens when service is disrupted?
Which customers may need rescheduling?
Has the customer been notified?
How is the branch performing?
```

The product is intended to evolve toward use in environments such as government service centres, municipalities, banks, hospitals, clinics, universities, embassies, retail service desks, and other high-volume service organisations.

A core product principle is:

> **Every Smart Q workflow should reduce uncertainty for customers, staff, and managers.**

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

Business rules remain in backend service functions so the frontend does not become responsible for queue state, priority rules, or operational decisions.

---

## Smart Q User Roles

Day 29 introduces the first Smart Q-specific authorization model.

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

### Customer

Customer-facing account. Public registration always creates this role.

### Receptionist

May view live waiting/current queue information for the assigned branch but may not perform queue service transitions.

### Counter Staff

May view and operate live queues for the assigned branch.

### Branch Manager

May view and operate live queues for the assigned branch. This role is also the foundation for future manager APIs.

### System Administrator

Global Smart Q operational role. Not restricted to one branch.

### Branch scope rules

```text
CUSTOMER        → branch = NULL
SYSTEM_ADMIN    → branch = NULL
RECEPTIONIST    → branch required
COUNTER_STAFF   → branch required
BRANCH_MANAGER  → branch required
```

A database constraint enforces these combinations.

Existing profiles migrate safely to `CUSTOMER`. Existing Django superusers are mapped to `SYSTEM_ADMIN`; ordinary historical `is_staff=True` users are **not** automatically promoted into Smart Q operational roles.

---

## Authentication

Day 29 adds a customer authentication REST foundation using Django's built-in session authentication.

### Account APIs

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

### Registration security

Public registration accepts normal customer information only and always creates:

```text
role = CUSTOMER
branch = NULL
is_staff = False
is_superuser = False
```

The client cannot self-assign a staff/admin role by sending extra privilege fields.

Django's configured password validators are reused, and User + Profile creation occurs in one database transaction.

### Session-auth deployment note

Session authentication is a valid Django/DRF foundation. If the final production frontend is hosted on a different origin, Smart Q will need an explicit **CORS + CSRF + secure-cookie deployment strategy** before launch. JWT is not being added merely for appearance without first choosing the deployment architecture.

---

## Core Domain Flow

```text
Customer Identity
   ↓
Profile + Role
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

`Profile` stores:

- date of birth
- gender
- disability status
- Smart Q role
- optional staff branch assignment

Current automatic queue priority logic can classify a booking as Priority when:

```text
Age >= 55
OR disability_status = True
OR pregnancy-related priority applies
```

Queue number examples:

```text
A001 → General
P001 → Priority
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
- validate past dates
- validate time against branch operating hours

### Queue tickets

Queue states:

```text
waiting
serving
completed
no_show
cancelled
```

QueueTicket contains its booking relationship, queue number/type, current status, optional counter assignment, and creation time.

### Counters

Counters represent service points and currently support queue operating states such as open, closed, and paused.

### Waiting-time intelligence

The current estimator is **rule-based**, not machine learning.

It uses concepts such as:

```text
people ahead
average service time
active counters
```

Conceptually:

```text
Estimated Wait ≈
(People Ahead × Average Service Time)
÷ Active Counters
```

The backend can calculate:

- people ahead
- queue position
- estimated wait time

This provides the baseline that a future ML model can later improve and be evaluated against.

### Disruption and rescheduling foundation

Existing backend work includes:

- queue pause/disruption tracking
- lost service capacity
- affected customer detection
- reschedule-risk detection
- disruption impact records
- reschedule recommendations/options
- approval/application workflows
- queue-number regeneration after rescheduling
- reschedule confirmation notifications

### Notifications

The in-app notification foundation supports:

- notification records
- types
- message body
- related queue/disruption records
- read/unread state
- unread count
- mark-as-read flow

External SMS, WhatsApp, email, and push delivery remain future work.

---

## REST API Status

### Account / authentication

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

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

Booking ownership is scoped to `request.user`.

### Customer queue tracker

```http
GET /api/v1/queues/my-current/
```

Returns the customer's active ticket with current queue position and rule-based estimated wait.

### Staff queue reads

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

Allowed for queue-viewer roles in their assigned branch; `SYSTEM_ADMIN` is global.

### Staff queue operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Allowed for:

```text
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Receptionists can view queue state but cannot perform these service transitions.

### Notifications

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

---

## Security Direction

Authentication and authorization are intentionally separated:

```text
Authentication
"Who are you?"
        ↓
Smart Q role
"What category of work may you perform?"
        ↓
Branch scope
"Where may you perform it?"
        ↓
Object permission
"May you act on this specific Branch/Counter?"
```

Important current safeguards:

- customers cannot operate counters;
- public registration cannot create staff/admin identities;
- receptionists are read-only for current queue operations;
- branch staff are restricted to their assigned branch;
- system administrators are global;
- customers can only read/modify their own booking data;
- queue state changes use transactions;
- Booking and QueueTicket terminal states are synchronized;
- invalid/future queue operations have regression tests.

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

The migration check prevents model changes from being committed without their required Django migration.

---

## Development Workflow

Smart Q uses feature branches and pull requests instead of editing `main` directly.

```text
main / verified predecessor
        ↓
feature branch
        ↓
small coherent implementation slice
        ↓
comments + permanent documentation
        ↓
CI verification
        ↓
pull request
        ↓
squash merge
        ↓
update local main
```

Current branches:

```text
feature/day28-operational-core
feature/day29-auth-roles
```

Current PR dependency:

```text
PR #16 Day 28
    ↓
PR #17 Day 29
```

PR #17 temporarily targets the Day 28 branch until PR #16 is manually marked Ready for review and merged.

---

## Documentation

Permanent repository engineering notes:

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
```

Daily documentation should explain:

- objective and business problem
- previous state
- architecture
- code responsibilities
- important code with comments
- API contract
- security reasoning
- state transitions
- shell/API tests
- automated tests
- CI verification
- bugs found/fixed
- known limitations
- next development step

---

## Known Operational Gaps

Smart Q is not production-ready yet. Important remaining work includes:

1. Final production authentication deployment decision (same-origin session vs token/JWT architecture).
2. Password reset / account verification and login throttling.
3. Staff-management APIs and audit logs for role changes.
4. Customer check-in before joining the live queue.
5. Walk-in/reception ticket workflow.
6. Booking slot capacity/availability engine.
7. Branch ↔ Service mapping.
8. Counter lifecycle + staff-to-counter assignment APIs.
9. Manager dashboard APIs.
10. Manager-facing disruption/rescheduling APIs.
11. Historical queue event timestamps.
12. Real-time polling/WebSocket strategy.
13. External notification channels.
14. PostgreSQL production setup, secrets, HTTPS, logs, monitoring, and backups.
15. Queue-number concurrency hardening.
16. Analytics and a genuinely trained/evaluated ML wait-time predictor.

---

## Roadmap

### Completed foundation

```text
Profiles
Branches
Services
Bookings
Queue Tickets
Priority Logic
Queue Numbers
Notifications
Disruption / Rescheduling Foundation
DRF API Foundation
Booking APIs
Queue Operations
Live Queue Read APIs
Regression Tests
CI
```

### Day 29 - Authentication + Authorization

```text
Customer registration
Session login/logout
Current account API
Smart Q role model
Branch staff assignment
Role permissions
Branch object permissions
Privilege-escalation protection
```

**Status:** implemented on `feature/day29-auth-roles`; final CI verification in progress.

### Next operational-MVP phase

```text
Customer Check-In
Walk-Ins / Reception
Booking Availability
Counter Lifecycle
Staff Assignment
Manager APIs
Historical Queue Events
```

### Production phase

```text
PostgreSQL
Environment secrets
HTTPS
CORS/CSRF production config
External notifications
Real-time delivery
Monitoring
Backups
Audit/compliance
```

### Analytics + AI phase

```text
Historical queue dataset
Actual wait/service duration measurement
Demand patterns
Peak-hour analysis
Model training
Model evaluation
ML wait-time prediction
Operational recommendations
```

Current wait-time estimation remains rule-based until a model is actually trained and evaluated.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| API | Django REST Framework |
| Authentication foundation | Django sessions |
| Authorization | Smart Q Profile roles + DRF permissions |
| Language | Python |
| Development database | SQLite |
| Target production database | PostgreSQL |
| Internal administration | Django Admin |
| Testing | Django + DRF APITestCase |
| CI | GitHub Actions |
| Future real-time | Polling first; WebSockets where justified |
| Future AI | Trained/evaluated ML wait-time forecasting |

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

Run checks/tests:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

---

## Product Maturity

| Stage | Meaning | Current position |
|---|---|---|
| Pitch prototype | Full story can be demonstrated; mock frontend data allowed | Strong foundation |
| Pilot operational MVP | Real customer/staff workflow can run safely at one branch | In progress |
| Production platform | Secure, monitored, scalable, audited, enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give customers greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

The backend now combines booking management, priority decisions, queue tickets, queue movement, waiting-time estimation, disruption/rescheduling logic, notifications, live queue APIs, authentication, and the first Smart Q-specific role/branch authorization model.

The immediate engineering priority is to finish the pilot-MVP workflow safely before adding production infrastructure and genuine ML forecasting.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
