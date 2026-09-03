# Smart Q — Day 47 Branch Manager Workspace

## Status

Day 47 implements the dedicated Branch Manager frontend on top of the existing Day 33 counter lifecycle and Day 34 manager dashboard backend contracts.

The final merge decision is gated by GitHub Actions. This document records the architecture, implementation, security boundaries, trade-offs, tests and engineering lessons for the milestone.

---

# Part 1 — Goal and Starting Point

## 1. Day 47 objective

Day 47 replaces the generic `/app/manager/` role shell with a real branch-operational dashboard.

The manager should be able to answer four questions quickly:

1. What is happening in my branch today or on a selected date?
2. How many customers are scheduled, waiting, serving or resolved?
3. Which services are driving demand?
4. What is the live state and staffing of my counters?

The screen is intentionally a branch operations workspace, not a System Admin control plane.

## 2. Starting backend capabilities

Smart Q already had the required domain foundations:

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD

GET  /api/v1/counters/branches/<branch_id>/
POST /api/v1/counters/<counter_id>/assign/
POST /api/v1/counters/<counter_id>/unassign/
```

The Day 34 dashboard is a composite read model built from authoritative operational tables. Day 33 owns counter assignment and lifecycle rules.

## 3. Day 47 scope

Included:

- dedicated Branch Manager route and template;
- authenticated own-branch restoration;
- daily dashboard date selector;
- branch/customer KPI summary;
- queue lifecycle and General/Priority comparison;
- online/walk-in and check-in summary;
- per-service demand view;
- live counter status and current-customer visibility;
- branch-scoped Counter Staff directory;
- manager assign/unassign workflow for closed/free counters;
- explicit loading/error/empty states;
- Day 47 integration tests and CI step.

Deferred deliberately:

- System Admin staff/account management — Day 48;
- historical QueueEvent reporting UX — Day 49;
- disruption/rescheduling management UX — Day 49;
- final cross-role release audit — Day 50.

---

# Part 2 — Architecture and Data Ownership

## 4. Manager workspace architecture

```text
Branch Manager session
        |
        v
GET /api/v1/accounts/me/
        |
        +--> role = branch_manager
        +--> branch_id = authorised branch
        |
        v
Day 47 Manager Workspace
        |
        +--> GET /dashboard/branches/<branch_id>/?date=...
        |       |
        |       +--> customer activity
        |       +--> queue lifecycle
        |       +--> service demand
        |       +--> live counter state
        |
        +--> GET /counters/branches/<branch_id>/counter-staff/
        |       |
        |       +--> active Counter Staff in own branch only
        |
        +--> POST counter assign/unassign
```

## 5. Why the dashboard remains a read model

Day 47 does not create a `ManagerDashboard` database model.

The displayed metrics already exist as facts in:

```text
Booking
QueueTicket
Counter
Branch
Service
```

Persisting copied totals such as `waiting_customers = 12` would create a synchronization problem: every booking/check-in/call/complete event would also need to update a second dashboard record.

Instead, the backend derives dashboard state from the source-of-truth models.

### Engineering lesson

Derived state should usually be recomputed from authoritative facts unless there is a proven performance need to persist a cache or projection.

## 6. Branch scope is restored from identity

The frontend never presents a branch selector to a Branch Manager.

It calls:

```http
GET /api/v1/accounts/me/
```

and uses the returned `branch_id`.

A manager without a branch is treated as an account-configuration error.

### Engineering lesson

Authority is not a convenience setting. A branch permission should not become editable browser input just because a dropdown would be easy to build.

## 7. Object-level authorization remains authoritative

The dashboard and new staff directory both use `IsBranchManager` and call:

```python
self.check_object_permissions(request, branch)
```

A Branch Manager can therefore access only their assigned branch. A System Admin remains globally authorised at the permission layer, but the Day 47 frontend itself is role-gated specifically to Branch Manager.

---

# Part 3 — The Day 47 Backend Gap and Fix

## 8. The integration gap discovered

Day 33 allowed managers to assign Counter Staff using:

```http
POST /api/v1/counters/<counter_id>/assign/
{
  "staff_user_id": 123
}
```

However, the browser had no manager-safe API from which to obtain valid Counter Staff IDs.

The existing staff list is:

```http
GET /api/v1/accounts/admin/staff/
```

and correctly requires `SYSTEM_ADMIN`.

Weakening that endpoint for Branch Managers would expose a much larger staff-management surface than Day 47 needs.

## 9. Least-privilege solution

Day 47 adds:

```http
GET /api/v1/counters/branches/<branch_id>/counter-staff/
```

The endpoint returns only active users who are:

```text
role = COUNTER_STAFF
branch = requested authorised branch
is_active = true
```

Returned operational fields are intentionally small:

```text
id
username
first_name
last_name
display_name
assigned_counter_id
assigned_counter_number
```

It does not expose password/security fields, account administration, other staff roles or other branches.

### Engineering lesson

When a workflow needs one small slice of a privileged dataset, create a narrow read contract rather than widening access to an administrator endpoint.

## 10. Why the endpoint lives in `counters`

The data exists in user/profile records, but its purpose is counter assignment. Placing the read API in the counter domain keeps the contract aligned with the operation it enables.

This is a pragmatic application-level decision: API ownership can follow workflow responsibility when it avoids coupling a less-privileged role to a broader administration interface.

---

# Part 4 — Frontend Information Architecture

## 11. Dedicated route

`/app/manager/` now renders:

```text
templates/frontend/manager_workspace.html
```

The page declares:

```html
data-manager-workspace
data-expected-role="branch_manager"
```

The shared app-shell session logic and the Day 47 page module therefore agree on the expected role.

## 12. Workspace sections

The page contains:

```text
Branch overview
Queue activity
Service demand
Counters & staffing
Security
```

It deliberately excludes System Admin branch/service/staff configuration.

## 13. Date selector

The manager dashboard supports:

```http
?date=YYYY-MM-DD
```

The page defaults to the browser's current local date and reloads the dashboard when the date changes.

Customer, booking, queue and service metrics use the selected date.

## 14. Important temporal distinction: counters remain live

The Day 34 backend labels counter data:

```text
scope = live_current_state
```

Even when a manager chooses a historical date, the counter section still shows the current counter assignment/status/customer.

The Day 47 UI states this explicitly rather than pretending current counter state is historical data.

### Engineering lesson

A dashboard can combine data with different time semantics, but the interface must label those semantics truthfully.

---

# Part 5 — Operational Overview

## 15. KPI cards

The top of the manager page displays:

- total customers;
- active customers;
- completed tickets;
- checked-in customers.

These values come directly from the Day 34 read model.

## 16. Customer activity definition

The backend defines:

```text
active_customers = waiting + serving
resolved_customers = completed + no_show + cancelled

total_customers = scheduled + active + resolved
```

The frontend does not recalculate a different business definition.

## 17. Branch identity and operating hours

The workspace displays the backend-returned branch name, city, opening time and closing time.

This gives the manager clear scope context while reinforcing that the dashboard belongs to one authorised branch.

---

# Part 6 — Queue Activity

## 18. Combined lifecycle

Day 47 renders the backend lifecycle totals:

```text
Scheduled
Waiting
Serving
Completed
No-show
Cancelled
```

These are domain states, not decorative dashboard labels.

## 19. General vs Priority comparison

The dashboard read model already returns separate statistics for:

```text
general
priority
```

The manager UI displays waiting, serving and completed counts for each.

The manager cannot modify a customer's queue type from this screen.

### Engineering lesson

Visibility into a fairness policy does not imply permission to override the policy.

## 20. Booking source and check-in summary

The screen also displays:

```text
online bookings
walk-ins
not checked in
```

These give operational context without turning Day 47 into a historical reporting suite.

---

# Part 7 — Service Demand

## 21. Service distribution

The backend returns, for each service:

```text
service_id
service_code
service_name
customers
```

The frontend renders a compact demand bar and exact customer count.

The bar is only a visual comparison. The number remains the authoritative readable value.

## 22. No duplicate chart data

The browser does not create a second service-demand dataset. It transforms only the current dashboard response into visual width percentages.

### Engineering lesson

Presentation calculations such as bar width are frontend concerns. Operational totals and business facts remain backend concerns.

---

# Part 8 — Counters and Staffing

## 23. Live counter summary

The manager sees current totals for:

```text
open
busy
free
unstaffed
```

The individual counter table shows:

```text
counter number
queue type
status
assigned staff
current serving customer
staffing action
```

## 24. Manager responsibility vs Counter Staff responsibility

The manager controls assignment.

Counter Staff control their own counter lifecycle and customer-serving actions through the Day 46 workspace.

Day 47 intentionally does not expose `Call Next`, `Complete` or `No-show` to the manager UI even though the backend manager role may possess broader queue-operator permission.

This keeps the interface aligned to the actual repeated managerial job.

### Engineering lesson

Backend permission can be broader than a role-specific screen. Good UX should still expose the smallest useful action set.

## 25. Assignment eligibility

Day 33 rules remain authoritative:

- staff must have the Counter Staff role;
- staff and counter must belong to the same branch;
- one staff member may be assigned to only one counter;
- assignment changes are allowed only while the counter is closed;
- a busy counter cannot change assignment.

Day 47 mirrors these rules in presentation but does not replace server validation.

## 26. Available-staff selector

For an unstaffed closed counter, the UI lists only currently unassigned Counter Staff returned by the branch directory.

The selected ID is posted to:

```http
POST /api/v1/counters/<counter_id>/assign/
```

## 27. Unassign flow

For a staffed closed counter, the manager can call:

```http
POST /api/v1/counters/<counter_id>/unassign/
```

After either mutation, the frontend reloads both the dashboard and Counter Staff directory.

### Engineering lesson

After a write changes relationships used by multiple read models, refresh every authoritative view that depends on that relationship.

## 28. Why assignment is disabled for open/paused/busy counters

The frontend explains that the counter must be closed and free before changing staff.

This reduces invalid clicks, but the backend service remains the integrity boundary and can still return HTTP 409 if state changed concurrently.

---

# Part 9 — Async State and Error Handling

## 29. Parallel dashboard loading

The page loads:

```text
manager dashboard
Counter Staff directory
```

with `Promise.all` because both are required to render the complete counter staffing table.

## 30. Refresh sequence guard

A monotonically increasing sequence number prevents stale dashboard/date responses from overwriting newer state.

This matters when a manager changes dates or refreshes while previous requests are still in flight.

## 31. Write states

Assignment buttons are disabled while their request is running.

Server errors are displayed using the backend's `detail` message where available.

Examples include:

```text
counter_not_closed
counter_busy
staff_already_assigned
wrong_branch
```

The UI does not silently reinterpret these domain conflicts.

---

# Part 10 — Security Boundaries

## 32. Day 47 deliberately does not provide

- a branch selector;
- staff-account creation;
- staff activation/deactivation;
- role changes;
- service configuration;
- branch configuration;
- queue-priority override;
- customer reassignment;
- System Admin settings.

## 33. Frontend role redirect

During bootstrap the page verifies:

```text
account.role == branch_manager
```

A user with another authenticated role is redirected to their correct role workspace.

This is a UX boundary. Backend permissions remain the security boundary.

## 34. Cross-branch protection

Changing a branch ID manually in an API URL does not bypass authorization because the API performs object-level branch checking.

---

# Part 11 — Testing Strategy

## 35. Day 47 focused test module

```text
smartq/test_day47_manager_workspace.py
```

## 36. Dedicated route test

The route test proves `/app/manager/` renders the Day 47 workspace and includes the expected manager hooks while excluding System Admin copy.

## 37. Static asset test

Django staticfiles must discover:

```text
css/manager-workspace.css
js/pages/manager-workspace.js
```

## 38. Dashboard integration test

An authenticated Branch Manager must be able to read the assigned branch dashboard and receive the expected composite sections.

## 39. Staff-directory scope test

The test proves the new directory returns only Counter Staff from the manager's branch.

A Receptionist in the same branch and Counter Staff in another branch must not appear.

## 40. Cross-branch denial test

A Branch Manager requesting another branch's Counter Staff directory must receive HTTP 403.

## 41. Customer denial test

A normal customer attempting to read the manager Counter Staff directory must receive HTTP 403.

## 42. End-to-end staffing integration test

The focused test exercises:

```text
list available staff
        ↓
assign Counter Staff
        ↓
read directory again
        ↓
verify assigned counter
        ↓
read dashboard
        ↓
verify counter assignment in manager read model
        ↓
unassign
```

This is stronger than testing the new directory in isolation because it proves the read and write contracts agree.

## 43. CI integration

The workflow adds:

```yaml
- name: Run Day 47 branch manager workspace tests
  run: python manage.py test smartq.test_day47_manager_workspace
```

The full Smart Q suite still runs afterward.

---

# Part 12 — Trade-Offs

## 44. No manager-side counter serving controls

The backend allows Branch Managers to qualify as queue operators, but Day 47 does not expose Call Next/Complete/No-show.

Reason: those are repeated Counter Staff tasks and already have a dedicated Day 46 interface.

## 45. No System Admin staff endpoint reuse

The broad `/accounts/admin/staff/` API stays System-Admin-only.

Reason: widening it would violate least privilege merely to populate one assignment dropdown.

## 46. No historical operational reporting charts yet

The QueueEvent reporting backend exists, but its full frontend is deferred to Day 49.

Reason: Day 47 should remain a live/daily branch operations dashboard rather than mixing every future management feature into one milestone.

## 47. No disruption controls yet

The Day 35 APIs remain available, but the disruption/reschedule UX is deferred to Day 49 according to the frontend roadmap.

## 48. No automatic polling yet

Day 47 uses explicit refresh and refresh-after-write rather than introducing a new polling architecture before the final integration milestone.

---

# Part 13 — Files Added or Changed

```text
counters/manager_api.py
counters/api_urls.py
templates/frontend/manager_workspace.html
static/css/manager-workspace.css
static/js/pages/manager-workspace.js
smartq/urls.py
smartq/test_day47_manager_workspace.py
.github/workflows/django-tests.yml
docs/DAY47_BRANCH_MANAGER_WORKSPACE.md
README.md                    (final milestone sync before merge)
```

---

# Part 14 — Engineering Lessons

## 49. Read models keep dashboards truthful

A dashboard should aggregate authoritative facts rather than becoming another mutable business-data store.

## 50. Least privilege is also API design

Do not solve a narrow read requirement by exposing a broad administrator endpoint.

## 51. Time semantics must be explicit

Selected-date customer metrics and live current counter state can coexist only if the UI clearly distinguishes them.

## 52. Role screens should represent jobs, not maximum permissions

The fact that a role may technically call an API does not mean every action belongs on that role's primary workspace.

## 53. Integration tests should prove contract agreement

The strongest Day 47 staffing test verifies that the new directory, existing assignment write API and manager dashboard all agree after the same mutation.

## 54. Refresh after relationship-changing writes

Changing `Counter.assigned_staff` affects both the staff directory and dashboard counter read model, so both are re-read from the server.

## 55. Frontend validation reduces friction; backend validation protects truth

Hiding an assignment button for an open counter improves usability. The transaction-safe backend service still owns the actual invariant.

---

# Part 15 — Day 47 End State and Handoff

## 56. End-to-end manager workflow

```text
Branch Manager signs in
        ↓
Smart Q restores authorised branch
        ↓
Manager reviews selected-date branch activity
        ↓
Inspects queue lifecycle + service demand
        ↓
Inspects live counters
        ↓
Closed/free unstaffed counter?
        ↓
Choose available own-branch Counter Staff
        ↓
Backend validates and assigns
        ↓
Dashboard + staff directory refresh
```

## 57. Day 48 handoff

Day 48 moves to a different role and responsibility level: **System Admin**.

Expected direction:

```text
system-wide status
staff/account administration
branch management
service management
BranchService/capacity management
platform control-plane density
```

The System Admin workspace should not simply copy the Branch Manager dashboard. It needs a denser, system-wide control-plane information architecture.

## 58. Day 49 handoff boundary

Historical reporting, audit exploration and disruption/rescheduling UX remain intentionally reserved for Day 49.

## 59. Completion gate

Day 47 should be declared complete only when:

- focused Day 47 tests pass;
- all previous frontend milestone tests pass;
- the full Smart Q regression suite passes;
- the PR is mergeable;
- README reflects the final merged milestone state.
