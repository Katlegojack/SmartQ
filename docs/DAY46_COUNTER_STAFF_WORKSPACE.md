# Smart Q - Day 46 Full Engineering Documentation

## Counter Staff Workspace

**Status:** Complete, merged into `main`, verified  
**Feature branch:** `feature/day46-counter-staff-workspace`  
**Pull Request:** #39 - Build Day 46 counter staff workspace  
**Feature head:** `9a327476fa24e17e21790173cab2306d2a759720`  
**Merge commit:** `6ea8646e1459a5d221385c1b9486da888939d5de`  
**Post-merge CI:** Django Tests run 212 - success  
**README closeout:** PR #40 - merged  

> **Day 46 architectural rule:** Counter Staff operate an assigned counter. The backend owns assignment, queue allocation, fairness and valid state transitions.

---

# Executive Summary

Day 46 transformed the Counter Staff role from a generic role shell into a real serving workspace. The page restores the authenticated staff member's assigned counter, mirrors the counter lifecycle, shows the current customer, exposes backend-authoritative Call Next / Complete / No-show actions and provides a read-only waiting preview for the counter's queue type.

The key design decision was to keep allocation authority out of the browser. Counter Staff cannot choose a branch, self-assign a counter, change queue type, click a waiting row to bypass order, or force a lifecycle transition the backend rejects. The frontend presents the operational state machine while the server remains the source of truth.

Day 46 was protected by a dedicated APITestCase suite, the full Smart Q regression suite, feature-branch and pull-request GitHub Actions, and a successful post-merge `main` run. The milestone is therefore documented from the verified final state rather than from an untested implementation snapshot.

---

# Part 1 - Day 46 Context, Scope and Objectives

## 1. Introduction

Day 46 is the point where the frontend moves from customer intake and reception activation into the actual service-delivery loop.

Before Day 46, Smart Q already had backend support for:

- counter assignment;
- counter lifecycle states;
- waiting tickets;
- General/Priority queue types;
- Call Next;
- current serving ticket;
- Complete;
- No-show;
- counter ownership permissions.

The missing piece was a dedicated Counter Staff interface.

The repeated workflow is:

```text
ASSIGNED COUNTER
      |
      v
CLOSED --open--> OPEN
                  |
                  +--> CALL NEXT --> SERVING
                  |                   |
                  |                   +--> COMPLETE
                  |                   +--> NO_SHOW
                  |
                  +--> PAUSE --> PAUSED --resume--> OPEN
                  |
                  +--> CLOSE (only when free)
```

## 2. Position in the Frontend Roadmap

```text
Day 41  Shared frontend design system
Day 42  Authentication + role-aware shell
Day 43  Customer Dashboard
Day 44  Booking + availability + rescheduling
Day 45  Receptionist Workspace
Day 46  Counter Staff Workspace
Day 47  Branch Manager Workspace
Day 48  System Admin Workspace
Day 49  History/reporting/disruption UX
Day 50  Full integration + release audit
```

## 3. Objectives

Day 46 had to:

- replace `/app/counter/` with a dedicated Counter Staff page;
- restore the authenticated staff member's assigned counter;
- represent `CLOSED`, `OPEN` and `PAUSED` clearly;
- expose Open, Pause, Resume and Close lifecycle actions;
- show the current `SERVING` customer;
- expose server-authoritative Call Next, Complete and No-show;
- show a read-only waiting preview for the counter queue type;
- handle no-assignment, free-counter, empty-queue and conflict states;
- add focused tests and CI coverage;
- keep Reception, Manager and Admin features outside this role surface.

## 4. Acceptance Criteria

Day 46 is complete only if a Counter Staff user can:

1. authenticate;
2. restore the assigned counter;
3. open the counter;
4. call the next eligible customer chosen by the backend;
5. read the current serving ticket;
6. complete or no-show that customer;
7. return to a free counter state;
8. remain blocked from operating another staff member's counter.

## 5. Role Boundary

Counter Staff are service executors, not branch coordinators.

```text
Receptionist    -> identify/check in customers, create walk-ins
Counter Staff   -> serve customers at assigned counter
Branch Manager  -> observe branch + staff counters
System Admin    -> configure platform-wide resources
```

### Engineering lesson

A role workspace should expose the repeated job, not every API the role can technically reach.

---

# Part 2 - Counter Domain Architecture and Backend Contracts

## 6. Assignment Is an Authorization Boundary

Counter Staff do not choose a counter from a dropdown.

```http
GET /api/v1/counters/my/
```

The endpoint answers a permission question:

```text
200 -> this is the counter you may operate
404 -> you are not currently assigned to a counter
```

The Day 46 frontend translates the 404 into an explicit state telling the user a Branch Manager must assign a counter.

### Engineering lesson

Operational assignment is identity/authorization data, not ordinary form input.

## 7. Counter Lifecycle

The backend counter states are:

```text
CLOSED
OPEN
PAUSED
```

The frontend mirrors those states but does not replace backend validation.

### CLOSED

- Open is available.
- Call Next is disabled.

### OPEN and free

- Call Next is available.
- Pause is available.
- Close is available.

### OPEN and serving

- Complete / No-show are available.
- Pause is available.
- Close is blocked.
- Call Next is blocked.

### PAUSED and free

- Resume is available.
- Close is available.
- Call Next is blocked.

### PAUSED and serving

- The current customer may still be resolved.
- No new customer may be called.

### Engineering lesson

Operational interfaces become easier to reason about when they mirror a state machine instead of exposing every endpoint simultaneously.

## 8. Backend Contracts Reused

```http
GET  /api/v1/accounts/me/
GET  /api/v1/counters/my/
POST /api/v1/counters/<counter_id>/open/
POST /api/v1/counters/<counter_id>/pause/
POST /api/v1/counters/<counter_id>/resume/
POST /api/v1/counters/<counter_id>/close/

GET  /api/v1/queues/branches/<branch_id>/waiting/?queue_type=<type>
GET  /api/v1/queues/counters/<counter_id>/current/
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Day 46 did not create a second queue-selection or lifecycle engine in JavaScript.

## 9. Queue Type Is a Counter Property

Each counter has a backend-owned queue type:

```text
GENERAL
or
PRIORITY
```

The Day 46 page displays the value and uses it for the waiting preview. Counter Staff cannot alter it.

The backend Call Next service also uses the counter's stored queue type, so allocation does not depend on a browser-selected customer.

## 10. Call Next Is an Allocation Operation

The waiting table is informational.

Clicking Call Next sends only:

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
```

The backend chooses the next eligible ticket using authoritative queue rules.

The staff member does **not** click a waiting row to choose who is served.

### Engineering lesson

Queue visibility and queue-allocation authority are different responsibilities.

## 11. Current Customer Contract

```http
GET /api/v1/queues/counters/<counter_id>/current/
```

Possible results:

```text
200 -> SERVING ticket exists
404 -> counter is free
```

A 404 from this endpoint is therefore a normal operational state rather than a page failure.

The current-customer card shows:

- queue number;
- customer name;
- service;
- queue type;
- appointment date/time;
- check-in time.

## 12. Complete Service

```http
POST /api/v1/queues/counters/<counter_id>/complete/
```

Authoritative transition:

```text
QueueTicket: SERVING -> COMPLETED
Booking:     -> COMPLETED
assigned_counter -> cleared
QueueEvent:  COMPLETED
```

The frontend then refreshes server state rather than trying to reproduce every related database update itself.

## 13. No-Show

```http
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Authoritative transition:

```text
QueueTicket: SERVING -> NO_SHOW
Booking:     -> NO_SHOW
assigned_counter -> cleared
QueueEvent:  NO_SHOW
```

This remains distinct from an appointment that never checked in and later becomes `CANCELLED`.

## 14. Pause Semantics

`PAUSED` stops new work from being called. It does not erase a customer already being served.

That means:

```text
PAUSED + current customer
    -> Complete allowed
    -> No-show allowed
    -> Call Next blocked
```

### Engineering lesson

Interruption states often block new work while allowing in-flight work to reach a safe terminal state.

---

# Part 3 - Frontend Workspace Implementation

## 15. Dedicated Route

`/app/counter/` now renders:

```text
templates/frontend/counter_workspace.html
```

instead of the generic Day 42 shell.

The template declares:

```html
data-expected-role="counter_staff"
```

and loads:

```text
static/css/counter-workspace.css
static/js/pages/counter-workspace.js
```

## 16. Workspace Information Architecture

The page is organized around four areas:

```text
Serve customer
Waiting queue
Counter controls
Security
```

It deliberately excludes:

- receptionist search;
- guest walk-in creation;
- manager analytics;
- System Admin configuration.

## 17. Bootstrap Flow

The page first restores the authenticated account.

```javascript
account = await getCurrentAccount();

if (!account) {
    // redirect to login
}

if (account.role !== "counter_staff") {
    // redirect to real role workspace
}
```

It then loads the assigned counter:

```javascript
counter = await apiRequest("/api/v1/counters/my/");
```

A no-assignment 404 becomes a dedicated UI state instead of a branch/counter selector.

## 18. State-Driven Lifecycle Controls

The frontend renders actions from the current server state.

```text
CLOSED:
  Open

OPEN + free:
  Call Next
  Pause
  Close

OPEN + serving:
  Complete / No-show
  Pause

PAUSED + free:
  Resume
  Close

PAUSED + serving:
  Complete / No-show
  Resume
```

The backend still validates every request independently.

## 19. Current-Customer Card

When a serving ticket exists, the customer card becomes the dominant content.

Primary actions:

```text
Complete service
Mark no-show
```

The page does not expose arbitrary booking status changes.

## 20. Free-Counter State

When the current-ticket endpoint returns 404, the page shows the next meaningful instruction:

- open the counter;
- resume the counter;
- call the next eligible customer.

## 21. Waiting Preview

The page requests the assigned branch waiting queue with the counter queue type.

It displays:

```text
waiting count
first visible queue number
counter queue type
queue number
customer
service
check-in time
status
```

The table is read-only.

## 22. Safe DOM Rendering

Customer/API values are written as text nodes / `textContent` rather than being concatenated into executable HTML.

### Engineering lesson

Customer-controlled strings should be treated as data, not markup.

## 23. Refresh-After-Write

After lifecycle or queue mutations, Day 46 refreshes:

```text
assigned counter
current ticket
waiting preview
```

This is safer than manually updating several related client-side objects and hoping they match what the backend persisted.

## 24. Stale Refresh Protection

Day 46 uses a refresh sequence counter:

```javascript
const sequence = ++refreshSequence;

await Promise.all([...]);

if (sequence !== refreshSequence) {
    return;
}
```

Older network responses cannot overwrite newer workspace state.

## 25. In-Flight Button Protection

Buttons are disabled while mutations are running and are temporarily relabelled.

This reduces duplicate clicks but is not treated as the data-integrity guarantee.

### Engineering lesson

Frontend safeguards improve usability. Backend transactions and validation protect correctness.

## 26. Error and Empty States

The workspace explicitly handles:

- unauthenticated session;
- wrong role;
- no counter assignment;
- no current ticket;
- no matching waiting customers;
- paused counter;
- closed counter;
- conflict responses;
- failed reads;
- failed lifecycle writes;
- failed Call Next;
- failed Complete / No-show.

## 27. Responsive Layout

The workspace continues the Day 41 design system and prioritizes compact operational clarity rather than decorative dashboard density.

---

# Part 4 - Security, Fairness and Data Integrity

## 28. No Self-Assignment

Counter Staff cannot choose a counter.

Branch Managers own counter staffing.

## 29. No Cross-Counter Operation

A Counter Staff user cannot operate another staff member's counter even when both users belong to the same branch.

This is enforced by the API, not only hidden in the UI.

## 30. No Manual Queue Allocation

The waiting table contains no `Serve` or `Select` action.

Allowing staff to pick a row would turn a read-only queue view into a fairness override.

## 31. No Client-Controlled Queue Type

Queue type comes from the counter model. The browser may display it but does not control it.

## 32. No Client-Controlled Branch Scope

The branch comes from the assigned counter. Counter Staff are not offered a branch selector.

## 33. Write-Then-Read Consistency

A successful mutation is followed by authoritative reads.

This matters because one action can affect:

```text
Counter
QueueTicket
Booking
QueueEvent
```

## 34. Frontend Concurrency vs Backend Integrity

Sequence counters and disabled buttons reduce accidental races, but the backend remains the real concurrency and integrity boundary.

## 35. Status Meaning Is Preserved

Day 46 keeps domain semantics consistent:

```text
unchecked expiry -> CANCELLED
checked in + called + absent -> NO_SHOW
served successfully -> COMPLETED
```

---

# Part 5 - Automated Testing, CI and Verification

## 36. Focused Test Module

```text
smartq/test_day46_counter_workspace.py
```

The fixture builds:

- a branch;
- a service;
- two Counter Staff users;
- a customer;
- an assigned counter;
- waiting tickets as required by each test.

## 37. Route Test

The dedicated route test verifies:

```text
Counter staff workspace
data-counter-workspace
data-call-next
data-complete-current
data-no-show-current
data-counter-action="pause"
```

It also verifies that manager/admin language is not rendered.

## 38. Static Asset Test

Django staticfiles must discover:

```text
css/counter-workspace.css
js/pages/counter-workspace.js
```

## 39. No-Assignment Test

Removing the assignment must cause:

```http
GET /api/v1/counters/my/
-> 404
```

with the explicit assignment message.

## 40. Open -> Call -> Complete Integration

The focused test proves:

```text
Open counter
    -> 200

Call Next
    -> WAITING ticket becomes SERVING
    -> assigned_counter set

GET current
    -> same ticket

Complete
    -> COMPLETED
    -> assigned_counter cleared

GET current
    -> 404 (counter free)
```

## 41. Paused Counter Test

With a paused counter and an existing serving ticket:

```text
Call Next -> 409 Conflict
No-show   -> 200 OK
```

This protects the in-flight-work semantics.

## 42. Queue-Type Allocation Test

The test creates General and Priority waiting tickets and configures the assigned counter as Priority.

Call Next must select the Priority ticket while leaving the General ticket waiting.

## 43. Cross-Staff Isolation Test

A second Counter Staff user attempts to Call Next using the first staff member's counter.

Expected result:

```http
403 Forbidden
```

## 44. CI Integration

The workflow contains an explicit Day 46 step:

```yaml
- name: Run Day 46 counter staff workspace tests
  run: python manage.py test smartq.test_day46_counter_workspace

- name: Run full test suite
  run: python manage.py test
```

## 45. Verified CI State

```text
Feature branch push: Django Tests run 210 - success
Pull request:        Django Tests run 211 - success
PR head:             9a327476fa24e17e21790173cab2306d2a759720
Merge commit:        6ea8646e1459a5d221385c1b9486da888939d5de
Post-merge main:     Django Tests run 212 - success
```

PR #39 merged only after the focused Day 46 test and complete Smart Q regression suite passed.

## 46. README Closeout

After the Day 46 implementation merge, README still described Day 46 as being at the verification gate.

A documentation-only PR #40 corrected the final project state and marked Day 47 as next. That PR also passed CI before merging.

### Engineering lesson

A milestone is not fully closed until code, tests, permanent documentation and project-status documentation all agree.

## 47. Recommended Local Verification

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test smartq.test_day46_counter_workspace
python manage.py test
```

---

# Part 6 - Engineering Trade-Offs and Design Decisions

## 48. No Manual Customer Selection

A clickable queue row could feel convenient but would allow staff to bypass queue allocation policy.

Decision:

```text
waiting table = information
Call Next     = allocation
```

## 49. No Counter Self-Assignment

This may require a Branch Manager to fix a missing assignment, but it preserves accountability and the Day 33 staffing boundary.

## 50. No Manager Analytics

Counter Staff need current operational context, not branch-wide performance analysis.

That belongs to Day 47.

## 51. No Automatic Polling Yet

Day 46 uses explicit refresh and refresh-after-write instead of introducing a temporary real-time architecture.

This avoids continuous traffic and prevents a throw-away polling design before the final integration phase.

## 52. No Frontend Lifecycle Engine

The UI hides or disables clearly invalid actions for usability, but lifecycle validity remains backend-owned.

## 53. No Mid-Roadmap Framework Rewrite

Day 46 continued Django templates + vanilla JavaScript ES modules.

A new framework could simplify some client state management, but introducing it mid-roadmap would add migration risk and duplicate the frontend foundation during a deadline-driven integration phase.

---

# Part 7 - Engineering Lessons Learned

## 54. State Machines Make Operational UIs Clearer

Counter service is naturally represented by explicit states and transitions. This makes both implementation and debugging easier.

## 55. Identity and Assignment Are Different From Input

A counter assignment is permission data, not a user preference.

## 56. Visibility Does Not Imply Control

The operator may see waiting customers without receiving the authority to choose who is next.

## 57. Fairness Decisions Belong on the Backend

Queue type, ticket order and eligibility should be centrally enforced and independently testable.

## 58. Expected 404s Can Represent Valid Domain State

`no current ticket` and `no assigned counter` are meaningful operational states.

Good frontend code translates transport responses into domain language.

## 59. Frontend Safeguards Are Not Integrity Guarantees

Disabled buttons and freshness counters reduce mistakes. Backend validation and transactions remain the real protection.

## 60. Re-Read Authoritative State After Compound Writes

Complete and No-show affect multiple related models. Refreshing backend reads avoids incomplete local simulation.

## 61. Role Separation Improves Usability and Security

```text
Counter Staff -> serve
Reception     -> identify/activate
Manager       -> coordinate
Admin         -> configure
```

Narrow role surfaces reduce cognitive load and accidental privilege expansion.

## 62. Status Names Are Shared Contracts

`CANCELLED`, `WAITING`, `SERVING`, `COMPLETED` and `NO_SHOW` must carry the same meaning in frontend, backend, reports and documentation.

## 63. CI Should Name New Milestones Explicitly

A named Day 46 CI step keeps the role workflow visible and prevents it from disappearing inside only a large full-suite result.

---

# Part 8 - Final State and Day 47 Handoff

## 64. Files Added or Changed

```text
templates/frontend/counter_workspace.html
static/css/counter-workspace.css
static/js/pages/counter-workspace.js
smartq/urls.py
smartq/test_day46_counter_workspace.py
.github/workflows/django-tests.yml
docs/DAY46_COUNTER_STAFF_WORKSPACE.md
README.md
```

## 65. End-to-End Counter Staff Workflow

```text
COUNTER STAFF LOGIN
        |
        v
Restore role
        |
        v
GET assigned counter
        |
        +--> none -> manager assignment required
        |
        v
Render counter state
        |
        +--> CLOSED -> OPEN
        +--> PAUSED -> RESUME / CLOSE when free
        +--> OPEN + free -> CALL NEXT
        |
        v
Backend selects matching WAITING customer
        |
        v
SERVING
   |            |
   v            v
COMPLETE      NO_SHOW
   |            |
   +------v-----+
          |
          v
Counter free
          |
          v
Refresh authoritative state
          |
          v
CALL NEXT
```

## 66. What Day 46 Deliberately Did Not Add

- receptionist customer/booking search;
- guest walk-in creation;
- branch-level analytics;
- historical reporting UI;
- System Admin configuration;
- manual queue reordering;
- manual queue-type changes;
- counter self-assignment;
- a temporary WebSocket/polling architecture.

## 67. Day 47 Handoff

Day 47 moves from individual service execution to branch coordination.

```text
Day 46
Counter Staff -> serve assigned work

Day 47
Branch Manager -> observe branch demand + coordinate counter staffing
```

The Day 46 rule carries forward: frontend screens present role-appropriate operations while backend permissions and domain services remain authoritative.

## 68. Final Outcome

Day 46 is complete, merged and verified.

Smart Q now has a real Counter Staff serving workspace instead of a generic shell. Counter Staff can operate only their assigned counter, follow the approved lifecycle, call the next eligible customer, resolve service as Complete or No-show, and see the matching waiting queue without receiving authority to reorder or reclassify customers.

The milestone preserves Smart Q's central architecture:

> **Frontend = task-focused operator surface. Backend = authorization, fairness, allocation and state integrity.**
