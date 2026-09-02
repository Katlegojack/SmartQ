# Smart Q - Day 45 Engineering Documentation

## Receptionist Workspace

## 1. Day 45 goal

Day 45 converts the generic receptionist application shell from Day 42 into a real branch-operational workspace.

The target workflow is intentionally narrow:

```text
Receptionist signs in
        ↓
Smart Q restores role + assigned branch
        ↓
Search customer / booking
        ↓
Inspect appointment + queue state
        ↓
Staff-assisted check-in when valid
        ↓
QueueTicket becomes WAITING
        ↓
Branch queue refreshes
```

For a person without a Smart Q account or advance appointment:

```text
Guest arrives
        ↓
Reception captures minimum operational details
        ↓
Select service offered at receptionist branch
        ↓
Backend creates GuestCustomer + WALK_IN booking
        ↓
Backend calculates General / Priority
        ↓
QueueTicket is created in WAITING
        ↓
Reception shows queue confirmation
```

Day 45 is not a manager dashboard. It contains no branch analytics, reporting controls, staff administration or system configuration.

---

## 2. Starting point

Before Day 45, Smart Q already had:

- the Day 41 design system;
- Day 42 session restoration, CSRF and role routing;
- Day 43 customer dashboard;
- Day 44 appointment booking and rescheduling experience;
- the Day 31 backend reception APIs for search, staff check-in and guest walk-ins;
- branch-scoped queue visibility from the queue API.

The `/app/reception/` route still rendered the generic Day 42 shell. Day 45 replaces only that role surface while preserving the shared visual language and the existing backend authority.

### Engineering lesson

A frontend milestone should integrate proven backend workflows instead of rebuilding their rules in JavaScript.

---

## 3. Backend contracts reused

Day 45 uses existing APIs:

```http
GET  /api/v1/accounts/me/
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/<booking_id>/staff-check-in/
POST /api/v1/bookings/reception/walk-ins/
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/services/branches/<branch_id>/
```

No new queue, booking or priority algorithm was added in the frontend.

### Engineering lesson

The browser should orchestrate backend capabilities, not become a second business-logic server.

---

## 4. Reception route and role boundary

`/app/reception/` now renders:

```text
templates/frontend/reception_workspace.html
```

instead of the generic `app_shell.html`.

The page declares:

```html
data-expected-role="receptionist"
```

The shared session shell and the Day 45 script both verify the authenticated account. A non-receptionist is redirected to the workspace that belongs to their real backend role.

The receptionist's `branch_id` comes only from `/api/v1/accounts/me/`. There is no branch selector in the reception UI.

### Engineering lesson

A branch-scoped operator should not choose their authority scope from a dropdown. Scope is identity data, not form input.

---

## 5. Search-first workspace

Reception work is interruption-heavy and speed-sensitive, so search is the dominant first interaction.

The lookup accepts the identifiers already supported by the backend:

- booking ID;
- username;
- first or last name;
- email;
- guest name;
- guest phone number.

The input is automatically focused when the workspace loads. Receptionists can also press `Ctrl+K` or `Cmd+K` to return focus to search.

The frontend enforces the API's minimum two-character rule before sending a request.

Results display:

```text
Customer
Appointment date/time
Service + branch
Booking ID + booking status
Queue number + queue type/status
Available action
```

### Engineering lesson

Operational screens should optimize the repeated task, not maximize the number of widgets visible at once.

---

## 6. Staff-assisted check-in

A valid search result exposes `Check in` only when the booking is not already checked in and is not in a final state.

The write is sent to:

```http
POST /api/v1/bookings/<id>/staff-check-in/
```

The frontend does not decide whether check-in is actually allowed. The backend still decides:

- whether the six-hour window is open;
- whether the appointment expired;
- whether the booking is already checked in;
- whether the booking is in a final state;
- whether the staff member may operate on that branch.

Important responses are shown directly to reception. For an early check-in, the UI also formats the backend-provided `check_in_opens_at` timestamp.

After success, Smart Q refreshes both the search result and the live branch queue from backend reads.

### Engineering lessons

A disabled button can prevent accidental double-clicks, but only the backend can guarantee idempotency and state correctness.

After a state-changing operation, refresh from authoritative read endpoints rather than guessing the new state locally.

---

## 7. Check-in is live-queue activation

Day 45 preserves the Day 31 domain meaning:

```text
SCHEDULED appointment
        ↓ valid check-in
WAITING live queue
```

Check-in does not mean Smart Q has independently proved physical presence. It means the booking has been activated into the live queue.

This distinction also preserves the difference between:

```text
CANCELLED = appointment expired before check-in
NO_SHOW   = customer checked in but later failed to present when called
```

### Engineering lesson

Status names are domain contracts. If the UI gives them a different meaning from the backend, reporting and user expectations eventually become inconsistent.

---

## 8. Branch queue visibility

Receptionists need enough queue visibility to confirm that a successful check-in or walk-in really entered the branch queue.

Day 45 reads:

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
```

The table shows:

- queue number;
- customer;
- service;
- check-in time;
- queue type;
- waiting status.

It also summarizes counts for Waiting, Priority and General tickets.

This is operational confirmation, not analytics. Day 47 remains responsible for manager-level metrics and historical reporting.

### Engineering lesson

The same underlying data can support different roles, but each role should receive only the presentation needed to perform its job.

---

## 9. Guest walk-in flow

The walk-in form collects only the fields supported by the backend contract:

```text
full_name
phone_number (optional)
date_of_birth
gender
disability_status
is_pregnant (only shown when gender = female)
service
```

Services are loaded from:

```http
GET /api/v1/services/branches/<receptionist_branch_id>/
```

so reception cannot select a service that is not offered at the assigned branch.

The browser does not send a branch ID to the walk-in creation endpoint. The backend derives branch authority from the receptionist's profile.

### Engineering lesson

Do not ask the client to send a security-sensitive value when the server already knows the correct value from authenticated identity.

---

## 10. Priority remains backend-owned

The walk-in UI never offers a General/Priority selector.

Smart Q continues using its existing priority policy:

```text
age 55+
OR disability status
OR female + pregnant for this visit
```

The frontend only captures facts required by that policy. The backend calculates the queue type and returns the final queue number.

On success, the confirmation panel displays the returned:

```text
queue number
customer
service
queue type
status
```

### Engineering lesson

When a value affects fairness, security or allocation, collect inputs in the frontend but make the final decision on the server.

---

## 11. Error and empty states

Day 45 includes explicit states for:

- initial ready state;
- search loading;
- no search results;
- API search errors;
- branch queue loading;
- empty waiting queue;
- guest walk-in validation errors;
- service loading failures;
- staff check-in conflicts;
- successful check-in;
- successful walk-in creation.

Mutating buttons are disabled while requests are in flight to reduce duplicate submissions.

### Engineering lesson

Error handling is part of the workflow, not decoration added after the happy path works.

---

## 12. Files added or changed

```text
templates/frontend/reception_workspace.html
static/css/reception-workspace.css
static/js/pages/reception-workspace.js
smartq/urls.py
smartq/test_day45_reception_workspace.py
docs/DAY45_RECEPTION_WORKSPACE.md
```

---

## 13. Test coverage

Day 45 adds frontend/integration regression checks for:

- the dedicated reception template route;
- required reception controls being present;
- Day 45 CSS and JavaScript discoverability;
- branch-service lookup for a receptionist;
- guest walk-in creation;
- immediate WAITING queue state;
- queue confirmation data;
- the guest appearing in branch waiting queue;
- customer role being forbidden from the reception walk-in API.

The existing backend suites remain responsible for deeper branch-isolation, check-in-window and queue-operation rules.

Recommended verification before merge:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day45_reception_workspace
python manage.py test
```

---

## 14. Day 45 trade-offs

### No auto-refresh polling yet

The branch queue has an explicit Refresh button and refreshes after successful mutations. Constant polling is deferred until the broader Day 50 integration audit determines the appropriate update strategy.

Reason: frontend v1 should not introduce unnecessary network traffic or a second pseudo-real-time mechanism before the real-time strategy is chosen.

### Search instead of a giant daily appointment table

Reception starts from lookup rather than loading every appointment for the day.

Reason: the backend already provides targeted branch search, and the receptionist's repeated task is identifying the person in front of them quickly.

### No receptionist analytics

Queue counts on this page are immediate operational counts only.

Reason: manager analytics belong to Day 47 and would distract from the receptionist's task while widening the role surface unnecessarily.

---

## 15. Day 45 outcome

The receptionist role now has a real frontend workspace rather than a placeholder shell.

A receptionist can:

```text
restore their branch-scoped session
search a customer or booking
inspect appointment and queue state
perform staff-assisted check-in
confirm the customer entered WAITING
see the current branch waiting queue
create a guest walk-in without an account
receive the backend-generated queue number and type
handle clear validation/conflict states
```

The main architectural rule remains intact:

```text
Frontend presents and orchestrates.
Backend authorizes, validates and decides.
```

That boundary is especially important for reception because this role touches customer identity, queue activation and priority-sensitive inputs at high operational speed.
