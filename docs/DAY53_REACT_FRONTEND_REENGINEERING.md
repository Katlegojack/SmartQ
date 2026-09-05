# Smart Q — Day 53 React + TypeScript Frontend Reengineering

## Status

Day 53 replaces the Smart Q runtime frontend architecture with a React + TypeScript application while preserving the existing Django REST backend, domain rules, authentication model, permissions, URLs and operational data contracts.

**Branch:** `feature/day53-react-frontend`  
**Pull request:** #52 — Day 53 React + TypeScript frontend reengineering  
**Runtime frontend:** React 18 + TypeScript + Vite + React Router + TanStack Query  
**Backend:** Django + Django REST Framework remains authoritative

Final merge and CI metadata are recorded only after the complete feature/PR regression gates pass.

---

## 1. Why Day 53 exists

The Day 41–52 frontend successfully exposed Smart Q's backend features and made live product testing possible, but it still carried the visual and structural characteristics of a prototype dashboard:

- excessive cards and boxed sections;
- repeated generic dashboard layouts across fundamentally different roles;
- inconsistent information density;
- engineering-oriented presentation leaking into operational screens;
- manually coordinated browser fetch state spread across large page scripts;
- role screens optimized for demonstrating features rather than completing jobs.

Day 53 treats that frontend as successful prototype infrastructure, not the final product design.

The reengineering rule is:

> **A production interface is organized around the user's job, not around the number of features the system has.**

---

## 2. What did not change

Day 53 is deliberately not a backend rewrite.

The following remain authoritative:

```text
Django sessions + CSRF
Profile roles
Branch scope
Counter assignment scope
Customer ownership scope
Booking + QueueTicket lifecycle
Queue priority calculation
Queue number allocation
Appointment slot generation
Capacity validation
Check-in eligibility
Counter lifecycle services
QueueEvent audit history
Disruption/rescheduling logic
System Admin invariants
SQLite3 persistence
```

The existing `/api/v1/` routes remain stable. React is an API client, not a second business-logic layer.

---

## 3. New runtime architecture

```text
Browser
  |
  v
React 18 + TypeScript
  |
  +-- React Router
  +-- TanStack Query
  +-- Smart Q role-specific design system
  |
  v
same-origin /api/v1/*
  |
  v
Django REST Framework
  |
  +-- authentication + CSRF
  +-- permissions
  +-- serializers / read models
  +-- workflow APIs
  +-- domain services / transactions
  |
  v
Django ORM -> SQLite3
```

Django still owns the public URL entry points. Every existing frontend route renders one thin React host template and boots the same compiled application.

---

## 4. Toolchain

Day 53 introduces:

```text
React 18
TypeScript 5
Vite 5
React Router 6
TanStack Query 5
Node.js 22 in CI
```

The production frontend build is emitted into:

```text
static/react/app.js
static/react/app.css
```

Django serves those static assets through the existing project static-file architecture.

---

## 5. Preserved public URLs

No user-facing route migration is required.

```text
/                       Smart Q public entry
/login/                 Customer sign in
/staff-login/           Staff role sign in
/register/              Customer registration
/app/                   Role router
/app/customer/          Customer
/app/reception/         Receptionist
/app/counter/           Counter Staff
/app/manager/           Branch Manager
/app/admin/             System Admin
/app/history/           Manager/Admin history + disruption
/app/recovery/          Customer recovery
```

This is an important migration choice: architecture changes underneath stable product URLs.

---

## 6. Authentication and session architecture

The React API client preserves Smart Q's same-origin Django session design.

For unsafe writes it first obtains the CSRF token from:

```http
GET /api/v1/accounts/csrf/
```

Requests use browser credentials and continue to depend on backend authorization.

Role routing remains explicit:

```text
customer       -> /app/customer/
receptionist   -> /app/reception/
counter_staff  -> /app/counter/
branch_manager -> /app/manager/
system_admin   -> /app/admin/
```

Secondary routes remain allowlisted instead of accepting arbitrary `next` destinations.

Every protected React workspace restores `/api/v1/accounts/me/` and verifies the exact expected role before rendering operational content.

---

## 7. Shared account security

Day 53 preserves password-change parity across operational roles.

The shared React shell provides an Account Security dialog that calls:

```http
POST /api/v1/accounts/change-password/
```

The browser verifies that the new password and confirmation match, while Django password validators remain authoritative. Successful password rotation keeps the current trusted session active, matching the established backend contract.

---

# Part 2 — Product Design Reengineering

## 8. Design rule

Day 53 does not translate the old HTML into JSX one-for-one.

That would preserve the architecture problem while changing only syntax.

The new Smart Q design system intentionally uses:

- restrained dark green / neutral surfaces;
- stronger typography and whitespace hierarchy;
- low border-radius usage;
- limited shadows;
- fewer floating cards;
- operational tables where comparison matters;
- prominent current-task states where action matters;
- role-specific layouts instead of one universal dashboard template.

No role is forced into the same visual structure as another role.

---

## 9. Public experience

The public entry page becomes a product statement rather than a feature dashboard.

The interface explains the core customer journey:

```text
Book -> Check in -> Get served
```

A live-queue example communicates the product directly through queue number, people ahead and estimated wait rather than technical architecture copy.

---

## 10. Customer experience

The Customer workspace is intentionally calmer than the staff applications.

Primary information hierarchy:

```text
Live queue if active
Next visit
Book / reschedule
Upcoming visits
Recent history
```

### Live state

Customer booking and queue state refetch every 5 seconds.

```http
GET /api/v1/bookings/my/
GET /api/v1/queues/my-current/
```

Today's slot availability refreshes every 15 seconds while the user is selecting an appointment time.

### Check-in behavior

The Check in action is rendered only while:

```text
booking.is_checked_in == false
```

After successful check-in, the action disappears from both the next-visit action area and upcoming-visit rows. Cancel remains available while the booking is non-final.

This directly fixes the confusing state where a completed action could still look actionable.

### Appointment creation

React reuses backend availability and final-write validation:

```http
GET  /api/v1/services/branches/<branch>/<service>/availability/?date=...
POST /api/v1/bookings/
```

Past same-day slots are still removed/rejected by the backend using South African local time.

### Normal rescheduling

Day 53 preserves normal customer rescheduling:

```http
PATCH /api/v1/bookings/<id>/reschedule/
```

Branch and service identity stay fixed while the customer chooses a new valid date/time. The backend returns the ticket to `SCHEDULED`, clears check-in, and requires a fresh check-in.

### Live queue entry

Registered customers can still join a live queue without an appointment:

```http
POST /api/v1/bookings/walk-ins/
```

The backend owns priority and prevents a second simultaneous active queue.

### Pregnancy priority input

Pregnancy remains visit-specific and is shown only for a female profile. The backend independently revalidates eligibility before priority can be influenced.

---

## 11. Receptionist experience

Reception becomes an operational desk, not an explanatory dashboard.

Primary layout:

```text
Search
Today's customers
Live queue
Add customer
```

### Live coordination

Today's workload and live waiting queue refresh every 5 seconds:

```http
GET /api/v1/bookings/reception/today/
GET /api/v1/queues/branches/<branch>/waiting/
```

This shortens the Day 51 polling interval from 15 seconds and makes Customer -> Reception -> Counter coordination feel substantially more immediate without introducing WebSocket infrastructure yet.

### Search

Search remains exception handling, not the default state. The React client mirrors the backend's two-character minimum and keeps Today as the normal operational view.

### Check-in

Reception uses the existing staff check-in workflow:

```http
POST /api/v1/bookings/<id>/staff-check-in/
```

### Guest walk-ins

Guest walk-ins still use:

```http
POST /api/v1/bookings/reception/walk-ins/
```

The form is reset only after a successful backend write. Failed submissions keep the entered customer data so Reception can correct the problem instead of typing everything again.

---

## 12. Counter Staff experience

The Counter Staff workspace is now a serving console.

The largest visual object is the current queue ticket, not a dashboard metric.

```text
COUNTER
CURRENT CUSTOMER
queue number
customer
service

Complete service | No show

Open / Pause / Resume / Close

Waiting queue
```

Backend endpoints are unchanged:

```http
GET  /api/v1/counters/my/
GET  /api/v1/queues/counters/<id>/current/
GET  /api/v1/queues/branches/<branch>/waiting/
POST /api/v1/queues/counters/<id>/call-next/
POST /api/v1/queues/counters/<id>/complete/
POST /api/v1/queues/counters/<id>/no-show/
POST /api/v1/counters/<id>/open/
POST /api/v1/counters/<id>/pause/
POST /api/v1/counters/<id>/resume/
POST /api/v1/counters/<id>/close/
```

Counter/current/waiting state refreshes every 5 seconds. Backend operation errors are surfaced directly in the workspace rather than failing silently.

---

## 13. Branch Manager experience

Manager becomes a dense live operations surface.

Top-line operational metrics:

```text
Customers today
Waiting
Serving
Open counters
Busy counters
```

The primary table shows:

```text
Counter
Assigned staff
Status
Current customer
Controls
```

Service demand is shown as relative pressure bars instead of another collection of generic stat cards.

Manager dashboard state refreshes every 5 seconds through:

```http
GET /api/v1/dashboard/branches/<branch>/
```

Staff assignment reuses:

```http
GET  /api/v1/counters/branches/<branch>/counter-staff/
POST /api/v1/counters/<counter>/assign/
POST /api/v1/counters/<counter>/unassign/
```

Operational errors are visible, and an unstaffed closed counter is not presented as immediately openable.

---

## 14. System Admin experience

System Admin is designed as a management console rather than a feature dashboard.

Primary areas:

```text
Branches
Services
Branch services
Staff
```

### Branches

Admins can create and update:

```text
branch code
name
city
address
opening time
closing time
active state
```

The React form performs an early `closing > opening` check for usability; the Django serializer remains authoritative.

### Services

Admins can create and update service catalogue entries, average service time and active state.

### Branch services

Admins can create mappings and edit existing mapping capacity/active state. Branch/service identity is locked during mapping edit, preserving the original Day 48 invariant.

### Staff

Admins can create full staff accounts and edit the safe fields exposed by the current staff read/write contract:

```text
first name
last name
email
role
branch
```

Creation still collects required DOB/gender/password profile data. System Admin branch is forced to null; branch-scoped roles require a branch.

The current logged-in admin is clearly identified and is not offered a self-deactivation shortcut. Backend last-active-admin protections remain authoritative for every write.

---

## 15. History, disruptions and recovery

Day 49 behavior is not discarded by the React cutover.

Manager/Admin history reuses:

```http
GET /api/v1/queues/branches/<branch>/reports/operational/
GET /api/v1/queues/branches/<branch>/events/
GET/POST /api/v1/rescheduling/branches/<branch>/pauses/
POST /api/v1/rescheduling/pauses/<id>/resume/
```

Customer recovery reuses:

```http
GET  /api/v1/rescheduling/recommendations/my/
POST /api/v1/rescheduling/options/<id>/select/
```

The backend still performs final capacity and stale-option validation.

---

# Part 3 — State Management

## 16. Why TanStack Query

Smart Q is dominated by server state:

```text
booking status
queue position
counter assignment
current customer
waiting customers
branch configuration
service configuration
recovery recommendations
```

TanStack Query centralizes:

- request lifecycle;
- caching;
- background refetch;
- invalidation after writes;
- loading/error state;
- window-focus refresh.

This replaces large amounts of page-specific manual refresh orchestration.

---

## 17. Current live strategy

Day 53 deliberately uses short polling rather than immediately adding WebSockets.

```text
Customer booking/queue      5 seconds
Reception workload/queue    5 seconds
Counter/current/waiting     5 seconds
Manager live dashboard      5 seconds
Same-day availability      15 seconds
```

Writes also invalidate related queries immediately.

This means local actions update without waiting for the next poll while remote-role actions become visible within a short predictable interval.

### Trade-off

WebSockets or Server-Sent Events could reduce cross-client latency below polling intervals, but they would introduce deployment, reconnect, channel authorization and connection-lifecycle complexity. Day 53 first fixes architecture and product design using the already stable HTTP API contracts.

---

# Part 4 — Migration and Compatibility

## 18. Django host template

All frontend entry routes now render:

```text
templates/frontend/react_app.html
```

The host contains the React root and compiled asset references.

Historical Day 41–52 template regression markers are retained in an inert `<template>` element during this migration so the old tests remain evidence of previously accepted route contracts without executing or rendering the old runtime.

The new Day 53 suite separately protects the actual React runtime architecture and workflows.

---

## 19. Legacy static frontend

The old CSS/vanilla-JS assets remain in the repository during Day 53 to preserve regression evidence and reduce migration risk.

They are **not** the primary runtime architecture after the React route cutover.

A later cleanup can remove them only after the React runtime has been live-tested and historical tests have been deliberately migrated rather than silently deleted.

---

# Part 5 — CI and Verification

## 20. React build gate

GitHub Actions now installs Node.js 22 and runs:

```bash
cd frontend
npm install
npm run build
```

The build runs TypeScript compilation before Vite output:

```text
tsc -b
vite build
```

Day 53 CI development already caught and corrected ESM/Node TypeScript configuration problems before backend regressions were allowed to run. This is exactly what a build gate should do.

---

## 21. Day 53 focused regression suite

```bash
python manage.py test smartq.test_day53_react_frontend
```

The suite protects:

- one React runtime across existing Smart Q URLs;
- generated `static/react` assets;
- React/TypeScript/Vite/Router/Query toolchain;
- role routing and safe secondary routes;
- shared account security;
- customer live state, check-in disappearance, rescheduling and walk-in contracts;
- Reception live workload/check-in/walk-in contracts;
- Counter operational contracts;
- Manager live operations contracts;
- System Admin CRUD and operating-hour contracts;
- history/disruption/recovery React surfaces;
- responsive and accessibility design rules.

---

## 22. Regression philosophy

The React rewrite must not pass simply because the new frontend builds.

The CI pipeline continues to run:

```text
missing migration check
Django system check
accounts
branches
services
counters
queues
bookings
notifications
dashboard
rescheduling
Day 36 audit
Day 39 reporting
Day 40 backend audit
Day 41–52 historical frontend/integration tests
legacy JavaScript syntax gate
Day 53 React gate
full Django test suite
```

A frontend architecture migration is considered successful only if backend behavior and security remain intact.

---

# Part 6 — Development Commands

## 23. Codespaces / local integrated build

From the repository root:

```bash
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python manage.py migrate
python manage.py bootstrap_demo
python manage.py runserver 0.0.0.0:8000
```

Django then serves the compiled React frontend at the normal Smart Q URLs.

## 24. Frontend development server

For focused frontend work:

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

Vite proxies `/api` requests to Django on port 8000.

## 25. Verification commands

```bash
cd frontend
npm run typecheck
npm run build
cd ..
python manage.py check
python manage.py test smartq.test_day53_react_frontend
python manage.py test
```

---

# Part 7 — Engineering Decisions and Lessons

## 26. React does not automatically improve UX

A poor dashboard rewritten in React is still a poor dashboard.

Day 53 therefore changes both the framework architecture and the information architecture.

## 27. Stable backend contracts make frontend rewrites possible

Days 28–52 invested heavily in service layers, permissions, serializers, tests and API boundaries. That work is why Day 53 can replace the browser layer without replacing queue logic.

## 28. Role-specific UX is more important than component reuse

Shared components are valuable for buttons, fields, status, security and shell behavior. The actual operational pages should not be forced into one generic dashboard template simply to maximize reuse.

## 29. Server state belongs in a server-state tool

Bookings and queues are not local form state. TanStack Query makes refresh, invalidation and stale-response behavior explicit instead of hiding it inside page scripts.

## 30. Migration tests should preserve behavior, not obsolete implementation

The permanent goal is to protect URLs, security, workflows and user-visible behavior. The old vanilla-JS implementation is temporary evidence, not the future contract.

---

## 31. Day 53 completion rule

Day 53 is complete only when:

```text
React production build passes
        +
TypeScript passes
        +
Day 53 focused tests pass
        +
all earlier Smart Q regression gates pass
        +
full Django suite passes
        +
PR CI passes
        +
PR is merged
        +
post-merge main CI passes
```

Until those conditions are satisfied, the reengineering remains a release candidate rather than a completed milestone.
