# Smart Q — Day 49 History, Reporting, Disruption & Recovery

## Status

Day 49 turns backend work from Days 35, 36 and 39 into role-appropriate frontend workflows for historical reporting, audit evidence, branch disruption control and customer service recovery.

**Branch:** `feature/day49-history-reporting-disruption`  
**Management route:** `/app/history/`  
**Customer recovery route:** `/app/recovery/`  
**Roles:** `BRANCH_MANAGER`, `SYSTEM_ADMIN`, `CUSTOMER`  
**Verification:** focused Day 49 and complete Smart Q CI are required before merge. This engineering record is written before final verification and must be updated with exact CI facts at closeout.

---

# Part 1 — Goal and Scope

## 1. Day 49 objective

Days 45–48 made the primary role workspaces operational:

```text
Day 45  Receptionist -> customer intake and queue activation
Day 46  Counter Staff -> assigned-counter service execution
Day 47  Branch Manager -> own-branch operational coordination
Day 48  System Admin -> global configuration control plane
```

Day 49 surfaces the historical and disruption-recovery workflows that already existed in the backend but were not yet usable from dedicated frontend screens.

The milestone covers:

```text
historical operational reporting
append-only branch audit history
branch service disruption pause/resume
persistent disruption restoration after refresh
customer reschedule recommendations
customer replacement-slot selection
```

## 2. Why Day 49 spans more than one role

The underlying workflows have different owners.

### Branch Manager

Needs:

- own-branch historical report;
- own-branch audit evidence;
- service pause/resume controls;
- disruption-impact visibility.

### System Admin

Needs:

- global branch report inspection;
- global branch audit inspection.

### Customer

Needs:

- only their own disruption-recovery recommendations;
- future replacement choices;
- server-validated selection/application.

A single universal Day 49 screen would weaken role boundaries created in Days 47 and 48.

## 3. Day 49 frontend routes

```text
/app/history/   -> Branch Manager / System Admin
/app/recovery/  -> Customer
```

The existing role workspaces remain focused. Day 49 navigation points to these dedicated workflows rather than adding several large sections to already dense screens.

### Engineering lesson

A feature can be one roadmap milestone while still requiring multiple role-specific surfaces. Organise by responsibility, not by milestone number.

---

# Part 2 — Historical Operational Reporting

## 4. Existing report API

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
GET /api/v1/queues/branches/<branch_id>/reports/operational/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

Permission:

```text
BRANCH_MANAGER -> assigned branch only
SYSTEM_ADMIN   -> any active branch
```

## 5. Reporting source of truth

The report reads append-only `QueueEvent` history.

It does not derive historical facts from today's mutable Booking or QueueTicket state.

```text
QueueEvent history
      |
      v
historical reconstruction
      |
      +--> actual waits
      +--> actual service time
      +--> outcomes
      +--> daily activity
      +--> service activity
      +--> queue-type/source mix
```

## 6. Reporting period contract

Backend rules:

```text
default period: most recent 30 days
maximum inclusive range: 366 days
start_date <= end_date
ISO YYYY-MM-DD
```

The frontend defaults to a 30-day inclusive period and sends explicit start/end dates when loading the report.

## 7. Historical summary fields

The Day 49 page presents:

```text
lifecycle events
completed outcomes
average actual wait
average actual service time
completion rate
no-show rate
```

It also exposes sample counts for measured waits/services so an average is not shown without its measurement context.

## 8. Actual wait remains separate from live ETA

Smart Q's live ETA contract remains:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Historical actual wait is reconstructed from lifecycle events:

```text
CALLED occurred_at - CHECKED_IN occurred_at
```

Day 49 labels the historical values as actual measurements rather than reusing the live ETA terminology.

### Engineering lesson

Forecasts and historical measurements are different data products. Similar units do not make them interchangeable.

## 9. Service and daily breakdowns

The management UI renders:

- lifecycle activity by day;
- outcomes/activity by service;
- General/Priority check-in mix;
- source check-in mix.

Counts come directly from the report API. The frontend formats and presents them but does not recalculate lifecycle facts.

---

# Part 3 — Append-Only Branch Audit Trail

## 10. Existing audit API

```http
GET /api/v1/queues/branches/<branch_id>/events/
```

Permission:

```text
BRANCH_MANAGER -> own branch
SYSTEM_ADMIN   -> global
```

## 11. QueueEvent evidence fields

The branch audit response includes operational evidence such as:

```text
event_type
source
actor username / role
booking ID
ticket ID
counter ID
queue number / queue type
from/to ticket status
from/to booking status
metadata
occurred_at
```

## 12. Day 49 audit presentation

The frontend shows:

```text
Time | Event | Subject | Transition | Actor
```

Client-side presentation filters include:

- event type;
- actor username/role;
- queue number;
- booking/ticket/counter identifiers.

## 13. Why filtering is client-side in Day 49

The existing audit API returns the authorised branch event history but does not currently expose query filtering/pagination.

Day 49 therefore:

1. loads the authorised event collection;
2. filters it for presentation;
3. displays at most the first 100 matching events;
4. reports how many matching/loaded records exist.

This does **not** change the append-only audit source.

### Trade-off

This is acceptable for the current project scale and deadline, but a future large deployment should add server-side pagination/filtering rather than transferring an unbounded history to the browser.

---

# Part 4 — Disruption Workflow and the Missing Restore Contract

## 14. Existing disruption write APIs

```http
POST /api/v1/rescheduling/branches/<branch_id>/pauses/
GET  /api/v1/rescheduling/pauses/<pause_id>/
POST /api/v1/rescheduling/pauses/<pause_id>/resume/
```

Before Day 49, the manager could create a pause and later inspect/resume it **only if the client still knew its pause ID**.

## 15. Integration gap found on Day 49

A production-style UI cannot rely on temporary browser memory for persistent server state.

Example failure:

```text
Manager pauses service
        |
        v
QueuePause stored in database
        |
        v
Browser refresh
        |
        X
No branch pause-list API to restore active pause ID/state
```

That meant the backend disruption was persistent but the planned frontend workflow was not recoverable after refresh.

## 16. Day 49 restore endpoint

The existing branch pause path now supports GET:

```http
GET /api/v1/rescheduling/branches/<branch_id>/pauses/
```

Response shape:

```json
{
  "branch_id": 1,
  "pauses": [
    {
      "pause_impact": {},
      "affected_waiting_count": 0,
      "reschedule_risk_count": 0,
      "reschedule_risk_tickets": []
    }
  ]
}
```

No new disruption business calculation was introduced. Each item reuses the existing `get_disruption_report()` contract.

## 17. Pause ordering

Pauses are restored using:

```text
active first
then newest started_at
then newest id
```

Reason: the manager's first responsibility after refresh is an interruption that still needs operational action.

## 18. Permission model was not widened

The restore API uses the same `IsBranchManager` object-level branch permission:

```text
Branch Manager -> own branch only
System Admin   -> any active branch
```

The Day 49 manager UI itself exposes pause/resume only to Branch Managers; System Admin uses the history route for global inspection, preserving the UI role boundary from Day 48.

### Engineering lesson

If persistent workflow state disappears from the UI after refresh, the workflow is incomplete even if the database state is correct.

---

# Part 5 — Disruption Impact Remains Backend-Owned

## 19. Pause creation

Manager submits factual operational inputs:

```text
service_id
booking_date
reason
```

Backend validates:

- active branch;
- active service;
- service offered by branch;
- valid booking date;
- branch permission.

## 20. Lost capacity calculation

The browser does not calculate disruption severity.

The backend uses service duration and elapsed pause duration to determine lost service opportunities.

Conceptually:

```text
lost capacity ~= pause duration / average service time
```

The exact existing backend implementation remains authoritative.

## 21. Affected and at-risk tickets

The backend evaluates eligible WAITING tickets for the exact:

```text
branch + service + booking date
```

It then identifies the tail of the affected waiting list that exceeds remaining service capacity as reschedule risk.

The frontend only displays:

- affected waiting count;
- reschedule-risk count;
- at-risk queue numbers;
- lost service capacity;
- pause duration/status/reason.

## 22. Resume is the processing boundary

When the manager resumes a queue, the backend:

```text
resume QueuePause
      |
      v
create/finalise disruption impacts
      |
      v
create notifications
      |
      v
create reschedule recommendations/options
```

The Day 49 page reports processing counts returned by that server workflow and refreshes report/audit/pause state afterward.

### Engineering lesson

A frontend should expose the business boundary already defined by the backend transaction/workflow instead of reproducing each internal step as separate client logic.

---

# Part 6 — BranchService ID Contract Bug Found During Integration

## 23. The contract

`GET /api/v1/services/branches/<branch_id>/` uses `BranchServiceSerializer`.

Important fields:

```text
id         = BranchService mapping ID
service_id = actual Service primary key
service_name
```

The pause POST expects:

```json
{
  "service_id": <Service primary key>
}
```

## 24. Initial Day 49 frontend mistake

The first disruption selector implementation used:

```javascript
option.value = String(mapping.id)
```

That would send a BranchService mapping ID to an API that expects the Service ID.

The values may sometimes coincidentally match in a small database, making this type of bug particularly dangerous.

## 25. Correct implementation

The selector now uses:

```javascript
option.value = String(mapping.service_id)
option.textContent = mapping.service_name
```

and the POST payload uses:

```javascript
service_id: Number(form.elements.service_id.value)
```

## 26. Regression guard

The focused Day 49 test reads the shipped JavaScript asset and asserts that `mapping.service_id` is used.

### Engineering lesson

Never infer foreign-key meaning from a generic `id` field. Read the serializer contract. Mapping-resource IDs and related-object IDs are different identities.

---

# Part 7 — Customer Recovery

## 27. Existing customer recommendation API

```http
GET /api/v1/rescheduling/recommendations/my/
```

The queryset is ownership-scoped:

```text
booking__user = request.user
```

A customer cannot use the endpoint to inspect another customer's recovery recommendations.

## 28. Existing replacement selection API

```http
POST /api/v1/rescheduling/options/<option_id>/select/
```

The option lookup is also ownership-scoped through the recommendation booking.

## 29. Recommendation response

Day 49 consumes existing fields:

```text
recommendation id
booking id
old date/time
suggested date/time
priority_on_reschedule
reason
status
applied_at
options[]
```

Options include:

```text
option date/time
capacity
booked count
available count
is_recommended
is_selected
```

## 30. Bulk booking enrichment

The recommendation contract contains `booking_id` but not branch/service display names.

The customer recovery UI loads these in parallel:

```http
GET /api/v1/rescheduling/recommendations/my/
GET /api/v1/bookings/my/
```

Then it builds:

```javascript
Map<booking_id, booking>
```

and composes display labels in memory.

This avoids one booking-detail request per recommendation.

### Engineering lesson

When a UI needs contextual labels for a list, prefer bulk read + index + compose over N+1 network calls.

## 31. Replacement option selection remains server-authoritative

The browser displays the stored option availability, but selection triggers fresh server validation under the existing transaction/locking logic.

Possible conflict examples:

```text
slot_full
past_slot
past_date
invalid_slot
service_not_offered
```

A stale option therefore cannot be forced through merely because it was displayed earlier.

## 32. Successful recovery state transition

After an option is successfully selected/applied:

```text
Booking -> chosen future date/time
Booking.status -> PENDING
Booking.checked_in_at -> null

QueueTicket.status -> SCHEDULED
QueueTicket.assigned_counter -> null
QueueTicket.queue_type -> PRIORITY when recovery policy applies
QueueTicket.queue_number -> newly allocated

Recommendation.status -> APPLIED
QueueEvent -> DISRUPTION_RESCHEDULED
Notification -> reschedule confirmation
```

## 33. Fresh check-in is required

A recovered appointment does not remain checked in from the disrupted visit.

The customer must enter the new check-in window later and check in again.

The Day 49 customer UI states this explicitly after an applied recovery.

---

# Part 8 — Frontend Information Architecture

## 34. Management history workspace

`templates/frontend/history_reporting_workspace.html`

Sections:

```text
Historical report
Audit trail
Disruptions (Branch Manager only)
Security
```

System Admin receives an active branch selector for history/reporting.

Branch Manager receives no branch selector; branch scope comes from `/accounts/me/`.

## 35. Customer recovery workspace

`templates/frontend/customer_recovery_workspace.html`

Sections:

```text
Recovery summary
Recommendation cards
Replacement options
Security
```

The design is intentionally less dense than the management history page because the customer task is a decision, not analysis.

## 36. Navigation integration

The shared app shell adds:

```text
Branch Manager -> History & disruptions
System Admin   -> History & reporting
```

The customer dashboard receives:

```text
Service recovery
```

The history page itself suppresses duplicate injected history navigation because it already contains its own dedicated history navigation.

## 37. Safe DOM rendering

API-derived actor names, queue numbers, service names, branch names, recommendation reasons and other dynamic values are rendered via DOM text nodes / `textContent`.

The frontend does not create executable HTML from customer/staff-provided strings.

---

# Part 9 — Frontend State and Concurrency

## 38. Management refresh sequence

The history page uses a monotonically increasing refresh sequence.

An older asynchronous refresh cannot overwrite state from a newer refresh request.

## 39. Recovery refresh sequence

The customer recovery page uses the same freshness pattern for parallel recommendations/bookings loading.

## 40. Refresh-after-write

After disruption resume:

```text
reload pauses
reload audit
reload historical report
```

After customer option selection:

```text
reload recommendations
reload bookings
```

This avoids simulating compound backend writes across several client-side objects.

## 41. No automatic polling yet

Day 49 uses explicit refresh and refresh-after-write.

A permanent real-time/polling strategy remains part of final integration/release decisions rather than adding a temporary mechanism just before Day 50.

---

# Part 10 — Security Boundaries

## 42. History route roles

The page-level JavaScript permits only:

```text
BRANCH_MANAGER
SYSTEM_ADMIN
```

Other roles are redirected to their normal role route.

Backend permissions still protect every report/audit/disruption API.

## 43. Manager branch scope

A Branch Manager's branch comes from authenticated account state.

There is no editable branch selector for the manager.

## 44. System Admin history scope

System Admin loads the protected branch administration catalogue and selects an active branch for report/audit inspection.

This uses the System Admin's existing global access without weakening Branch Manager object-level rules.

## 45. Customer ownership scope

Recovery reads and writes are tied to `request.user` through the Booking relationship.

Knowing another recommendation/option ID does not grant access.

## 46. Frontend role checks are not security

Navigation and route redirection improve usability.

Real security remains:

```text
Django session authentication
DRF permission classes
object ownership/branch checks
serializer/service validation
transactional slot revalidation
```

---

# Part 11 — Focused Day 49 Testing

## 47. Focused test module

```text
smartq/test_day49_history_recovery.py
```

## 48. Route and asset coverage

Tests verify:

```text
/app/history/
/app/recovery/
css/day49-workflows.css
js/pages/history-reporting-workspace.js
js/pages/customer-recovery-workspace.js
```

The route tests assert key workflow hooks rather than only status code 200.

## 49. Branch pause restoration test

The suite creates active and ended pauses, then proves:

```text
own Branch Manager -> 200
active pause -> restored first
other Branch Manager -> 403
System Admin -> 200
```

## 50. Historical API role test

The suite proves:

```text
own manager report/audit -> 200
Receptionist report/audit -> 403
System Admin report/audit -> 200
```

It also verifies existing CHECKED_IN history appears in report/audit data.

## 51. End-to-end disruption recovery test

The primary Day 49 integration test executes:

```text
Manager pauses service
        |
        v
pause persists in DB
        |
        v
GET branch pauses restores state
        |
        v
simulate sufficient elapsed interruption
        |
        v
Manager resumes
        |
        v
backend computes affected + reschedule risk
        |
        v
backend creates recommendations/options
        |
        v
Customer lists own recommendation
        |
        v
Customer selects future option
        |
        v
backend revalidates slot
        |
        v
Booking -> PENDING, fresh check-in required
Ticket  -> PRIORITY + SCHEDULED
        |
        v
DISRUPTION_RESCHEDULED audit event
```

## 52. BranchService service ID regression test

The test reads the shipped history JavaScript and asserts:

```text
mapping.service_id
service_id: Number(form.elements.service_id.value)
```

This locks the serializer/frontend contract discovered during Day 49 integration.

---

# Part 12 — CI

## 53. Named Day 49 CI gate

GitHub Actions now includes:

```yaml
- name: Run Day 49 history reporting and recovery tests
  run: python manage.py test smartq.test_day49_history_recovery
```

It runs after Days 41–48 frontend gates and before the complete regression suite.

## 54. Verification policy

Day 49 is not complete merely because the focused test passes.

The merge candidate must pass:

```text
missing migration check
Django system check
all backend app suites
Day 41-49 focused frontend suites
complete Smart Q regression suite
```

After merge, `main` must be checked again before the milestone is closed.

**Final CI run IDs / head / merge commit are intentionally pending until verification completes.**

---

# Part 13 — Trade-Offs

## 55. Dedicated Day 49 pages instead of expanding existing dashboards

**Benefit:** preserves role/task focus and avoids turning Day 47/48 pages into universal workspaces.

**Cost:** one additional navigation step.

## 56. Client-side audit filtering

**Benefit:** no unnecessary backend contract expansion for the current project scale.

**Cost:** does not scale indefinitely; future production growth should add server pagination/filtering.

## 57. One pause restore collection endpoint

**Benefit:** completes persistent workflow restoration with minimal new API surface.

**Cost:** currently returns all branch pauses rather than a paginated collection.

## 58. No WebSocket/polling implementation

**Benefit:** avoids temporary infrastructure just before final integration.

**Cost:** users explicitly refresh or rely on refresh-after-write.

## 59. Customer recovery on a separate route

**Benefit:** disruption recovery remains clear and high-signal instead of being buried among ordinary booking actions.

**Cost:** customer must navigate from My Smart Q to recovery when action is required.

---

# Part 14 — Consolidated Engineering Lessons

## 60. Persistent workflows require read restoration

Database persistence alone is not enough. After a refresh, the client must be able to reconstruct the workflow state needed for the next action.

## 61. Serializer field names are contracts

`id` and `service_id` represented different database identities. Reading the serializer prevented a subtle wrong-resource bug.

## 62. Historical facts should come from event history

Mutable current state cannot reliably answer what happened in the past. Append-only events are a stronger reporting foundation.

## 63. Historical actuals and live estimates must stay separate

Measured wait time and deterministic ETA may both use minutes, but they answer different questions.

## 64. One milestone can need multiple role surfaces

Design should follow responsibility rather than forcing every feature into a single page.

## 65. Backend workflows should remain compound operations

Resume processing and recovery application touch several records. The client calls the domain operation and refreshes authoritative state instead of reimplementing the transaction.

## 66. Bulk read + index + compose avoids N+1 calls

The customer recovery page enriches recommendation booking IDs with one booking-list request rather than one request per recommendation.

## 67. Displayed capacity is advisory until the write

A replacement option can become stale after it is rendered. Transactional backend revalidation is the only safe acceptance rule.

## 68. UI visibility is not permission

A manager-only section hidden in JavaScript is convenience; DRF branch/object permission remains security.

## 69. Tests should protect integration discoveries

When Day 49 exposed the `service_id` mismatch, the fix was accompanied by a test so the lesson becomes executable knowledge.

---

# Part 15 — Files Added or Changed

Current Day 49 implementation includes:

```text
rescheduling/api_views.py
templates/frontend/history_reporting_workspace.html
templates/frontend/customer_recovery_workspace.html
static/css/day49-workflows.css
static/js/pages/history-reporting-workspace.js
static/js/pages/customer-recovery-workspace.js
static/js/pages/app-shell.js
smartq/urls.py
smartq/test_day49_history_recovery.py
.github/workflows/django-tests.yml
docs/DAY49_HISTORY_REPORTING_RECOVERY.md
```

README synchronization is a closeout task after the integrated implementation is verified.

---

# Part 16 — Day 50 Handoff

Day 50 is the final frontend integration and release audit.

It should treat Days 41–49 as one system and verify:

```text
cross-role navigation
responsive behavior
session expiry paths
loading / empty / error states
access-control consistency
frontend/backend contract consistency
release documentation
full regression health
```

Day 49's central handoff principle is unchanged from the broader Smart Q architecture:

```text
frontend presents and orchestrates
backend authorizes, validates and decides
history records what actually happened
```
