# Smart Q — Day 51 Receptionist Workflow Simplification + Customer Handoff

## Status

Day 51 is the first post-Day-50 live-product refinement milestone. It was created from direct Codespaces testing rather than from a planned feature checklist.

**Branch:** `feature/day51-receptionist-workflow`  
**Baseline:** verified `main` after PR #48 (`bddf5188d06c8192d63057fb0e27480fbc1bb28d`)  
**Primary purpose:** make Reception the obvious operational bridge between Customer and Counter Staff while removing engineering-oriented UI copy that does not help the receptionist perform the job.

**Final CI / PR / merge:** pending until verification completes.

---

# Part 1 — Live-Test Finding and Day 51 Objective

## 1. Why Day 51 exists

The Day 45 Receptionist Workspace was technically functional, but live product testing exposed a usability contradiction:

- the page opened to a search box instead of actual work;
- the receptionist had to know which customer to search for before Smart Q showed any workload;
- the interface contained development-day labels, backend explanations, branch-scope explanations, queue-priority explanations and keyboard hints;
- the live queue exposed Priority/General counters even though the receptionist does not need those totals to perform the next customer action;
- a customer could join the queue from the Customer Dashboard, but the Receptionist surface did not make that customer handoff obvious.

The result was a screen that explained Smart Q rather than operating Smart Q.

## 2. Day 51 product rule

> **Reception should show work, not explain the system.**

The main screen should answer only:

```text
Who needs attention?
What service do they need?
What state are they in?
What action can Reception take?
```

Anything else belongs in backend logic, documentation, management reporting or a secondary workflow.

## 3. Day 51 scope

Day 51 is intentionally receptionist-only.

It changes:

- Reception's default workload;
- Reception's live customer handoff visibility;
- Reception copy and information density;
- Reception background refresh behavior;
- Reception-focused automated tests;
- one narrow branch-scoped read API needed by the simplified UI.

It does **not** redesign Counter Staff, Branch Manager or System Admin workspaces.

### Engineering lesson

Live product testing exposes failures that API tests cannot: an endpoint can be correct while the role using it still has no obvious job to perform.

---

# Part 2 — Original Architecture Problem

## 4. Search-first reception was backwards

Before Day 51, Reception relied on:

```http
GET /api/v1/bookings/reception/search/?q=<query>
```

The API correctly required at least two search characters.

That is useful for finding an exception, but it cannot support a default shift workload because an empty query returns an error.

The UI therefore opened with no customer list.

```text
Receptionist opens workspace
        ↓
empty search state
        ↓
receptionist must already know a customer
        ↓
search
        ↓
only then does Smart Q show work
```

Day 51 reverses this:

```text
Receptionist opens workspace
        ↓
Today's customers load automatically
        ↓
Receptionist sees work immediately
        ↓
Search is available only when needed
```

## 5. Why search remains

Search is still useful for:

- a customer asking about a booking not currently visible in today's workload;
- finding a booking by name or reference;
- resolving exceptions.

It is no longer the definition of the Receptionist role.

---

# Part 3 — Day 51 Reception Workload API

## 6. New read contract

Day 51 adds:

```http
GET /api/v1/bookings/reception/today/
```

The endpoint returns today's non-final bookings for the receptionist's authorised branch.

## 7. Included booking states

The read model includes:

```text
Booking.PENDING
Booking.CONFIRMED
```

This deliberately covers:

- today's scheduled appointments that may need staff check-in;
- customer self-service live queue entries;
- guest walk-ins created by Reception;
- checked-in customers whose booking remains operationally active.

It excludes:

```text
COMPLETED
CANCELLED
NO_SHOW
future bookings
other branches
```

## 8. Branch security

The endpoint reuses the existing reception/staff branch resolver and `IsQueueViewer` permission boundary.

A Receptionist cannot request a different branch merely by changing a browser value.

System Admin branch behavior remains governed by the existing staff-branch rules; Day 51 does not weaken them.

## 9. Why this is a read contract, not new queue logic

The endpoint does not create another customer lifecycle.

It reads the same authoritative records already used by booking, queue and counter workflows:

```text
Booking
   +
QueueTicket
```

### Engineering lesson

When the UI needs a new view of existing truth, add a narrow read model. Do not invent a second domain workflow just to make a screen easier to render.

---

# Part 4 — Customer → Reception → Counter Coordination

## 10. Customer self-service entry already uses the shared queue lifecycle

The customer live-queue feature creates:

```text
Booking(source=walk_in, date=today, checked_in_at=now)
        +
QueueTicket(status=WAITING)
```

The Day 51 workload API therefore sees the same customer record automatically.

No synchronization table is needed.

## 11. End-to-end coordination

```text
CUSTOMER
books appointment OR joins live queue
        ↓
Booking + QueueTicket
        ↓
RECEPTIONIST
Today's customers + Live queue
        ↓
if appointment needs activation -> Check in
        ↓
QueueTicket = WAITING
        ↓
COUNTER STAFF
existing waiting queue / Call Next
        ↓
SERVING
        ↓
COMPLETED / NO_SHOW
```

The roles coordinate through shared backend state, not by sending messages to each other.

## 12. Why Reception sees both Today's customers and Live queue

The two lists answer different operational questions:

**Today's customers** answers:

> Who belongs to today's branch workload and what action does Reception need to take?

**Live queue** answers:

> Who is already waiting for Counter Staff right now?

A scheduled customer can appear in Today's customers without being in the Live queue yet.

A self-service walk-in appears in both because they are already checked in and waiting.

---

# Part 5 — Receptionist UI Simplification

## 13. Final main-screen structure

The Reception workspace is reduced to:

```text
Reception

Today's customers                         [Add walk-in]
[ Search customer or booking ] [Search]

Customer        Service        Time        Status        Action

Live queue                                 [Refresh]
Queue           Customer       Service     Status

Add walk-in
<essential form fields>

Security
```

## 14. Information removed

Day 51 removes main-screen text such as:

- `Day 45 operational workspace`;
- `Reception never chooses General or Priority`;
- `The backend assigns...`;
- `Branch scoped`;
- `Session active`;
- keyboard shortcut instructions;
- queue-priority explanation paragraphs;
- check-in architecture explanations;
- capacity or permission explanations;
- Priority/General KPI counters;
- confirmation-panel detail that duplicates the success message.

## 15. Why removing information is an engineering change

The removed text is not wrong.

It is simply the wrong information for this user at this point in the workflow.

Rules such as queue priority remain important, but the backend enforces them. The receptionist does not need a paragraph describing those rules on every shift.

### Engineering lesson

Correct information can still be harmful UI when it competes with the action a user must perform.

## 16. Essential walk-in fields retained

Reception still captures the domain data required to create a safe walk-in:

- full name;
- optional phone;
- date of birth;
- gender;
- service;
- disability status;
- pregnancy when applicable.

The UI does not ask Reception to choose queue type.

The backend still determines queue priority from the authoritative policy.

---

# Part 6 — Live Coordination and Refresh Strategy

## 17. 15-second background refresh

The Reception browser refreshes:

```text
Today's customers
Live queue
```

every 15 seconds while the browser tab is visible.

This allows a customer who joins from another browser/device to become visible at Reception without manual lookup.

## 18. Why polling was chosen

Smart Q does not currently require WebSockets or a persistent browser push channel to solve this workflow.

A small 15-second branch-scoped polling interval is simple, predictable and consistent with the existing REST architecture.

### Trade-off

Polling can show a change up to roughly 15 seconds after it happens. WebSockets could reduce that delay but would introduce connection lifecycle, deployment and reconnection complexity that is not justified by the current project scale.

## 19. Search stability

Background refresh deliberately does **not** overwrite active search results.

Conceptually:

```text
searchMode = false
    -> Today auto-refresh allowed

searchMode = true
    -> user search result remains stable
    -> Live queue may still refresh

Clear search
    -> return to Today workload
```

## 20. Refresh after writes

Reception actions refresh authoritative state immediately.

After staff check-in:

```text
POST staff-check-in
        ↓
refresh Today / current search
        ↓
refresh Live queue
```

After guest walk-in creation:

```text
POST reception walk-in
        ↓
show queue number
        ↓
refresh Today
        ↓
refresh Live queue
```

### Engineering lesson

Periodic polling handles external changes. Immediate refresh-after-write handles changes caused by the current browser. Both are needed for a responsive operational screen.

---

# Part 7 — Error, Empty and Loading States

## 21. Today's customers states

The page distinguishes:

- loading today's customers;
- no customers yet today;
- no search match;
- failed workload read.

It does not fill empty states with tutorials.

## 22. Live queue states

The live queue distinguishes:

- loading;
- no customers waiting;
- populated queue;
- request error.

## 23. Check-in failure

If the backend rejects check-in, the authoritative server message is surfaced.

For an early check-in, the existing `check_in_opens_at` value may be shown so Reception knows when the action becomes valid.

The browser does not recreate check-in-window rules.

---

# Part 8 — Security and Role Boundaries

## 24. Receptionist role remains branch-scoped

Day 51 simplifies presentation, not authorization.

The backend still owns:

- branch scope;
- service validity;
- queue priority;
- queue number generation;
- check-in eligibility;
- booking final states.

## 25. Customers cannot read the Reception workload

The Day 51 focused test proves a Customer receives HTTP 403 from:

```http
GET /api/v1/bookings/reception/today/
```

## 26. Reception does not become Counter Staff

Reception sees who is waiting, but does not receive:

- Call Next;
- Complete;
- No-show;
- counter lifecycle controls.

Those remain Counter Staff responsibilities.

---

# Part 9 — Automated Tests

## 27. Existing Day 45 guard updated

`smartq/test_day45_reception_workspace.py` no longer protects engineering copy as if it were a functional requirement.

It now protects the operational surface:

- Today's customers;
- Live queue;
- Add walk-in;
- search;
- Today table;
- live queue refresh;
- walk-in form;
- no Manager/System Admin content.

It explicitly protects the **absence** of obsolete explanatory copy.

## 28. Day 51 focused suite

New file:

```text
smartq/test_day51_receptionist_workflow.py
```

Focused coverage includes:

1. Reception page is job-first and engineering copy is absent.
2. Today's endpoint returns only current non-final own-branch customers.
3. A customer self-service live queue entry appears in both Reception Today and branch waiting queue.
4. Customer role cannot access Reception workload.
5. Browser module uses the Today API and 15-second background refresh without overwriting active search mode.

## 29. CI gate

The workflow now includes:

```yaml
- name: Run Day 51 receptionist workflow tests
  run: python manage.py test smartq.test_day51_receptionist_workflow
```

Final CI results will be added after exact-head, PR and post-merge verification.

---

# Part 10 — Files Changed

## 30. Day 51 file responsibilities

```text
bookings/reception_api.py
    -> new branch-scoped Today's customers read model

bookings/api_urls.py
    -> route reception/today API

templates/frontend/reception_workspace.html
    -> job-first Reception structure

static/css/reception-workspace.css
    -> simplified presentation and responsive layout

static/js/pages/reception-workspace.js
    -> Today workload, search, queue, check-in, walk-in and polling orchestration

smartq/test_day45_reception_workspace.py
    -> remove obsolete copy requirements; retain Day45 workflow regression guards

smartq/test_day51_receptionist_workflow.py
    -> Day51 coordination and UI tests

.github/workflows/django-tests.yml
    -> named Day51 CI gate

docs/DAY51_RECEPTIONIST_WORKFLOW.md
    -> permanent engineering record

README.md
    -> Day51 project-state synchronization
```

---

# Part 11 — Engineering Decisions and Trade-offs

## 31. Read model instead of changing search semantics

The existing reception search keeps its two-character contract.

Day 51 adds a dedicated Today endpoint rather than overloading an empty search with a different meaning.

This keeps each API intention explicit.

## 32. Polling instead of WebSockets

15-second polling is sufficient for the current operational requirement and does not introduce a new infrastructure layer.

## 33. Keep Live queue separate from Today's customers

Combining both lists into one table would reduce page sections but blur an important state distinction: booked vs already waiting.

## 34. Hide queue-priority explanation, keep priority logic

Day 51 removes explanatory UI text but does not modify the priority algorithm.

The correct abstraction is:

> Reception provides required customer facts. Smart Q decides queue placement.

## 35. Keep Security as a secondary section

Password change remains accessible because it is a real account action, but it does not compete with shift operations at the top of the screen.

---

# Part 12 — Engineering Lessons

## 36. A technically complete screen can still fail its role

Day 45 had working search, check-in, walk-in and queue APIs. Live testing showed the receptionist still could not immediately answer, “What do I do now?”

## 37. Default state is part of workflow design

Opening to an empty search form made the receptionist supply context that Smart Q already had in the database.

Good operational software should use known context to show the next work automatically.

## 38. Shared state is better coordination than manual messaging

Customer and Reception do not need a chat channel to coordinate queue entry. They need both screens to read the same authoritative Booking + QueueTicket state promptly.

## 39. Tests should protect behavior, not historical copy

An old Day45 test required the sentence `Reception never chooses General or Priority` to remain visible.

That was a test-design mistake: the real requirement is that Reception cannot choose priority, which is enforced by the backend. The explanatory sentence is not the requirement.

## 40. Minimal UI requires stronger backend design, not weaker rules

Removing explanations from the screen works because backend permissions and serializers continue to enforce the rules consistently.

## 41. Live testing is an engineering input

Automated tests proved correctness. Codespaces testing exposed usability and coordination defects. Both forms of evidence are required for a product that people can actually operate.

---

# Part 13 — Day 51 Final State

## 42. Expected finished flow

```text
CUSTOMER
        ↓
books appointment OR joins live queue
        ↓
RECEPTION
opens workspace and immediately sees today's workload
        ↓
booked customer -> Check in
walk-in guest -> Add to queue
already waiting customer -> visible, no extra Reception action
        ↓
LIVE QUEUE
        ↓
COUNTER STAFF
Call Next / Serve
```

## 43. Deferred work

Day 51 deliberately does not simplify the Counter Staff, Branch Manager or System Admin workspaces.

Those should be reviewed one role at a time through the same live-test method.

## 44. Verification closeout

Pending:

- exact Day 51 feature-head CI;
- official Day 51 PR CI;
- merge commit;
- post-merge `main` CI;
- final downloadable Day 51 DOCX/PDF package.

These fields will be updated only after GitHub verifies the exact final state.
