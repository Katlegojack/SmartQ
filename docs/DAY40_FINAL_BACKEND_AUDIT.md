# Smart Q - Day 40 Engineering Documentation

## Final Backend Integration, Security and Release Audit

## 1. Day 40 goal

Day 40 is the backend v1 completion milestone.

The purpose is not to add another major feature. It is to prove that the features built across Days 28-39 still work together under the approved Smart Q rules, permissions and SQLite3 deployment scope.

```text
Days 28-39 backend capabilities
        ↓
final integration journeys
        ↓
security/isolation checks
        ↓
duplicate + stale-state checks
        ↓
release verification
        ↓
backend v1 ready
```

Day 40 preserves the locked product rules:

```text
Check-in opens exactly 6 hours before appointment time
Unchecked at appointment time -> CANCELLED
Branch opens 08:00 -> service starts 08:00
Priority = age >= 55 OR disability OR female + pregnancy for the visit
Estimated Wait = People Ahead × Service.average_service_time
SQLite3 remains the Smart Q project database
```

---

## 2. Final audit scope

Day 40 validates the complete backend across these boundaries:

```text
customer ownership
branch isolation
counter assignment isolation
booking slot capacity
check-in idempotency/conflict handling
queue lifecycle integration
QueueEvent history
historical reporting permissions
ETA contract
migration/system checks
full regression suite
```

The final audit is intentionally evidence-based. Existing tests remain valuable, but Day 40 adds focused cross-feature tests that exercise multiple subsystems in the same journey.

---

## 3. Customer ownership isolation

Customer APIs must never allow one customer to inspect another customer's private booking history.

Day 40 verifies that a customer requesting another customer's booking timeline receives a not-found response rather than the other customer's lifecycle data.

This preserves an important information-disclosure boundary:

```text
customer A booking -> customer A only
customer B -> no access
```

---

## 4. Duplicate check-in protection

Check-in is a state transition, not a repeatable write.

Expected flow:

```text
SCHEDULED
    ↓ first valid check-in
WAITING + checked_in_at + one CHECKED_IN event
    ↓ duplicate check-in request
409 Conflict
```

Day 40 verifies that the duplicate request does not create a second activation event and does not corrupt the ticket state.

This protects against double-clicks, retries and repeated frontend submissions.

---

## 5. Stale capacity revalidation

Frontend availability is only advisory until the final backend write is validated.

Day 40 verifies the final-slot rule:

```text
slot capacity = 1
customer A books final slot
customer B submits same previously visible slot
backend revalidates current capacity
customer B is rejected
```

The second request must not create another Booking.

This prevents stale UI data from bypassing the authoritative booking-capacity rule.

---

## 6. Counter-service integration journey

Day 40 verifies an end-to-end operational path using the existing API surface:

```text
checked-in WAITING customer
        ↓
assigned Counter Staff calls next
        ↓
SERVING + counter assignment + CALLED event
        ↓
Counter Staff completes service
        ↓
COMPLETED booking/ticket + counter released + COMPLETED event
```

The test proves that queue state, booking state, counter state and QueueEvent history remain synchronized across the journey.

---

## 7. Counter assignment security

Being Counter Staff at the same branch is not enough to operate any counter.

Day 40 verifies:

```text
Counter assigned to staff A
staff B attempts Call Next
        ↓
403 Forbidden
```

This preserves the Day 33 assignment boundary and prevents same-branch privilege creep.

---

## 8. Reporting branch isolation

Day 39 introduced historical operational reporting.

Day 40 confirms that its permissions remain consistent with the rest of Smart Q:

```text
Branch Manager -> own branch only
System Admin   -> any active branch
```

A manager from another branch is denied while System Admin retains approved global visibility.

---

## 9. ETA contract audit

The live ETA formula remains intentionally deterministic:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Day 40 includes a direct regression contract proving that one person ahead with a 10-minute service average returns a 10-minute estimate.

Counter count is not introduced into the formula.

Historical Day 39 actual-wait analytics remain separate from this live prediction rule.

---

## 10. Security review summary

The final backend security model relies on layered restrictions rather than frontend trust.

Reviewed boundaries include:

```text
session authentication
CSRF-protected browser login
customer ownership filtering
Smart Q role permissions
branch-scoped staff permissions
counter assignment checks
System Admin global role
bounded reporting date ranges
soft deactivation for operational identities/configuration
append-only operational history
```

Day 40 does not treat hidden frontend buttons as authorization. The API remains responsible for every protected action.

---

## 11. Data-integrity review

The backend v1 integrity model includes:

```text
Booking exactly-one-customer identity constraint
BranchService uniqueness
QueueNumberSequence scope uniqueness
QueueEvent historical indexes
booking-capacity validation
queue-number sequence allocation
final-state guards
one staff -> one counter assignment
checked-in-only live queue selection
```

Day 40 does not add speculative database complexity. The project remains aligned to the approved current Smart Q scale and SQLite3 decision.

---

## 12. Release verification

The GitHub Actions SQLite3 regression workflow runs on `main` and `feature/**` branches.

Day 40 explicitly adds the focused final audit suite before the full regression run:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test queues.test_day40_final_audit
python manage.py test
```

Backend v1 is not considered complete until the exact final Day 40 branch head passes the complete workflow.

---

## 13. Day 40 automated tests

`queues/test_day40_final_audit.py` verifies:

```text
cross-customer timeline denial
duplicate check-in conflict
single CHECKED_IN event after duplicate submission
stale final-slot capacity rejection
Counter Staff Call Next -> Complete journey
booking/ticket/counter state synchronization
CALLED and COMPLETED QueueEvent creation
unassigned Counter Staff operation denial
Branch Manager report isolation
System Admin global reporting access
locked ETA formula
```

These tests complement rather than replace the existing app-specific regression suites.

---

## 14. Backend v1 completion boundary

Included in backend v1:

```text
authentication and role model
branch/service configuration
booking and capacity
six-hour check-in
reception and guest walk-ins
priority/general queues
queue tracking and deterministic ETA
counter assignment/lifecycle
Call Next / Complete / No Show
manager dashboard
notifications/reminder processing
disruption/rescheduling recovery
QueueEvent timeline/audit
historical operational reporting
SQLite3 production/security hardening
final integration/security regression
```

Not required for backend v1:

```text
ML forecasting
WebSockets
SMS/WhatsApp
Celery/Redis
external BI tools
large-scale database infrastructure
frontend implementation
```

These remain separate future/product milestones.

---

## 15. Engineering lesson

A backend is not finished because every feature passed in isolation.

The final milestone must prove that identity, authorization, state transitions, capacity, historical facts and reporting still agree when exercised together.

Day 40 therefore follows this rule:

```text
feature correctness + integration correctness + security boundaries + release evidence
= backend v1 confidence
```

---

## 16. Completion rule

Day 40 is complete only when:

```text
focused Day 40 audit tests pass
all existing Smart Q tests pass
no missing migrations exist
Django system checks pass
exact final branch head is green in GitHub Actions
```

After that evidence is green and the Day 40 pull request is merged, Smart Q backend v1 is complete and frontend integration can begin against a stable backend contract.
