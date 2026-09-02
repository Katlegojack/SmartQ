# Smart Q - Day 45 Full Engineering Documentation

## Receptionist Workspace

**Status:** Complete, merged into `main`, and verified by GitHub Actions  
**Pull Request:** #35 - Build Day 45 receptionist workspace  
**Merge Commit:** `7cfe9f9e4eac979fd14d56dc88f608a9217d6f56`  
**Final CI:** Django Tests run 195 - success

---

# Part 1 - Day 45 Context, Scope and Objectives

Day 45 transformed the receptionist role from a generic application shell into a real branch-operational workspace. The aim was not to place every queue-management capability on one screen. The aim was to give reception staff the smallest complete toolset needed to identify a customer, inspect a booking, activate a valid booking into the live queue, create a guest walk-in and confirm the branch queue state.

## 1. Introduction

Before Day 45, Smart Q already had the backend queue and booking foundations, the shared frontend design system, session restoration, role routing, the customer dashboard and the customer booking/check-in experience. The receptionist route still rendered a generic Day 42 role shell. Day 45 replaced that placeholder with a dedicated operational workspace.

Reception work is interruption-heavy and speed-sensitive. The workspace therefore revolves around four repeated questions:

1. Who is the person at the desk?
2. Do they have a booking?
3. Can the booking enter the live queue now?
4. If they have no account or booking, can reception create a walk-in ticket?

## 2. Position in the Frontend Roadmap

- Day 41 - design system and shared visual language.
- Day 42 - authentication, session restoration, role routing and shared shell.
- Day 43 - customer dashboard.
- Day 44 - appointment booking, rescheduling and check-in experience.
- Day 45 - receptionist operational workspace.
- Day 46 - counter staff serving workspace.
- Day 47 - branch manager dashboard.
- Day 48 - system administrator control plane.
- Day 49 - history, reporting, disruption and rescheduling UX.
- Day 50 - full integration, responsive and release audit.

## 3. Objectives

- Replace `/app/reception/` with a dedicated receptionist page.
- Add branch-scoped customer and booking search.
- Add staff-assisted check-in using the existing backend rules.
- Show the branch waiting queue for operational confirmation.
- Allow guest walk-in creation without a customer account.
- Load only services offered by the assigned branch.
- Keep branch authority, check-in eligibility, queue priority and queue numbering backend-owned.
- Add explicit loading, empty, error, conflict and success states.
- Add focused tests and CI coverage.
- Preserve strict separation from manager and administrator functionality.

## 4. Acceptance Criteria

A completed Day 45 implementation must allow a receptionist to sign in, restore their assigned branch, search a customer or booking, perform a valid staff-assisted check-in, create a guest walk-in, receive the backend-generated queue number and queue type, and confirm the customer appears in the waiting queue. A normal customer must not be able to use the receptionist write APIs.

## 5. Core Architecture Rule

> Frontend presents and orchestrates. Backend authorizes, validates and decides.

This rule is especially important at reception because the UI touches customer identity, queue activation and priority-sensitive inputs. The browser must not become a second business-logic server.

### Engineering lessons

- Values that affect authority, fairness or allocation belong on the server.
- A fast UI should reduce operator effort without weakening the permission model.

---

# Part 2 - Receptionist Role Architecture and API Contracts

## 6. Responsibility Boundary

Reception is an operational role, not a management role. Its responsibilities are customer identification, booking lookup, assisted check-in, guest intake and queue confirmation. The workspace intentionally excludes branch analytics, staff administration and system configuration.

This improves both usability and security: the operator sees the tools required for the repeated job and no wider control surface.

## 7. Branch Scope Comes From Identity

The receptionist does not select a branch from a dropdown. Branch scope is restored from:

```http
GET /api/v1/accounts/me/
```

Relevant account fields include:

```text
role
branch_id
branch_name
```

The receptionist profile is therefore the source of truth for branch authority.

### Engineering lesson

Security scope is identity data, not ordinary form input. If the server already knows the authenticated staff member's branch, the client should not be allowed to invent it.

## 8. Existing Backend Contracts Reused

```http
GET  /api/v1/accounts/me/
GET  /api/v1/bookings/reception/search/?q=<query>
POST /api/v1/bookings/<booking_id>/staff-check-in/
POST /api/v1/bookings/reception/walk-ins/
GET  /api/v1/queues/branches/<branch_id>/waiting/
GET  /api/v1/services/branches/<branch_id>/
```

Day 45 did not create a new queue algorithm or duplicate existing booking rules in JavaScript.

## 9. High-Level Data Flow

```text
Receptionist signs in
        |
        v
GET /api/v1/accounts/me/
        | role + branch
        v
Dedicated Reception Workspace
        |
        +--> Search customer / booking
        |       |
        |       +--> Staff-assisted check-in
        |
        +--> Read branch waiting queue
        |
        +--> Load branch services
                |
                +--> Create guest walk-in
                        |
                        v
               Backend creates WAITING ticket
```

## 10. Why Existing Backend Rules Were Reused

Queue numbering, check-in windows, priority policy and branch authorization already existed on the backend. Reimplementing them in the browser would create two sources of truth. Day 45 therefore treats the frontend as an orchestration layer over proven backend contracts.

### Engineering lesson

When a rule changes, one authoritative implementation is safer than synchronizing copies across multiple clients.

---

# Part 3 - Frontend Implementation

## 11. Dedicated Reception Route

`/app/reception/` now renders:

```text
templates/frontend/reception_workspace.html
```

instead of the generic application shell. Other role routes were left unchanged.

The template declares:

```html
data-expected-role="receptionist"
```

so the shared session shell and the Day 45 page logic agree on the required role.

## 12. Workspace Information Architecture

The receptionist page contains four operational areas:

- **Reception desk** - customer/booking search and assisted check-in.
- **Branch queue** - current waiting queue and immediate counts.
- **Guest walk-in** - minimal walk-in intake and queue confirmation.
- **Security** - shared password and logout controls.

It deliberately contains no manager analytics or administrator settings.

## 13. Search-First Design

Search is the dominant first interaction because reception normally starts with one person standing at the desk. The input accepts identifiers already supported by the backend search endpoint, including booking ID, username, customer name, email, guest name and guest phone number.

The field is focused when the workspace boots. `Ctrl+K` or `Cmd+K` returns focus to search. Queries shorter than two characters are rejected before the API request.

### Engineering lesson

Operational screens should optimize the repeated task, not maximize the number of widgets visible at once.

## 14. Stale Search Response Protection

The page uses a request sequence counter:

```javascript
const sequence = ++searchRequestSequence;
const bookings = await apiRequest(searchUrl);
if (sequence !== searchRequestSequence) return;
renderSearchResults(bookings);
```

If an earlier network request returns after a newer search has started, the stale response is ignored.

### Engineering lesson

Frontend concurrency problems can happen even without threads. Network responses can arrive out of order, so asynchronous UI state sometimes needs a freshness guard.

## 15. Search Result Rendering

Results display:

```text
Customer
Appointment date/time
Service + branch
Booking ID + booking status
Queue number + queue type/status
Available action
```

Customer and API-derived display values are assigned with `textContent`. Static HTML is used only for known markup containers.

### Engineering lesson

Treat customer-controlled display values as untrusted text. Do not turn names, emails or phone values into executable HTML.

## 16. Check-In Button Presentation Logic

The UI only performs a light presentation check before showing the button:

```javascript
function canCheckIn(booking) {
    const finalStates = new Set([
        "cancelled", "completed", "no_show"
    ]);
    return !booking.is_checked_in
        && !finalStates.has(booking.status);
}
```

This does not replace backend validation. It only avoids presenting an obviously invalid action.

## 17. Staff-Assisted Check-In

The write is sent to:

```http
POST /api/v1/bookings/<id>/staff-check-in/
```

The backend still decides whether:

- the six-hour check-in window is open;
- the booking expired;
- the booking is already checked in;
- the booking is in a final state;
- the staff member is authorized for the branch.

The button is disabled while the request is in flight. If the backend provides `check_in_opens_at`, the error is formatted for reception. On success the page refreshes the current search result and waiting queue from the backend.

### Engineering lessons

- Disabling a button reduces duplicate clicks; it is not a substitute for backend integrity.
- After a write, read the authoritative state again instead of manually guessing what the server persisted.

## 18. Branch Queue Visibility

The page reads:

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
```

and displays queue number, customer, service, check-in time, queue type and status. It also calculates immediate counts for Waiting, Priority and General tickets.

These counts are operational confirmation only. They are not manager analytics.

## 19. Queue Refresh Strategy

The queue refreshes after successful check-in or walk-in creation and also provides an explicit **Refresh queue** button.

Constant polling was deliberately deferred until Smart Q chooses its wider real-time strategy. This avoids introducing continuous network traffic and a temporary pseudo-real-time architecture during the role-by-role frontend build.

## 20. Guest Walk-In Form

The form captures only the backend-supported operational fields:

```text
full_name
phone_number (optional)
date_of_birth
gender
service
disability_status
is_pregnant
```

Pregnancy is shown only when gender is female. The frontend still relies on backend validation for the final rule.

## 21. Walk-In Payload

The browser sends customer facts and the selected service:

```javascript
const payload = {
    full_name,
    phone_number,
    date_of_birth,
    gender,
    disability_status,
    is_pregnant,
    service
};
```

It does **not** send:

```text
branch_id
queue_type
queue_number
```

The backend derives branch authority from the receptionist profile, calculates priority and creates the queue number.

## 22. Branch Service Loading

The service selector is populated from:

```http
GET /api/v1/services/branches/<branch_id>/
```

This prevents the UI from offering services that are not active at the receptionist's branch. If no active services exist, the selector is disabled and communicates that state.

## 23. Walk-In Confirmation

On success the backend returns the created booking and queue ticket. The confirmation panel displays:

```text
queue number
customer
service
queue type
status
```

The browser displays these returned values instead of predicting them.

## 24. Operational Usability

Day 45 includes:

- search autofocus;
- `Ctrl+K` / `Cmd+K` search focus shortcut;
- in-flight button states such as `Checking in...` and `Creating ticket...`;
- a reset/new-walk-in flow that returns focus to full name;
- responsive layouts for narrower screens.

## 25. Loading, Empty, Error and Success States

The page explicitly handles:

- initial ready state;
- search loading;
- no search results;
- search/API errors;
- queue loading;
- empty waiting queue;
- service loading failure;
- walk-in validation errors;
- check-in conflicts;
- successful check-in;
- successful walk-in and queue confirmation.

### Engineering lesson

Error handling is part of workflow design, not decoration added after the happy path works.

---

# Part 4 - Backend Business Rules Preserved by the Frontend

## 26. Meaning of Check-In

Smart Q keeps the Day 31 domain meaning:

```text
SCHEDULED --valid check-in--> WAITING
```

Check-in means activation into the live queue. It does not claim that Smart Q independently proved physical presence.

The status distinction remains:

```text
Expired before check-in -> CANCELLED
Checked in but absent when called -> NO_SHOW
```

### Engineering lesson

Status names are domain contracts. Frontend, backend and reporting must give them the same meaning.

## 27. Check-In Window

The six-hour check-in window remains backend-owned. Reception can display an error and opening time, but it cannot bypass the server rule.

## 28. Walk-In State

A reception-created guest walk-in is immediately checked in and enters the live queue as `WAITING`. No customer account is required.

This differs from an advance appointment, which begins as scheduled and joins the live queue only after valid check-in.

## 29. Priority Calculation

Reception never chooses General or Priority. The backend applies the existing Smart Q priority policy using the factual inputs collected by the form, including age, disability and pregnancy conditions.

### Engineering lesson

Fairness decisions should be rule-driven and centrally enforced rather than delegated to an operator dropdown.

## 30. Queue Number Generation

Queue numbers are generated on the server. The browser never guesses, increments or composes queue numbers locally. This prevents collisions and keeps the numbering contract consistent across customer, reception and counter workflows.

## 31. Booking Search Scope

The reception search endpoint is branch-scoped through authenticated staff identity. Reception can search useful identifiers without exposing unrelated branch data.

---

# Part 5 - Security, Data Integrity and Failure Prevention

## 32. Role Enforcement

The page calls `getCurrentAccount()` during boot. Unauthenticated users are redirected to login. Authenticated users with a different role are redirected to the workspace for their real backend role.

```javascript
if (!account) {
    redirectToLogin();
}
if (account.role !== "receptionist") {
    window.location.replace(routeForRole(account.role));
}
```

Backend permissions remain authoritative, so UI routing is not the only security layer.

## 33. Missing Branch Protection

A receptionist without `branch_id` is treated as a configuration error. The workspace fails visibly rather than silently operating with ambiguous scope.

## 34. No Client-Side Authority Expansion

Day 45 deliberately has:

- no branch selector;
- no `branch_id` in the walk-in payload;
- no queue-type selector;
- no queue-number input;
- no client-side override of check-in time rules;
- no manager or administrator control surface.

## 35. Write-Then-Read Consistency

After queue-changing operations, the frontend refreshes the relevant backend reads. The user therefore sees what the server actually persisted, not a locally invented state transition.

## 36. Concurrency Safeguards

Sequence counters protect search and queue reads from stale asynchronous responses. Mutating buttons are disabled while requests are in flight. These improve frontend behaviour but do not replace transactional backend rules.

---

# Part 6 - Automated Testing, CI and Verification

## 37. Day 45 Test Module

The new test module is:

```text
smartq/test_day45_reception_workspace.py
```

The fixture creates a branch, service, branch-service relationship and receptionist account so the tests exercise the real role and branch contracts.

## 38. Dedicated Route Test

The test verifies that `/app/reception/` renders the dedicated workspace and required hooks:

```python
self.assertContains(response, "Reception desk")
self.assertContains(response, "data-reception-workspace")
self.assertContains(response, "data-search-form")
self.assertContains(response, "data-queue-refresh")
self.assertContains(response, "data-walkin-form")
self.assertNotContains(response, "Manager analytics")
self.assertNotContains(response, "System administration")
```

## 39. Static Asset Discovery

The test suite verifies Django staticfiles can find:

```text
css/reception-workspace.css
js/pages/reception-workspace.js
```

This catches template/static integration mistakes before deployment.

## 40. Branch Service Integration

An authenticated receptionist can load the services offered by the assigned branch. This verifies the walk-in service selector has a working backend source.

## 41. Guest Walk-In Integration

The test creates a guest walk-in and verifies:

- HTTP 201;
- the backend-selected branch matches the receptionist branch;
- `source == walk_in`;
- `is_checked_in == true`;
- queue ticket status is `waiting`;
- a queue number was generated;
- the guest appears in the branch waiting queue.

## 42. Authorization Regression Test

A normal customer attempts to use the receptionist walk-in endpoint and receives HTTP 403 Forbidden. This proves the restriction is enforced by the API rather than only hidden in the UI.

## 43. CI Pipeline Update

The Django workflow now contains a named Day 45 step:

```yaml
- name: Run Day 45 reception workspace tests
  run: python manage.py test smartq.test_day45_reception_workspace

- name: Run full test suite
  run: python manage.py test
```

## 44. Final Verification Result

The Day 45 feature-branch push workflow succeeded. The pull-request workflow succeeded. PR #35 was merged. The post-merge `main` workflow also completed successfully.

```text
Merge commit:
7cfe9f9e4eac979fd14d56dc88f608a9217d6f56

Final main workflow:
Django Tests run 195 - success
```

Day 45 is therefore verified on the final main-branch state.

## 45. Recommended Local Verification

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day45_reception_workspace
python manage.py test
```

---

# Part 7 - Engineering Trade-Offs and Decisions

## 46. Search Instead of a Giant Daily Table

Reception normally needs to identify one person quickly. Targeted lookup has lower cognitive cost than loading and scanning every appointment. The backend already provides a branch-scoped search contract, so the UI uses it directly.

## 47. No Automatic Polling Yet

Automatic polling would add continuous traffic and a second temporary real-time mechanism. Day 45 uses explicit refresh plus refresh-after-write until the wider real-time strategy is decided.

## 48. No Receptionist Analytics

Immediate waiting/priority/general counts are enough for operational confirmation. Historical branch metrics belong to the manager workspace on Day 47.

## 49. No Branch Selector

A dropdown would be convenient for demonstrations but wrong for branch-scoped operator authority. The authenticated profile already defines the branch.

## 50. No Manual Priority Selector

Allowing an operator to choose Priority would make a fairness decision subjective. The backend already has the required facts and policy, so the server performs the classification.

## 51. Reuse Instead of Rebuild

Existing reception, queue and branch-service APIs were reused instead of adding new endpoints or copying rules into JavaScript. This reduced risk and kept the milestone focused on frontend integration.

## 52. No Mid-Roadmap Framework Rewrite

Day 45 continued the current focused page-module approach instead of introducing a new JavaScript framework. The trade-off is more manual DOM state management, but it avoids destabilising the codebase during a deadline-driven integration phase.

---

# Part 8 - Engineering Lessons, Final State and Day 46 Handoff

## 53. Engineering Lessons Learned

- Design role workspaces around the repeated job, not every database table.
- Keep queue business rules in one authoritative backend layer.
- Derive branch scope from authenticated identity.
- A disabled button is a UX safeguard; backend validation is the integrity guarantee.
- Re-read authoritative state after writes.
- Treat statuses as shared domain contracts.
- Use safe text rendering for user-controlled values.
- Protect UI state from stale asynchronous responses.
- Design loading, empty, error, conflict and success states intentionally.
- Test authorization boundaries as well as successful behaviour.
- Role separation improves usability and security together.
- Keep fairness-related decisions rule-driven and server-owned.

## 54. Files Added or Changed

```text
templates/frontend/reception_workspace.html
static/css/reception-workspace.css
static/js/pages/reception-workspace.js
smartq/urls.py
smartq/test_day45_reception_workspace.py
.github/workflows/django-tests.yml
docs/DAY45_RECEPTION_WORKSPACE.md
```

## 55. End-to-End Receptionist Workflow

```text
REGISTERED / APPOINTMENT CUSTOMER
Receptionist login
        |
        v
Restore role + branch
        |
        v
Search customer / booking
        |
        v
Inspect booking + queue state
        |
        v
Backend validates staff check-in
        |
        v
Booking enters WAITING
        |
        v
Branch queue refresh confirms entry

GUEST WALK-IN
Guest arrives
        |
        v
Capture minimum details
        |
        v
Select branch-offered service
        |
        v
Backend creates walk-in booking
        |
        +--> derives branch from staff identity
        +--> calculates priority
        +--> generates queue number
        +--> sets WAITING
        |
        v
Reception displays queue confirmation
```

## 56. Deliberately Deferred to Later Days

- Counter serving actions such as call next, complete and no-show - Day 46.
- Branch performance analytics and staffing metrics - Day 47.
- System-wide configuration and administration - Day 48.
- Full reporting/history/disruption UX - Day 49.
- Final real-time/responsive/release audit - Day 50.

## 57. Day 46 Handoff

Day 46 should build a different task-focused counter staff surface using the same backend-authority principle.

The repeated counter workflow is:

```text
WAITING QUEUE
      |
      v
CALL NEXT
      |
      v
CURRENT CUSTOMER
      |
      +--> COMPLETE
      |
      +--> NO-SHOW
      |
      v
NEXT CUSTOMER
```

Receptionist search, guest intake, manager analytics and administrator controls should not be copied into the counter workspace unless a genuine counter task requires them.

### Engineering lesson

Different roles can use the same queue data while still needing completely different task-focused interfaces.

## 58. Final Day 45 Outcome

Day 45 is complete, merged and verified. Smart Q now has a functional receptionist workspace instead of a placeholder shell.

Reception can identify branch customers, inspect booking and queue state, perform staff-assisted check-in, create guest walk-ins, confirm backend-generated queue tickets and view the current branch waiting queue while preserving server-owned branch scope, check-in rules, priority and queue numbering.

The codebase is ready to move into Day 46 from a known-good, documented baseline.
