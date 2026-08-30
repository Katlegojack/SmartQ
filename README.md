# Smart Q

**Where Time Meets Priority**

Smart Q is a Django-based **Queue Intelligence Platform** designed to make queues more predictable, transparent, fair, and operationally efficient.

The platform is being built around the complete service journey rather than appointment booking alone: customers create bookings, receive queue tickets and track queue progress; staff operate live counters; reception and managers receive role-appropriate operational visibility; and the backend provides the foundation for disruption recovery, analytics, and future ML-based waiting-time prediction.

> **Current development state:** Day 29 authentication + role-based branch authorization is implemented and verified on `feature/day29-auth-roles`. GitHub Actions passes the migration check, Django system check, account tests, queue tests, booking tests, and the full project test suite. PR #17 is temporarily based on `feature/day28-operational-core` because Day 28 PR #16 is still marked Draft in GitHub.

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

Business rules remain in backend service functions so the frontend does not become responsible for queue state, priority rules, or operational decisions.

---

## Smart Q Roles

Day 29 introduces the first Smart Q-specific authorization model:

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
| Receptionist | Read live queue state for assigned branch |
| Counter Staff | Read + operate live queue for assigned branch |
| Branch Manager | Read + operate live queue for assigned branch |
| System Admin | Global operational access |

Branch rules are enforced by the Profile model/database:

```text
CUSTOMER        → branch = NULL
SYSTEM_ADMIN    → branch = NULL
RECEPTIONIST    → branch required
COUNTER_STAFF   → branch required
BRANCH_MANAGER  → branch required
```

Existing profiles migrate safely to `CUSTOMER`. Existing Django superusers are mapped to `SYSTEM_ADMIN`; ordinary historical `is_staff=True` users are not automatically granted Smart Q operational authority.

---

## Authentication

Day 29 adds the account API foundation using Django session authentication.

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

Public registration always creates:

```text
role = CUSTOMER
branch = NULL
is_staff = False
is_superuser = False
```

Caller-supplied privilege fields cannot promote the account. Django password validators are reused, and User + Profile creation is transactional.

### Production authentication note

Session authentication is a valid Django/DRF foundation. If the final production frontend is hosted on another origin, Smart Q will require an explicit CORS, CSRF, secure-cookie, and deployment strategy. JWT/token authentication will be chosen only if the deployment architecture requires it.

---

## Core Queue Flow

```text
Authenticated Identity
        ↓
Smart Q Profile + Role
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

Cancellation and rescheduling are controlled alternate paths. A future phase will add explicit customer **check-in** before a scheduled booking joins the live operational queue.

---

## Current Backend Capabilities

Smart Q currently includes:

- Django users + Smart Q Profiles
- Customer / Receptionist / Counter Staff / Branch Manager / System Admin roles
- Branch-scoped staff authorization
- Branches and services
- Customer bookings
- automatic General/Priority decisions
- queue numbers (`A001`, `P001`, ...)
- queue tickets and lifecycle states
- counters
- Call Next / Complete / No Show operations
- Booking ↔ QueueTicket state synchronization
- rule-based queue position and wait-time estimation
- customer live queue tracker API
- staff waiting-queue and current-counter APIs
- cancellation and rescheduling APIs
- queue disruption/rescheduling backend foundation
- in-app notifications
- automated Django/DRF regression tests
- GitHub Actions CI

Current waiting-time estimation is **rule-based, not ML**. A trained prediction model remains future work.

---

## REST API

### Accounts

```http
POST /api/v1/accounts/register/
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

### Catalogue

```http
GET /api/v1/branches/
GET /api/v1/services/
```

### Bookings

```http
POST  /api/v1/bookings/
GET   /api/v1/bookings/my/
GET   /api/v1/bookings/<id>/
PATCH /api/v1/bookings/<id>/cancel/
PATCH /api/v1/bookings/<id>/reschedule/
```

### Customer queue

```http
GET /api/v1/queues/my-current/
```

### Staff queue reads

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

### Queue operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

### Notifications

```http
GET   /api/v1/notifications/
GET   /api/v1/notifications/unread-count/
PATCH /api/v1/notifications/<notification_id>/mark-read/
```

---

## Authorization Model

```text
Authentication
"Who are you?"
        ↓
Smart Q Role
"What kind of action may you perform?"
        ↓
Branch Scope
"Where may you perform it?"
        ↓
Object Permission
"May you act on this Branch/Counter?"
```

Important safeguards now include:

- customers cannot operate counters;
- receptionists can read but not mutate live queue state;
- counter staff and branch managers are restricted to their branch;
- system administrators can operate globally;
- public registration cannot create privileged accounts;
- customer booking data remains user-scoped;
- critical queue changes use database transactions;
- Booking and QueueTicket lifecycle states stay synchronized;
- regression tests cover both valid and denied operations.

---

## Automated Verification

GitHub Actions currently runs:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test
```

**Day 29 final result: all stages PASS.**

---

## Documentation

Permanent engineering records:

```text
docs/DAY28_OPERATIONAL_CORE.md
docs/DAY29_AUTH_ROLES.md
```

Smart Q daily documentation records the objective, architecture, code, API contract, security decisions, test commands, bugs/fixes, CI results, limitations, and next step.

---

## Current Git Workflow State

```text
main
  ↑
PR #16 - Day 28 (verified, still Draft in GitHub)
  ↑
feature/day28-operational-core
  ↑
PR #17 - Day 29 (verified, Draft)
  ↑
feature/day29-auth-roles
```

PR #17 temporarily targets the verified Day 28 branch. After PR #16 is manually marked **Ready for review** and squash-merged, PR #17 should be retargeted to `main` and merged after its checks are confirmed.

---

## Known Operational Gaps

The next important work includes:

1. Customer arrival/check-in before joining the live queue.
2. Walk-in/reception ticket workflow.
3. Capacity-aware booking availability.
4. Branch ↔ Service mapping.
5. Counter lifecycle and staff-to-counter assignment.
6. Manager dashboard and disruption-management APIs.
7. Historical queue event timestamps for analytics/ML.
8. Password reset/account verification and login throttling.
9. Final production CORS/CSRF/session-or-token authentication deployment strategy.
10. External SMS/email/WhatsApp/push notifications.
11. PostgreSQL, environment secrets, HTTPS, logging, monitoring, and backups.
12. Queue-number concurrency hardening.
13. Genuine trained/evaluated ML waiting-time prediction.

---

## Roadmap

### Implemented foundation

```text
Profiles
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
Authentication APIs
Smart Q Roles
Branch Authorization
Automated Tests
CI
```

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
Secure configuration
CORS/CSRF deployment policy
External notifications
Real-time delivery
Monitoring
Backups
Audit/compliance
```

### Analytics + AI phase

```text
Historical dataset
Actual wait/service-duration measurement
Demand/peak analysis
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
| Future AI | Trained/evaluated ML waiting-time forecasting |

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

Verify the project:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

---

## Product Maturity

| Stage | Meaning | Current position |
|---|---|---|
| Pitch prototype | Product journey can be demonstrated | Strong foundation |
| Pilot operational MVP | Safe real customer/staff workflow at one branch | In progress |
| Production platform | Secure, monitored, scalable, enterprise-ready | Future work |

---

## Final Project Statement

Smart Q is being built to give customers greater control over time normally lost in uncertain physical queues while giving service organisations safer and clearer operational control.

The backend now combines booking management, priority decisions, queue tickets, queue movement, waiting-time estimation, disruption/rescheduling logic, notifications, live queue APIs, authentication, and a real role/branch authorization foundation.

```text
Make queues fairer, smarter, more transparent,
and more respectful of people's time.
```

## Author

**Katlego Mmako**
