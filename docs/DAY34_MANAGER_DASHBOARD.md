# Day 34 — Manager Dashboard Read Model and APIs

## Objective

Day 34 gives Branch Managers and System Administrators a truthful operational view of a Smart Q branch without duplicating queue state into a new dashboard database table.

The dashboard is implemented as a **read model**: it derives its response from authoritative domain data already stored in `Booking`, `QueueTicket`, `Counter`, `Branch`, and related models.

## Product Decisions

The approved Day 34 rules are:

1. A Branch Manager may view only their assigned branch.
2. A System Administrator may view any active branch.
3. The dashboard defaults to today's local date and accepts `?date=YYYY-MM-DD` for a different daily report.
4. Only metrics supported by current stored data are exposed.
5. Smart Q does **not** claim an historical average actual wait time yet because the backend does not yet persist the full called/completed timeline required to calculate that metric honestly.

## Why There Is No Dashboard Model

Dashboard values such as waiting customers, open counters, and completed customers are derived state. Persisting those totals would duplicate information already stored in the operational models and introduce synchronization problems.

Instead:

```text
Booking ---------+
QueueTicket -----+
Counter ---------+--> dashboard aggregation service --> API response
Branch ----------+
Service ---------+
```

This keeps one source of truth.

## Day 34 App

A new `dashboard` Django app is used as a cross-domain read layer. It contains no database models and therefore should require no migration.

Files:

```text
dashboard/__init__.py
dashboard/apps.py
dashboard/services.py
dashboard/api_views.py
dashboard/api_urls.py
dashboard/tests.py
```

## API

```http
GET /api/v1/dashboard/branches/<branch_id>/
GET /api/v1/dashboard/branches/<branch_id>/?date=YYYY-MM-DD
```

Permissions:

- Branch Manager: assigned branch only.
- System Admin: any active branch.
- Counter Staff, Receptionist, Customer: denied.

The view uses both role-level and object-level authorization:

```text
IsBranchManager
      +
check_object_permissions(request, branch)
```

This prevents a Branch Manager from changing the branch ID in the URL to inspect another branch.

## Response Sections

The composite dashboard response includes:

- branch identity and operating hours
- report date
- customer activity summary
- General/Priority queue lifecycle counts
- combined lifecycle totals
- online/walk-in booking source counts
- checked-in/not-checked-in counts
- bookings per service
- counter summary
- individual counter state
- assigned staff
- current serving ticket/customer where applicable

## Queue Statistics Refactor

Day 34 refactors `queues/statistics.py` to use conditional aggregation.

Before, multiple status counts were calculated using repeated `.filter(...).count()` queries. The new implementation uses Django `Count` with filtered `Q` expressions so lifecycle counts can be calculated in grouped database queries.

Engineering lesson:

> Correct output is only the first requirement. Query shape also matters as data volume grows.

The report now calculates branch queue statistics once and derives combined totals and activity summaries in Python rather than querying the same data repeatedly.

## N+1 Query Avoidance

The counter dashboard intentionally avoids this pattern:

```python
for counter in counters:
    current_ticket = get_current_ticket(counter)
```

That design would execute one ticket query per counter.

Instead Day 34:

1. fetches all branch counters in one query;
2. fetches all currently-serving branch tickets in one query;
3. builds a dictionary keyed by `assigned_counter_id`;
4. composes each counter's response in memory.

This is the bulk-fetch/index/compose pattern and prevents an N+1 query problem.

## Truthful Metrics

Day 34 deliberately does not label estimated wait values as historical actual averages.

A trustworthy historical average wait requires timestamps such as:

```text
checked_in_at
called_at
completed_at
```

Smart Q currently stores `checked_in_at` but does not yet persist a complete queue event timeline. That work remains scheduled for the queue-event/audit milestone.

## Tests

`dashboard/tests.py` covers:

- correct customer and queue aggregation
- online vs walk-in counts
- check-in counts
- per-service distribution
- live counter summary
- assigned staff/current customer representation
- Branch Manager own-branch access
- cross-branch denial
- System Admin global access
- Counter Staff denial
- invalid date validation

The tests intentionally mix SCHEDULED, WAITING, and SERVING tickets so the dashboard is tested against realistic overlapping operational state rather than only an empty database.

## CI

The GitHub Actions workflow now includes:

```powershell
python manage.py test dashboard
```

and the Day 34 feature branch is included in push-triggered CI.

The final verified CI run and exact test count will be recorded after implementation stabilizes.

## Engineering Concepts Learned

Day 34 demonstrates:

- read models
- derived vs persisted state
- separation of domain aggregation from HTTP handling
- conditional database aggregation
- query reuse
- N+1 query avoidance
- `select_related`
- bulk fetch/index/compose
- object-level authorization
- API input validation
- composite dashboard API design
- truthful metrics and data provenance
- regression testing

## Known Limitation

Historical actual waiting/service-time analytics are not yet available because the current schema does not persist a complete event timeline. Day 34 does not fabricate those metrics.

## Next Handoff

After Day 34 is verified, Smart Q can move to disruption/rescheduling hardening and later queue-event history, which will unlock trustworthy historical wait-time analytics and future ML training data.
