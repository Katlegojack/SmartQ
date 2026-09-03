# Smart Q — Day 48 System Admin Workspace

## Status

Day 48 replaces the generic System Admin application shell with a protected global control plane built on the administration APIs already established during the backend milestones.

**Branch:** `feature/day48-system-admin-workspace`  
**Primary role:** `SYSTEM_ADMIN`  
**Frontend route:** `/app/admin/`  
**Pull request:** #43 — Build Day 48 system admin workspace  
**Initial integrated PR verification:** Django Tests run **242** completed successfully on implementation/documentation head `4043e8625cb220f5c7dfcca38c1ac24bf8938dde`. The focused Day 48 suite and complete Smart Q regression suite both passed. README/documentation closeout commits must pass the same gate again before merge.

---

# Part 1 — Goal and Scope

## 1. Day 48 objective

The Day 48 workspace gives a Smart Q System Admin one global configuration console for work that should not belong to a branch-scoped operator.

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

Day 48 is intentionally about **global configuration and oversight**. Historical reporting and disruption/rescheduling presentation remain Day 49 responsibilities.

## 3. Day 48 acceptance criteria

A valid System Admin must be able to:

1. restore an authenticated `SYSTEM_ADMIN` session;
2. list operational staff accounts;
3. create branch-scoped staff or another System Admin using backend role/branch rules;
4. update safe staff profile fields;
5. activate/deactivate staff safely;
6. create and edit branches;
7. create and edit services;
8. create and edit BranchService capacity mappings;
9. inspect any active branch through the existing manager dashboard read model;
10. see clear loading, empty, validation and conflict states;
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

## 5. Why no duplicate backend control plane was added

Smart Q already had protected APIs for staff, branches, services and BranchService mappings.

Building another `/admin/dashboard/` persistence or workflow layer would duplicate state and create new synchronization responsibilities.

The Day 48 frontend therefore orchestrates existing contracts.

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

Every endpoint remains protected by `IsSystemAdmin`.

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

The serializer remains the final authority against a forged request.

### Engineering lesson

Frontend guidance improves usability. Backend validation guarantees integrity.

## 9. Staff creation fields

Creation includes:

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

The UI labels the initial credential as a temporary password. Password strength remains enforced by Django password validators.

## 10. Staff editing boundary

The existing staff read model exposes operational identity and assignment fields but not every profile field required at creation.

Day 48 therefore edits only fields it can restore truthfully from the existing read contract:

```text
first_name
last_name
email
role
branch
```

It does not fabricate hidden profile values during edit.

## 11. Staff activation safety

Activation uses:

```http
PATCH /api/v1/accounts/admin/staff/<id>/activation/
{
  "is_active": true | false
}
```

Backend protections include:

- a System Admin cannot deactivate the account backing their own current active session;
- Smart Q must retain at least one active System Admin.

The UI disables the current admin's deactivate button for clarity, while the backend independently enforces the rule.

---

# Part 4 — Branch Administration

## 12. Branch API contracts

```http
GET   /api/v1/branches/admin/
POST  /api/v1/branches/admin/
GET   /api/v1/branches/admin/<id>/
PATCH /api/v1/branches/admin/<id>/
```

The administration catalogue includes inactive branches.

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

Native time inputs improve the browser experience but do not replace serializer validation.

## 15. Deactivation instead of destructive delete

Day 48 exposes active-state configuration rather than hard deletion.

This preserves historical bookings, queue events and operational references.

### Engineering lesson

Operational configuration becomes part of historical evidence. Deactivation is often safer than deletion.

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

`average_service_time` influences backend appointment slot duration and operational calculations.

The serializer requires a value greater than zero. Day 48 provides a positive number input, while the backend remains authoritative.

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

A mapping answers two configuration questions:

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

Create selectors therefore show active branches and services only. The serializer still validates the invariant for every write.

## 24. Mapping identity is locked during edit

For an existing mapping, Day 48 edits:

```text
max_bookings_per_slot
is_active
```

The branch/service pair remains visible but locked.

Changing the pair itself can collide with the database uniqueness rule and weakens the meaning of an existing configuration record. Creating a new mapping is clearer when the relationship identity must change.

---

# Part 7 — Global Branch Inspection

## 25. Existing global access reused

The manager dashboard permission model intentionally allows:

```text
BRANCH_MANAGER -> own branch only
SYSTEM_ADMIN   -> any active branch
```

Day 48 reuses:

```http
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

## 26. Inspection instead of manager-screen duplication

The System Admin page does not copy the entire Day 47 manager interface.

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

Detailed branch coordination remains the Branch Manager workspace.

## 27. Temporal semantics remain truthful

The selected date applies to customer/queue activity.

Counter status is still the manager dashboard's explicitly live current-state section.

Day 48 does not pretend current counter assignment/status is historical data.

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

Each administration domain displays:

```text
current catalogue state
        +
controlled create/edit form
```

Configuration work benefits from denser comparison than the task-focused Customer, Receptionist and Counter Staff screens.

## 31. Platform overview metrics

The overview derives counts from the protected catalogues:

```text
active staff / total staff
active branches / total branches
active services / total services
active mappings / total mappings
```

No additional dashboard state is persisted.

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

using `Promise.all`.

These catalogues also populate relationship selectors.

## 33. Refresh sequence guard

A monotonically increasing request sequence prevents an older Refresh All response from overwriting a newer one.

## 34. Refresh-after-write

After successful create/edit/activation operations, the protected catalogues are re-read.

This matters because configuration changes can alter valid options elsewhere in the same control plane.

Examples:

- deactivating a branch changes valid staff/mapping branch choices;
- deactivating a service changes valid mapping choices;
- role/branch updates change staff scope;
- mapping writes change capacity summary counts.

## 35. Explicit create/edit form modes

Staff, Branch, Service and Mapping forms each track create versus edit state.

Titles and action buttons change so the administrator knows whether the next write is POST or PATCH.

## 36. Safe DOM rendering

API-derived names, usernames, service labels and branch labels are rendered through DOM text nodes / `textContent` rather than executable HTML strings.

---

# Part 10 — Security Boundaries

## 37. Exact-role frontend routing

Bootstrap requires:

```text
account.role == system_admin
```

Other authenticated roles are redirected to their own workspace.

This is a UX boundary. Protected APIs remain the security boundary.

## 38. Global permission still has rules

System Admin global scope does not mean invalid state is accepted.

Serializers/services continue to enforce:

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

Day 48 uses activation/deactivation where the backend supports it, preserving historical context.

## 40. Session and CSRF security are reused

All non-safe browser writes use the shared API client, which obtains and sends the CSRF token for Django session-authenticated writes.

---

# Part 11 — Day 48 Automated Tests

## 41. Focused test module

```text
smartq/test_day48_admin_workspace.py
```

## 42. Dedicated route test

The route test proves `/app/admin/` renders Day 48 hooks for staff, branch, service, capacity and branch inspection.

It also checks that Counter Staff and Receptionist-specific serving/intake copy is absent.

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

The focused integration suite exercises:

```text
create branch
    |
create service
    |
create BranchService capacity
    |
create branch-scoped Receptionist
    |
inspect new branch dashboard globally
```

This proves the separate protected APIs cooperate as one admin workflow.

## 46. Role/branch invariant test

The suite proves the backend rejects:

```text
Receptionist + no branch
System Admin + branch
```

even though the UI guides the administrator away from those invalid inputs.

## 47. Self-deactivation safety test

The active System Admin attempts to deactivate their own session account and receives HTTP 400.

## 48. Non-admin denial test

A normal Customer attempts to read each protected administration catalogue and receives HTTP 403.

## 49. CI integration

GitHub Actions includes:

```yaml
- name: Run Day 48 system admin workspace tests
  run: python manage.py test smartq.test_day48_admin_workspace
```

The complete Smart Q regression suite runs afterward.

## 50. Initial integrated CI result

PR #43 run **242** completed successfully on head:

```text
4043e8625cb220f5c7dfcca38c1ac24bf8938dde
```

Verified in that run:

```text
missing migrations check                success
Django system check                    success
all backend app suites                 success
Day 41-47 frontend milestone tests     success
Day 48 system admin workspace tests    success
full Smart Q regression suite          success
```

README and documentation closeout commits occur after this proof, so the final PR head must re-run the same workflow before merge. No merge should be performed while the final head is unverified.

---

# Part 12 — Trade-Offs

## 51. No new admin backend aggregate

**Reason:** protected domain APIs already exist and are sufficient.

**Trade-off:** the browser makes four initial catalogue reads instead of one aggregate request.

**Benefit:** no duplicated API/data ownership; each domain remains independently reusable.

## 52. No destructive delete

**Reason:** historical operational references must remain understandable.

**Trade-off:** inactive records remain visible in admin catalogues.

**Benefit:** stronger audit and history integrity.

## 53. No full Day 47 manager dashboard duplication

**Reason:** System Admin needs global inspection, not a second copy of the complete branch-manager surface.

**Benefit:** clear role boundaries and less frontend duplication.

## 54. No Day 49 reporting/disruption UI

**Reason:** roadmap scope discipline.

**Benefit:** Day 48 remains a global configuration control plane instead of an overloaded universal admin screen.

## 55. Mapping identity locked during edit

**Reason:** preserve `(branch, service)` identity and avoid uniqueness collisions.

**Trade-off:** changing the pair requires a new mapping.

---

# Part 13 — Engineering Lessons

## 56. A control plane is an orchestrator

The admin frontend coordinates protected domain APIs; it does not need to become a new owner of domain rules.

## 57. Global permission still needs invariants

A System Admin has broader scope, not permission to create invalid state.

## 58. Least-destructive operations preserve history

Deactivation is safer than deletion where configuration is referenced by historical records.

## 59. Relationship selectors depend on other catalogues

Staff, branch and BranchService forms demonstrate why configuration UIs often need several read models at the same time.

## 60. Refresh authoritative state after configuration writes

A configuration write can change which options are valid elsewhere. Re-reading avoids stale relationship choices.

## 61. Frontend and backend validation have different jobs

Frontend validation makes mistakes harder. Backend validation makes invalid state impossible for every client.

## 62. Role-specific interfaces should remain distinct

System Admin configures globally. Branch Manager coordinates a branch. Counter Staff serve. Reception activates customers. Distinct role surfaces improve safety and learnability.

## 63. Reusing a read model is often better than duplicating a dashboard

Day 48's global branch inspection reuses the Day 34/47 dashboard contract rather than creating a second analytics definition.

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
README.md
```

No new main Day 48 business API was required.

---

# Part 15 — Final Merge Gate

Day 48 is complete at the implementation level and the initial integrated head passed CI.

The final merge candidate — including README and documentation synchronization — must still satisfy:

```text
missing-migration check
Django system check
all backend app suites
Day 41-48 focused frontend suites
full Smart Q regression suite
```

Only after that exact final head is green should PR #43 merge into `main`.

---

# Part 16 — Day 49 Handoff

Day 49 should build the dedicated history/reporting/disruption experience on top of the existing QueueEvent, reporting and rescheduling APIs.

Day 48's core architectural lesson carries forward:

```text
frontend presents and orchestrates
backend authorizes, validates and decides
```
