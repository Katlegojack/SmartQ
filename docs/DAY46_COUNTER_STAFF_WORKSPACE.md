# Smart Q - Day 46 Engineering Documentation

## Counter Staff Workspace

**Milestone:** Frontend Day 46  
**Branch:** `feature/day46-counter-staff-workspace`  
**Primary workflow:** assigned counter -> open -> call next -> serve -> complete/no-show -> next customer

---

## 1. Day 46 objective

Day 46 replaces the generic Counter Staff application shell with a focused operational workspace built on the counter and queue APIs already proven during the backend milestones.

The target loop is intentionally narrow:

```text
Counter Staff signs in
        |
        v
Restore authenticated role
        |
        v
GET assigned counter
        |
        +--> no assignment -> stop and explain manager assignment requirement
        |
        v
Counter lifecycle state
        |
        +--> CLOSED -> OPEN
        +--> PAUSED -> RESUME or CLOSE when free
        +--> OPEN -> CALL NEXT
        |
        v
SERVING customer
        |
        +--> COMPLETE
        +--> NO_SHOW
        |
        v
Counter free -> CALL NEXT
```

The screen is not a receptionist search tool, manager dashboard or administrator control plane.

---

## 2. Backend contracts reused

Day 46 does not create a second serving algorithm in JavaScript. It uses the existing server contracts:

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

### Engineering lesson

A frontend milestone should orchestrate already-proven domain rules. If the backend already owns queue selection, counter assignment and lifecycle transitions, JavaScript should not reproduce those decisions.

---

## 3. Assignment is an authorization boundary

Counter Staff do not choose their counter from a dropdown.

`GET /api/v1/counters/my/` returns the counter assigned to the authenticated staff member. If there is no assignment, the endpoint returns 404 and the Day 46 UI stops the serving flow with an explicit instruction that a Branch Manager must assign a counter.

This preserves the Day 33 rule:

```text
Branch Manager assigns Counter Staff
        |
        v
Counter Staff operates only that assigned counter
```

The backend rejects same-branch Counter Staff attempting to operate another staff member's counter.

### Engineering lesson

Operational scope should come from authenticated assignment, not client input. A selector would make authority look like a preference when it is actually a permission.

---

## 4. Counter lifecycle represented in the UI

The backend counter states are:

```text
CLOSED
OPEN
PAUSED
```

The Day 46 interface exposes only actions appropriate to the current state.

### CLOSED

The primary action is **Open counter**. Call Next remains disabled.

### OPEN and free

The counter may:

- Call Next;
- Pause;
- Close.

### OPEN and serving

The counter may:

- Complete the current customer;
- Mark the current customer as no-show;
- Pause the counter.

Closing is disabled in the frontend because a current customer exists, while the backend also independently rejects closing a busy counter.

### PAUSED and free

The counter may Resume or Close. Call Next remains disabled.

### PAUSED and serving

The current customer may still be completed or marked no-show, but no new customer can be called until the counter resumes.

### Engineering lesson

A good operational UI mirrors the state machine. It should make the valid next transition obvious instead of exposing every possible endpoint at all times.

---

## 5. Call Next remains backend-owned

The Day 46 page shows a preview of waiting customers matching the assigned counter's queue type, but clicking **Call next customer** does not select a row from that table.

The browser sends only:

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
```

The backend then selects the next eligible ticket for:

```text
assigned counter
+ same branch
+ today's checked-in waiting tickets
+ same queue type as the counter
+ oldest eligible check-in first within that queue type
```

The selected ticket is returned to the frontend as the current customer.

### Engineering lesson

A queue preview is information. Queue allocation is a business decision. Keeping those separate prevents a staff screen from bypassing fairness rules by clicking a different row.

---

## 6. Queue type is a counter property

Each counter has a backend-owned `queue_type` such as General or Priority.

Day 46 displays that queue type and requests a matching waiting preview, but it does not allow Counter Staff to alter it.

The backend Call Next service also filters by the counter's queue type, so even a manipulated browser request cannot make a General counter call a Priority ticket or vice versa through client-side selection.

---

## 7. Current-customer card

When `GET /api/v1/queues/counters/<counter_id>/current/` returns a serving ticket, the workspace presents the information needed to finish the service:

```text
queue number
customer name
service
queue type
appointment date/time
check-in timestamp
```

The two deliberate service outcomes are:

```text
COMPLETE SERVICE
MARK NO-SHOW
```

The UI does not add arbitrary booking status controls.

---

## 8. Complete service

```http
POST /api/v1/queues/counters/<counter_id>/complete/
```

The backend performs the authoritative transition:

```text
QueueTicket: SERVING -> COMPLETED
Booking:     current -> COMPLETED
assigned_counter -> null
QueueEvent:  COMPLETED
```

After success the frontend refreshes the assigned counter, current ticket and waiting preview from backend reads.

### Engineering lesson

After a mutation, refresh the authoritative read model. Do not manually simulate several related database transitions in browser memory.

---

## 9. No-show

```http
POST /api/v1/queues/counters/<counter_id>/no-show/
```

This action is only for a customer who already checked in and was called into `SERVING` but did not present.

The backend transition is:

```text
QueueTicket: SERVING -> NO_SHOW
Booking:     current -> NO_SHOW
assigned_counter -> null
QueueEvent:  NO_SHOW
```

This remains distinct from an unchecked appointment that expires before entering the live queue, which is cancelled rather than marked no-show.

---

## 10. Waiting queue preview

The workspace displays only waiting customers matching the assigned counter's queue type.

The table shows:

```text
queue number
customer
service
check-in time
status
```

It also shows:

```text
waiting count
first visible queue number
counter queue type
```

The preview is read-only. Staff cannot reorder it, drag rows or manually assign a ticket to themselves.

---

## 11. Refresh and concurrency behavior

Day 46 uses refresh-after-write plus an explicit Refresh button rather than introducing a separate polling mechanism during the role-by-role frontend build.

A sequence counter prevents an older asynchronous workspace refresh from overwriting a newer one.

Mutating buttons are disabled while their requests are in flight.

### Engineering lesson

Frontend safeguards improve operator experience, but transactional backend rules remain the real concurrency and integrity boundary.

---

## 12. Error and empty states

The workspace explicitly handles:

- unauthenticated session;
- wrong authenticated role;
- no counter assignment;
- free counter with no current ticket;
- no matching waiting customers;
- paused counter;
- closed counter;
- server conflicts;
- failed reads;
- failed lifecycle actions;
- failed Call Next;
- failed Complete/No-show.

A 404 from the current-ticket endpoint is treated as the normal **counter is free** state rather than as a page failure.

### Engineering lesson

Not every HTTP 404 represents a broken application. In a stateful API, “no current ticket” can be an expected business state and should be translated into useful UI language.

---

## 13. Files added or changed

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

---

## 14. Day 46 automated tests

The focused integration suite verifies:

1. `/app/counter/` renders the dedicated Counter Staff workspace.
2. Day 46 CSS and JavaScript assets are discoverable by Django staticfiles.
3. Counter Staff without an assignment receive the explicit assignment 404.
4. Assigned Counter Staff can open their counter, call the next matching customer, read the current ticket, complete it and return the counter to a free state.
5. A paused counter cannot Call Next but can resolve the existing current customer as no-show.
6. The counter's queue type determines which waiting customer Call Next selects.
7. Another same-branch Counter Staff user cannot operate a counter assigned to someone else.

The GitHub Actions workflow runs the focused Day 46 suite before the complete regression suite.

---

## 15. Trade-offs

### No manual customer selection

This is intentionally stricter than a clickable waiting table. It protects queue fairness and keeps the backend Call Next algorithm authoritative.

### No self-assignment

A no-assignment screen may require a manager intervention, but it preserves the separation between staffing decisions and service execution.

### No manager analytics

Counter Staff see the immediate waiting set for their queue type, not branch performance metrics. Analytics remain a Day 47 Branch Manager concern.

### No automatic polling yet

Explicit refresh plus refresh-after-write avoids introducing a temporary real-time architecture before the final integration phase.

### No frontend-only lifecycle rules

The UI hides/disables invalid actions for clarity, but all important transitions are still validated by the backend.

---

## 16. Core engineering lessons from Day 46

- Model operational interfaces around state transitions, not CRUD forms.
- Authenticated assignment is an authorization boundary.
- A read-only queue preview must not become a manual allocation mechanism.
- The server should own queue selection and fairness.
- Paused does not necessarily mean current work disappears; it blocks new work while allowing safe completion of in-flight work.
- Treat expected empty states differently from system failures.
- Disable duplicate UI actions, but rely on backend transactions for correctness.
- Re-read authoritative state after mutations.
- Keep role surfaces narrow: Counter Staff serve; Reception identifies/checks in; Managers analyse and configure branch operations.

---

## 17. Day 47 handoff

Day 47 moves from an individual counter's serving loop to the Branch Manager's broader operational view.

The manager workspace should build on existing branch-scoped capabilities such as:

```text
branch dashboard metrics
counter states and assignments
waiting/serving operational visibility
disruption controls
historical reporting/audit views
```

The Day 46 lesson must carry forward: management may observe and coordinate the branch, while existing backend permissions and domain services remain authoritative.
