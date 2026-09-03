# Smart Q — Day 48 System Admin Workspace

## Status

Day 48 replaces the generic System Admin application shell with a protected global control plane built on the administration APIs already established during the backend milestones.

**Branch:** `feature/day48-system-admin-workspace`  
**Primary role:** `SYSTEM_ADMIN`  
**Frontend route:** `/app/admin/`  
**Verification:** GitHub Actions pending at the time this engineering record is first written.

---

# Part 1 — Goal and Scope

## 1. Day 48 objective

The Day 48 workspace must let a System Admin perform the global configuration work that should not belong to a branch-scoped operator.

The control plane covers five responsibilities:

```text
Staff accounts
Branches
Services
BranchService capacity
Global branch inspection
```

The page remains an API client. It does not become a second configuration backend.

## 2. Position in the frontend roadmap

```text
Day 41  Frontend foundation
Day 42  Authentication + role-aware shell
Day 43  Customer Dashboard
Day 44  Booking / availability / rescheduling
Day 45  Receptionist Workspace
Day 46  Counter Staff Workspace
Day 47  Branch Manager Workspace
Day 48  System Admin Workspace
Day 49  History / reporting / disruption UX
Day 50  Full integration / responsive / release audit
```

Day 48 is intentionally about **global configuration and oversight**. It does not absorb the historical reporting/disruption milestone planned for Day 49.

## 3. Day 48 acceptance criteria

A valid System Admin should be able to:

1. restore the authenticated System Admin session;
2. list operational staff accounts;
3. create branch-scoped staff or another System Admin using backend role/branch rules;
4. update safe staff profile fields;
5. activate/deactivate staff safely;
6. create and edit branches;
7. create and edit services;
8. create and edit BranchService capacity mappings;
9. inspect any active branch through the existing manager dashboard read model;
10. see useful loading, empty, validation and conflict states;
11. remain blocked from unsafe shortcuts such as self-deactivation or invalid role/branch combinations.

---

# Part 2 — Architecture and API Reuse

## 4. Day 48 architecture

```text
System Admin session
        |
        v
GET /api/v1/accounts/me/
        |
        +--> role must be system_admin
        |
        v
Day 48 Admin Workspace
        |
        +--> /accounts/admin/staff/
        +--> /branches/admin/
        +--> /services/admin/
        +--> /services/admin/branch-services/
        +--> /dashboard/branches/<branch_id>/
```

No new business endpoint was required for the main Day 48 workflow.

## 5. Why no new backend control plane was added

Smart Q already had protected APIs for staff, branches, services and BranchService mappings.

Building another `/admin/dashboard/` persistence layer would duplicate state and create new synchronization responsibilities.

The frontend therefore orchestrates existing contracts.

### Engineering lesson

When the required domain APIs already exist, integration is usually safer than abstraction-for-abstraction's-sake.

---

# Part 3 — Staff Administration

## 6. Staff API contracts

```http
GET   /api/v1/accounts/admin/staff/
POST  /api/v1/accounts/admin/staff/
GET   /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/activation/
```

All of these APIs remain protected by `IsSystemAdmin`.

## 7. Staff roles managed by System Admin

```text
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Public registration still creates only Customer accounts.

## 8. Role/branch invariant

The backend enforces:

```text
Receptionist   -> active branch required
Counter Staff  -> active branch required
Branch Manager -> active branch required
System Admin   -> branch must be null
```

The Day 48 form mirrors this rule by disabling and clearing the branch selector when System Admin is selected.

The serializer remains the final authority if a caller forges a request.

### Engineering lesson

A frontend can guide valid input, but it must never become the only location where authorization/configuration invariants exist.

## 9. Staff creation fields

Creating staff requires:

```text
username
password
first_name / last_name
email
date_of_birth
gender
disability_status
role
branch where required
```

The page labels the password as a temporary password because the created user should rotate credentials through the normal authenticated security flow.

## 10. Staff editing boundary

The existing staff list/detail representation exposes operational identity fields such as name, email, role, branch and activation state.

Day 48 therefore edits only fields the UI can restore truthfully from that read model:

```text
first_name
last_name
email
role
branch
```

It does not pretend to know hidden profile fields during edit.

## 11. Staff activation safety

Activation uses:

```http
PATCH /api/v1/accounts/admin/staff/<id>/activation/
{
  "is_active": true | false
}
```

The backend protects two important cases:

- a System Admin cannot deactivate the account backing their own current active session;
- Smart Q must retain at least one active System Admin.

The frontend disables the current admin's deactivate button for clarity, while the backend still enforces the rule.

---

# Part 4 — Branch Administration

## 12. Branch API contracts

```http
GET   /api/v1/branches/admin/
POST  /api/v1/branches/admin/
GET   /api/v1/branches/admin/<id>/
PATCH /api/v1/branches/admin/<id>/
```

The catalogue includes inactive branches so configuration history remains visible.

## 13. Branch fields

```text
branch_code
name
address
city
opening_time
closing_time
is_active
```

## 14. Operating-hours invariant

The backend validates:

```text
opening_time < closing_time
```

The browser uses native time inputs for usability, but it does not replace server validation.

## 15. Deactivation instead of destructive delete

Day 48 exposes `is_active` rather than a hard-delete control.

This preserves historical bookings, queue events and operational references.

### Engineering lesson

Operational systems often need deactivation rather than deletion because configuration records become part of historical evidence.

---

# Part 5 — Service Administration

## 16. Service API contracts

```http
GET   /api/v1/services/admin/
POST  /api/v1/services/admin/
GET   /api/v1/services/admin/<id>/
PATCH /api/v1/services/admin/<id>/
```

## 17. Service fields

```text
service_code
name
description
average_service_time
is_active
```

## 18. Average service time remains domain data

`average_service_time` is not merely display text.

It influences backend appointment slot duration and operational time calculations.

The serializer requires a value greater than zero.

The Day 48 UI uses a positive number input but the backend remains authoritative.

---

# Part 6 — BranchService Capacity

## 19. BranchService API contracts

```http
GET   /api/v1/services/admin/branch-services/
POST  /api/v1/services/admin/branch-services/
GET   /api/v1/services/admin/branch-services/<id>/
PATCH /api/v1/services/admin/branch-services/<id>/
```

## 20. What BranchService represents

A BranchService record answers two configuration questions:

```text
Does this branch offer this service?
How many scheduled bookings fit in each generated slot?
```

## 21. Mapping fields

```text
branch
service
max_bookings_per_slot
is_active
```

The `(branch, service)` pair is unique.

## 22. Capacity invariant

`max_bookings_per_slot` must be at least 1.

## 23. Active mapping invariant

An active mapping requires:

```text
active branch
AND
active service
```

The Day 48 create selectors therefore list active branches/services only.

The serializer still rejects forged active mappings against inactive records.

## 24. Why branch and service are locked during edit

For an existing mapping, Day 48 allows changing:

```text
max_bookings_per_slot
is_active
```

The branch/service pair is displayed but locked in edit mode.

Reason: changing identity can accidentally collide with the database uniqueness constraint and makes audit meaning less clear. Creating a new mapping is the clearer operation when the pair itself should change.

---

# Part 7 — Global Branch Inspection

## 25. Existing global access reused

The manager dashboard permission class intentionally allows:

```text
BRANCH_MANAGER -> own branch only
SYSTEM_ADMIN   -> any active branch
```

Day 48 reuses:

```http
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

## 26. Why this is inspection rather than duplicated analytics

The System Admin page does not copy Day 47's full manager UI.

It provides a compact global inspection surface showing:

```text
selected branch
selected date
total customers
waiting
serving
live counter total
open counters
busy counters
unstaffed counters
```

This is enough for global oversight while keeping the detailed branch-operations interface in Day 47.

## 27. Temporal semantics remain truthful

The selected date applies to customer/queue activity.

Counter state remains the manager dashboard's explicitly labelled live current state.

Day 48 displays that distinction rather than implying historical counter state exists.

---

# Part 8 — Frontend Information Architecture

## 28. Dedicated route

`/app/admin/` now renders:

```text
templates/frontend/admin_workspace.html
```

instead of the generic application shell.

The page declares:

```html
data-admin-workspace
data-expected-role="system_admin"
```

## 29. Workspace sections

```text
Platform overview
Staff accounts
Branches
Services
Branch capacity
Branch inspection
Security
```

## 30. Dense control-plane design

Day 48 intentionally uses table + form pairings.

Each domain shows:

```text
current catalogue state
        +
controlled create/edit form
```

This is denser than the Customer or Counter Staff experiences because configuration work benefits from comparison and direct editing.

## 31. Platform overview metrics

The overview derives counts from the four protected catalogues:

```text
active staff / total staff
active branches / total branches
active services / total services
active mappings / total mappings
```

No extra dashboard database state is created.

---

# Part 9 — Frontend State Management

## 32. Parallel catalogue loading

The workspace loads:

```text
staff
branches
services
branch-service mappings
```

with `Promise.all`.

All four are required to render the complete configuration console and populate valid relationship selectors.

## 33. Refresh sequence guard

A monotonically increasing sequence prevents an older Refresh All request from overwriting a newer response.

## 34. Refresh-after-write

After any successful create/edit/activation operation, the protected catalogues are re-read from the backend.

This is especially important because:

- deactivating a branch changes which branch choices are valid;
- deactivating a service changes mapping choices;
- staff role/branch changes affect staff tables;
- mapping changes affect capacity summary counts.

## 35. Form modes

Staff, Branch, Service and Mapping forms each support explicit create/edit state.

The form title and button copy change so the operator knows whether the next request will create or patch a resource.

## 36. Safe DOM rendering

API-derived names, usernames, service labels and branch labels are rendered with DOM text nodes / `textContent` rather than HTML string interpolation.

---

# Part 10 — Security Boundaries

## 37. Exact-role frontend routing

Bootstrap requires:

```text
account.role == system_admin
```

Other authenticated roles are redirected to their own workspace.

Backend permissions remain the true security boundary.

## 38. System Admin is global but still constrained

Global scope does not mean unrestricted mutation.

Serializers/services still enforce:

```text
role/branch invariants
active-branch requirements
active-service requirements
capacity minimums
operating-hour ordering
self-deactivation safety
at-least-one-active-admin safety
```

## 39. No hard-delete controls

Day 48 uses activation/deactivation for staff, branches, services and mappings where the backend supports it.

Historical context remains intact.

## 40. CSRF and session security reused

All non-safe browser writes use the shared API client, which obtains and sends the CSRF token for Django session-authenticated writes.

---

# Part 11 — Day 48 Automated Tests

## 41. Focused test module

```text
smartq/test_day48_admin_workspace.py
```

## 42. Dedicated route test

The route test proves `/app/admin/` renders Day 48 administration hooks for staff, branch, service, capacity and branch inspection.

It also verifies Counter Staff and Receptionist-specific serving/intake copy is absent.

## 43. Static asset test

Django staticfiles must discover:

```text
css/admin-workspace.css
js/pages/admin-workspace.js
```

## 44. Protected catalogue test

An authenticated System Admin must be able to read:

```text
staff catalogue
branch catalogue
service catalogue
BranchService catalogue
```

## 45. Cross-domain create workflow test

The test exercises the control-plane chain:

```text
create branch
    |
create service
    |
create BranchService capacity
    |
create branch-scoped receptionist
    |
inspect new branch dashboard globally
```

This proves the separate admin contracts cooperate as one usable workflow.

## 46. Role/branch invariant test

The suite proves the backend rejects:

```text
Receptionist + no branch
System Admin + branch
```

even though the frontend also guides the user away from those inputs.

## 47. Self-deactivation safety test

The active System Admin attempts to deactivate their own session account and receives HTTP 400.

## 48. Non-admin denial test

A normal Customer attempts to read each administration catalogue and receives HTTP 403.

## 49. CI integration

GitHub Actions includes:

```yaml
- name: Run Day 48 system admin workspace tests
  run: python manage.py test smartq.test_day48_admin_workspace
```

The complete Smart Q regression suite still runs afterward.

---

# Part 12 — Trade-Offs

## 50. No new admin backend aggregate

Reason: the protected domain APIs already exist and are sufficient.

Trade-off: the browser makes four initial catalogue requests instead of one aggregate request.

Benefit: no duplicated API/data ownership and each domain remains independently reusable.

## 51. No destructive delete

Reason: historical operational references must remain understandable.

Trade-off: inactive records remain visible in admin catalogues.

Benefit: stronger audit/history integrity.

## 52. No full Day 47 manager dashboard duplication

Reason: System Admin needs global inspection, not a second copy of the full branch manager workspace.

Trade-off: detailed branch work still requires the appropriate dedicated view/workflow.

Benefit: clear role surfaces and less duplicated frontend logic.

## 53. No Day 49 reporting/disruption UI

Reason: frontend roadmap scope discipline.

Benefit: Day 48 remains a configuration control plane rather than an overloaded universal admin screen.

## 54. Mapping identity locked during edit

Reason: preserving `(branch, service)` identity avoids uniqueness collisions and ambiguous historical meaning.

Trade-off: changing the pair requires a new mapping.

---

# Part 13 — Engineering Lessons

## 55. A control plane is an orchestrator

The best admin frontend does not need to own the domain rules. It coordinates protected domain APIs and makes their state understandable.

## 56. Global permission still needs invariants

A System Admin has broader scope, not permission to create invalid state.

## 57. Least destructive operations preserve history

Deactivation is safer than deletion in operational systems where configuration is referenced by historical records.

## 58. Relationship selectors depend on other catalogues

Branch/service/staff forms demonstrate why configuration UIs often require several read models at once.

## 59. Refresh authoritative state after configuration writes

A configuration mutation can change what is valid elsewhere in the same control plane. Re-reading avoids stale relationship choices.

## 60. Frontend validation and backend validation have different jobs

Frontend validation improves usability. Backend validation guarantees integrity.

## 61. Role-specific interfaces should remain distinct

System Admin configures globally. Branch Manager coordinates a branch. Counter Staff serve. Reception activates customers. The product becomes safer and easier to learn when these surfaces stay distinct.

---

# Part 14 — Files Added or Changed

```text
templates/frontend/admin_workspace.html
static/css/admin-workspace.css
static/js/pages/admin-workspace.js
smartq/urls.py
smartq/test_day48_admin_workspace.py
.github/workflows/django-tests.yml
docs/DAY48_SYSTEM_ADMIN_WORKSPACE.md
README.md                  (final milestone sync before merge)
```

No new main Day 48 business API was required.

---

# Part 15 — Verification Gate

Day 48 is not considered closed until the final merge-candidate head passes:

```text
missing-migration check
Django system check
all backend app suites
Day 41–48 focused frontend suites
full Smart Q regression suite
```

After that result is known, this section must be updated with the exact CI run and merge state.

---

# Part 16 — Day 49 Handoff

Day 49 should build the dedicated history/reporting/disruption experience on top of existing QueueEvent, reporting and rescheduling APIs.

Day 48's lesson carries forward:

```text
frontend presents and orchestrates
backend authorizes, validates and decides
```
