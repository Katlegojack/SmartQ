# Smart Q - Day 45 Engineering Documentation

## Receptionist Workspace, Assisted Check-In and Guest Walk-Ins

## 1. Day 45 goal

Day 45 replaces the generic Reception shell from Day 42 with a working branch-scoped receptionist workspace connected to the backend reception contract completed on Days 29-31.

The receptionist can now perform four real operational tasks from `/app/reception/`:

```text
see assigned branch scope
        ↓
search branch bookings
        ↓
assist eligible customer check-in
        ↓
register no-account guest walk-ins
        ↓
watch the branch WAITING queue
```

The browser coordinates these tasks, while Django remains authoritative for branch scope, check-in eligibility, guest identity, service availability, priority, queue-number allocation and queue state.

---

## 2. Starting point

Before Day 45 the backend already exposed:

```http
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/reception/walk-ins/
POST /api/v1/bookings/<id>/staff-check-in/
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/services/branches/<branch_id>/
```

The frontend route `/app/reception/` still rendered only the generic role-aware shell.

Day 45 therefore does not invent a second receptionist business layer. It connects a dedicated operating screen to those existing contracts.

### Engineering lesson

A frontend milestone should first ask: "Which backend contract already owns this workflow?" If the answer exists, integration is usually safer than rewriting the rule in JavaScript.

---

## 3. Dedicated receptionist route

`smartq/urls.py` now maps:

```text
/app/reception/
```

to:

```text
frontend/reception_dashboard.html
```

instead of the generic `app_shell.html`.

The page still includes the Day 42 app-shell module and declares:

```html
data-app-shell
data-expected-role="receptionist"
```

so existing session restoration and role-routing behavior remains active.

### Engineering lesson

Specializing a role workspace should preserve shared authentication infrastructure. Reuse the shell contract and replace only the operational surface.

---

## 4. Branch scope is identity, not a form field

Receptionists do not choose a branch from a dropdown.

The browser calls:

```http
GET /api/v1/accounts/me/
```

and uses the returned `branch_id` and `branch_name` only to address branch-scoped read APIs and explain the current scope to the user.

The backend independently enforces the same boundary through `Profile.branch` and `IsQueueViewer`.

### Engineering lesson

When scope comes from authenticated identity, do not turn it into editable input. A receptionist selecting another branch in the browser would create misleading UX even if the backend later rejects it.

---

## 5. Reception overview metrics

The Day 45 overview shows:

```text
waiting tickets
priority tickets
general tickets
operating branch
```

These counts come from the live waiting-queue response. The frontend does not estimate queue population from appointments or local history.

### Engineering lesson

Operational dashboards should summarize the same read model that powers the detailed table. Two different client-side definitions of "waiting" eventually disagree.

---

## 6. Branch booking search

The search form accepts at least two characters and sends:

```http
GET /api/v1/bookings/reception/search/?q=<query>
```

The backend search supports booking ID, username, first/last name, email, guest name and guest phone number.

The response is rendered as an operational table containing:

```text
customer
booking id
appointment date/time
service
booking status
queue reference/state
eligible receptionist action
```

A monotonically increasing search request identifier prevents an older response from replacing a newer search result if network responses arrive out of order.

### Engineering lessons

Search is asynchronous state. A slower old request should never overwrite a newer user intention.

Branch filtering belongs in the backend query, not in JavaScript after receiving global data. Data the receptionist may not see should never be sent to the browser in the first place.

---

## 7. Assisted staff check-in

For a non-final online booking that is not already checked in, the result table exposes a Check in action.

The browser calls:

```http
POST /api/v1/bookings/<booking_id>/staff-check-in/
```

It does not calculate the six-hour check-in window.

The existing backend workflow decides whether the booking is:

```text
eligible
not open yet
already checked in
expired and cancelled
final state
outside branch scope
```

After a successful mutation, Day 45 refreshes both the search result and waiting queue.

### Engineering lessons

A button being visible is not authorization. The endpoint still owns object-level branch permission and check-in timing.

After a state-changing workflow, refresh every read model that the mutation affects. Staff check-in changes both the booking row and live waiting queue.

---

## 8. Guest walk-in workflow

Reception can register a customer who has no Smart Q account.

The form captures only backend-supported facts:

```text
full name
optional phone number
date of birth
gender
disability status
pregnancy for the visit
service
```

The branch is not submitted as an editable choice. The receptionist's authorised branch is selected server-side.

The form loads services from:

```http
GET /api/v1/services/branches/<branch_id>/
```

so a guest cannot be assigned to a service that is not offered by that branch through the UI.

### Engineering lesson

A form should collect facts the operator actually knows. Derived decisions such as queue type and branch authority should stay out of operator input.

---

## 9. Priority remains backend-controlled

The walk-in form deliberately contains no General/Priority selector.

The backend derives priority from the established Smart Q policy:

```text
age >= 55
OR disability status
OR female + pregnancy for this visit
```

The browser only reveals the pregnancy checkbox when gender is female. The API revalidates the same rule, so hidden fields are not trusted.

During implementation, the frontend gender options were checked against `Profile.GENDER_CHOICE`. An unsupported `prefer_not_to_say` option was removed before closeout because the backend contract currently accepts only:

```text
male
female
other
```

### Engineering lessons

Frontend choices must be generated from or intentionally synchronized with domain enums. A visually harmless extra option becomes a real API failure when the server rejects it.

Priority affects fairness. It must be derived by one trusted backend policy rather than receptionist discretion or client logic.

---

## 10. Walk-ins enter the live queue immediately

A successful guest walk-in is not a future appointment.

Existing backend logic creates:

```text
Booking.source = WALK_IN
checked_in_at = now
QueueTicket.status = WAITING
```

The backend also allocates the queue number and queue type.

Day 45 displays the returned queue reference and refreshes the waiting queue after creation.

### Engineering lesson

The frontend should present the result of allocation, not simulate allocation. Queue identifiers and fairness ordering have cross-user concurrency implications and belong on the server.

---

## 11. Live waiting queue

The workspace calls:

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
```

and supports the backend queue-type filter:

```text
?queue_type=priority
?queue_type=general
```

The table shows:

```text
queue number
customer
booking id
service
queue type
check-in time
status
```

The endpoint returns today's `WAITING` tickets only, using the existing queue service ordering.

### Engineering lesson

A receptionist dashboard should read the same queue ordering the counter workflow will consume. Re-sorting according to a frontend guess risks showing staff a different queue from the one the backend actually serves.

---

## 12. Explicit refresh instead of fake real-time

Day 45 includes a Refresh queue action and automatic refreshes after receptionist mutations.

It does not introduce WebSockets, aggressive polling or pretend that the screen is continuously synchronized.

### Trade-off

Manual/event-driven refresh is simpler and sufficient for the current milestone. True real-time transport can be added later when deployment architecture, connection scale and operational need justify it.

### Engineering lesson

Do not solve a future synchronization problem by silently introducing infrastructure in a role-screen milestone. Make freshness behavior explicit.

---

## 13. Error handling

The receptionist workspace preserves structured API messages for workflows such as:

```text
search query too short
check-in too early
booking already checked in
booking expired
wrong branch
unsupported service
future date of birth
invalid pregnancy input
permission denied
```

Successful mutations provide an operational confirmation and then refresh authoritative state.

### Engineering lesson

Staff-facing errors should explain the operational condition, not merely say that a request failed. The staff member needs to know what can happen next.

---

## 14. Responsive and accessible structure

Day 45 continues the Day 41 visual system:

```text
white surfaces
light-blue structure
restrained green success
small borders and radii
no emoji interface language
native form controls
visible labels
keyboard-operable actions
```

Desktop uses compact metric cards, multi-column walk-in fields and wide operational tables. Narrow screens collapse forms and metrics while tables remain horizontally scrollable rather than deleting operational fields.

### Engineering lesson

For operations software, responsive design should preserve information density and task meaning. Hiding important queue fields on mobile can be worse than allowing controlled horizontal scrolling.

---

## 15. Files changed

### Added

```text
templates/frontend/reception_dashboard.html
static/js/pages/reception-dashboard.js
static/css/reception-dashboard.css
smartq/test_day45_receptionist_workspace.py
docs/DAY45_RECEPTIONIST_WORKSPACE.md
```

### Updated

```text
smartq/urls.py
.github/workflows/django-tests.yml
README.md
```

No new database model or migration is required for Day 45.

---

## 16. Automated verification

The focused Day 45 suite verifies:

```text
reception route renders the dedicated operating contract
reception JS/CSS assets are discoverable
frontend references the existing reception APIs
frontend does not submit queue_type or queue_number allocation fields
branch search finds the expected booking
staff check-in moves the scheduled ticket to WAITING
waiting queue reflects the checked-in booking
guest walk-in is branch-scoped
walk-in enters WAITING immediately
backend assigns eligible priority and queue number
receptionist cannot read another branch waiting queue
customer cannot use reception search or walk-in creation
```

CI runs:

```powershell
python manage.py test smartq.test_day45_receptionist_workspace
```

before the complete Smart Q regression suite.

### Engineering lesson

A role workspace test should prove the end-to-end contract between page, permission boundary and lifecycle mutation, not only assert that HTML exists.

---

## 17. Product boundaries preserved

Day 45 does not add:

```text
frontend branch authorization
frontend check-in window calculation
frontend priority selection
frontend queue-number generation
frontend queue ordering rules
registered-account creation for guests
counter serving controls
manager controls
WebSockets
ML queue changes
```

Reception handles intake and activation. Counter service remains Day 46.

---

## 18. Day 45 completion rule

Day 45 is complete when:

```text
dedicated receptionist workspace renders
assigned branch is visible and non-editable
branch booking search works
assisted check-in uses server workflow
guest walk-in uses branch service catalogue
priority and queue number stay backend-owned
waiting queue is visible and filterable
wrong-branch access remains denied
focused Day 45 suite passes
previous frontend suites remain compatible
complete Smart Q regression passes
exact branch head passes GitHub Actions
README and permanent documentation are updated
```

---

## 19. Next milestone - Day 46

Day 46 moves to the Counter Staff workspace.

The next frontend slice should connect the existing assigned-counter and queue-operation contracts:

```text
assigned counter state
open / pause / resume / close
current serving ticket
call next
complete service
mark no-show
clear operating-state feedback
```

The same architecture rule continues:

```text
browser presents and coordinates
backend decides and protects
```
