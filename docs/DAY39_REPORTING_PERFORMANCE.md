# Smart Q - Day 39 Engineering Documentation

## Historical Reporting and Performance Review

## 1. Day 39 goal

Day 39 turns the append-only `QueueEvent` history into management reporting without creating a second historical source of truth.

The goal is to give Branch Managers and System Admins a compact historical operational view while keeping the approved live queue rules unchanged.

```text
QueueEvent history
        ↓
branch + date-range filter
        ↓
operational aggregation
        ↓
manager/admin report API
```

Day 39 does not change:

```text
Estimated Wait = People Ahead × Service.average_service_time
Check-in opens exactly 6 hours before appointment time
Priority = age >= 55 OR disability OR female + pregnancy for the visit
Branch opening time is the customer-service start boundary
SQLite3 remains the Smart Q project database
```

---

## 2. Reporting API

Endpoint:

```http
GET /api/v1/queues/branches/<branch_id>/reports/operational/
```

Optional inclusive date range:

```http
?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

If dates are omitted, Smart Q returns the most recent 30-day period ending today.

The maximum report range is 366 days to prevent accidental unbounded historical reads.

Access:

```text
Branch Manager -> own branch only
System Admin   -> any active branch
Receptionist   -> denied
Counter Staff  -> denied
Customer       -> denied
```

---

## 3. Historical source of truth

Reporting reads the existing append-only `QueueEvent` table rather than reconstructing history from mutable current-state rows.

Included event types:

```text
CHECKED_IN
CALLED
COMPLETED
NO_SHOW
CANCELLED
RESCHEDULED
DISRUPTION_RESCHEDULED
```

Counter administration events remain available in the audit timeline but are not mixed into customer-flow operational metrics.

### Engineering lesson

Historical reporting should read historical facts. Current booking/ticket status alone cannot reliably answer when a transition happened.

---

## 4. Summary metrics

The report returns counts for:

```text
total included events
checked in
called
completed
no show
cancelled
rescheduled
disruption rescheduled
```

It also groups check-ins by:

```text
queue type
source
service
calendar day
```

This gives management a compact view of traffic, throughput and outcomes without exposing customer-sensitive priority inputs.

---

## 5. Actual wait time

Day 39 introduces a historical actual-wait metric derived from events:

```text
Actual Wait = CALLED.occurred_at - CHECKED_IN.occurred_at
```

Only journeys that contain both valid events are included in the average.

This metric is historical analytics. It does **not** replace the live ETA formula.

```text
Live ETA      = People Ahead × Service.average_service_time
Historical wait = actual CHECKED_IN → CALLED elapsed time
```

Keeping these concepts separate prevents historical analytics from silently changing the approved customer-facing prediction rule.

---

## 6. Actual service time

For completed journeys:

```text
Actual Service Time = COMPLETED.occurred_at - CALLED.occurred_at
```

No-show journeys are not treated as completed service durations.

The API reports:

```text
average_actual_wait_minutes
average_service_minutes
measured_waits
measured_services
```

A missing timing sample returns `null` for the corresponding average rather than inventing zero minutes.

---

## 7. Outcome rates

Day 39 reports completed vs no-show outcomes after a customer has reached an outcome event.

```text
outcome denominator = completed + no_show
completion rate = completed / denominator × 100
no-show rate    = no_show / denominator × 100
```

If no outcome exists, the percentages are `null` rather than misleading `0%` values.

---

## 8. Service breakdown

Each service entry contains:

```text
service_id
service_name
checked_in
completed
no_show
cancelled
```

The report uses the service snapshot relationship stored on QueueEvent, so branch reporting does not need to scan every Booking separately.

---

## 9. Daily activity

The report includes one row per day containing:

```text
date
checked_in
called
completed
no_show
cancelled
```

Only days with included operational events are returned. The frontend can choose whether to display gaps as zero-value days.

---

## 10. Performance review

Day 39 follows the rule:

```text
measure first
optimize second
```

The report uses one bounded QueueEvent queryset for the selected branch/date range and selects only fields required for aggregation.

The existing QueueEvent index:

```text
queue_evt_branch_time(branch, occurred_at)
```

already matches the primary report access pattern:

```text
one branch + bounded occurred_at range
```

SQLite query-plan verification confirms that this existing index supports the historical range query. No speculative new database index was added.

### Engineering lesson

An extra index is not automatically an optimization. Every index increases write/storage cost. Keep an existing index when measurements show that it already matches the query shape.

---

## 11. Query-shape decision

The report selects these fields in one values query:

```text
id
event_type
ticket_id
booking_id
service_id
service name
queue_type
source
occurred_at
```

The service name is joined in the same query. This avoids per-event service lookups and the classic N+1 query pattern.

Timing pairs are calculated in memory after the bounded event set has been loaded.

For the current Smart Q scale and SQLite3 decision, this is intentionally simpler than introducing a reporting warehouse, cache or background aggregation system.

---

## 12. Validation and abuse boundaries

The API rejects:

```text
invalid date formats
start_date after end_date
ranges longer than 366 days
inactive/non-existent branches
cross-branch Branch Manager access
non-management roles
```

These limits keep the endpoint predictable and maintain the same branch-isolation rules used by the audit APIs.

---

## 13. Automated tests

`queues/test_day39_reporting.py` verifies:

```text
historical QueueEvent aggregation
actual wait calculation
actual service-time calculation
completion/no-show rates
queue-type check-in counts
source check-in counts
service breakdown
daily activity
other-branch exclusion
Branch Manager branch scope
System Admin global access
Receptionist denial
invalid/reversed/oversized date-range rejection
SQLite query-plan use of queue_evt_branch_time
```

GitHub Actions also now runs automatically for `main` and every `feature/**` branch, so Day 39 and Day 40 cannot silently fall outside CI coverage.

---

## 14. Day 39 boundary

Included:

```text
historical operational report API
QueueEvent-based aggregation
actual wait analytics
actual service-time analytics
completion/no-show rates
service/daily/queue-type/source breakdowns
bounded date ranges
role + branch isolation
measured SQLite query-plan verification
CI coverage for future feature branches
```

Not added:

```text
ML forecasting
new ETA formula
reporting warehouse
Celery/Redis
scheduled report exports
PDF/CSV export
external BI integration
```

Those are not required for backend v1.

---

## 15. Completion rule

Day 39 is complete when the exact final branch head passes the SQLite3 CI workflow, including the focused reporting tests and the full Smart Q regression suite.

The final backend milestone after this is Day 40: full integration, security and release audit.
