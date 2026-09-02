# Smart Q - Day 44 Engineering Documentation

## Appointment Booking, Availability and Rescheduling Experience

## 1. Day 44 goal

Day 44 turns the Day 43 Customer Dashboard into a complete appointment-entry workflow.

Day 43 proved that an authenticated customer could inspect owned bookings, see live queue state, check in, cancel and inspect lifecycle history. Day 44 closes the next customer-facing gap: creating and moving appointments from the real Smart Q backend contract instead of relying on Django Admin or an API client.

The target journey is:

```text
Customer dashboard
        ↓
Choose branch
        ↓
Choose a service offered by that branch
        ↓
Choose appointment date
        ↓
Load backend-generated availability
        ↓
Choose an available slot
        ↓
Review selection
        ↓
Server revalidates capacity
        ↓
Booking + SCHEDULED queue ticket
        ↓
Future check-in
        ↓
WAITING live queue
```

The browser presents choices. Django remains the authority for service availability, capacity, priority, queue ticket creation, check-in eligibility and final state transitions.

---

## 2. Starting point from Day 43

Before Day 44, the Customer workspace already used:

```http
GET   /api/v1/bookings/my/
GET   /api/v1/queues/my-current/
GET   /api/v1/queues/bookings/<booking_id>/timeline/
POST  /api/v1/bookings/<id>/check-in/
PATCH /api/v1/bookings/<id>/cancel/
```

It showed the next appointment, upcoming appointments, historical appointments and live queue information.

The missing journey was the beginning of the lifecycle:

```text
No appointment
      ↓
Book appointment
      ↓
Scheduled appointment
```

Day 44 adds that journey without changing the backend rules already completed before the frontend phase.

### Engineering lesson

A workflow should be built into the lifecycle that consumes its output. A booking form is more useful and easier to verify when the customer can immediately see the resulting appointment and queue reference in the same product surface.

---

## 3. Backend contracts reused

Day 44 reuses the existing backend endpoints rather than adding duplicate frontend rules.

```http
GET   /api/v1/branches/
GET   /api/v1/services/branches/<branch_id>/
GET   /api/v1/services/branches/<branch_id>/<service_id>/availability/?date=YYYY-MM-DD
POST  /api/v1/bookings/
PATCH /api/v1/bookings/<id>/reschedule/
```

The existing Day 43 endpoints remain in use for dashboard refresh, check-in, cancellation and lifecycle history.

### Engineering lesson

One domain rule implemented once in the backend is easier to secure, test and evolve than parallel copies in Django and JavaScript.

---

## 4. Branch selection

The booking workflow starts with the active branch catalogue. The browser displays branch name and city and does not embed a hard-coded location list.

When Branch changes, downstream state is invalidated:

```text
old Service cleared
old Date cleared
old Slot cleared
fresh branch-service request starts
```

### Engineering lesson

Dependent inputs should invalidate downstream state. If Service depends on Branch, changing Branch must clear Service, Date and Slot instead of trusting stale values.

---

## 5. Branch-specific services

After branch selection, the UI loads only services offered by that branch through `BranchService`.

The interface may display the backend-provided average service duration, but it does not use that value to generate slots.

The backend remains responsible for:

```text
slot duration = Service.average_service_time
```

### Engineering lesson

Displaying a business value is different from becoming the authority for that value. Presentation can explain the rule while the server still decides the actual appointment choices.

---

## 6. Date and slot availability

The browser sets today's date as the minimum selectable date for usability. The backend independently rejects past dates and past slots.

After Branch + Service + Date are known, Day 44 calls the existing availability endpoint and renders:

```text
slot time
remaining capacity
available/full state
```

Full slots remain visible but disabled. The frontend does not calculate branch opening boundaries, slot spacing or remaining capacity.

Day 44 also uses an availability request sequence number so an older response cannot overwrite a newer selection if network requests finish out of order.

### Engineering lessons

Client-side validation improves experience; server-side validation protects correctness.

Asynchronous UI introduces stale-response races even when the backend is correct. Old responses must not be allowed to win simply because they arrive last.

---

## 7. Advisory availability vs final capacity authority

The booking form explicitly tells the customer that availability is advisory until the final write.

```text
Customer A sees 1 remaining
Customer B sees 1 remaining
Customer A books first
Customer B submits next
        ↓
backend revalidates current capacity
        ↓
second write is rejected if full
```

The existing serializer validates capacity again inside an atomic create/update path. Day 44 reloads availability after a stale-state 400/409 response.

### Engineering lesson

Read-time availability is a snapshot, not a reservation. Scarce resources must be revalidated at write time.

---

## 8. Booking confirmation and queue reference

Once an available time is selected, the customer sees a review block containing:

```text
Branch
Service
Date
Time
```

The confirm action sends the selected IDs/date/time to the existing booking API. The backend supplies the authenticated user and online source, validates capacity again, creates the Booking, and creates its SCHEDULED QueueTicket through existing queue business logic.

The UI does not generate `A001`, `P001` or any other queue number. After mutation, the dashboard refreshes `/bookings/my/` and displays the backend-created queue reference.

### Engineering lessons

After a mutation, refresh from the authoritative read model instead of manually fabricating the new dashboard state.

Identifiers with business meaning belong to controlled allocation code, not presentation code.

---

## 9. Pregnancy priority server protection

The Day 44 UI shows the pregnancy option only when `/api/v1/accounts/me/` reports a female profile. This preserves the established Smart Q data model:

```text
Gender     -> Profile
Pregnancy  -> visit/Booking
```

Day 44 also closes the server-side validation gap: `BookingCreateSerializer` rejects `is_pregnant=true` unless the authenticated customer's profile gender is female.

This is required because hidden frontend controls are not a security boundary.

### Engineering lesson

```text
Frontend condition = cleaner experience
Backend condition  = trustworthy rule
```

A value that can change queue priority must be validated at the API boundary.

---

## 10. Rescheduling

Upcoming, non-final, not-yet-checked-in appointments expose a Reschedule action.

The Day 44 reschedule UI keeps Branch and Service fixed and asks for a new Date + Time from fresh backend availability.

```text
Existing appointment
        ↓
Reschedule
        ↓
Branch + Service locked in UI
        ↓
Choose Date
        ↓
Load fresh availability
        ↓
Choose Time
        ↓
PATCH booking
        ↓
backend revalidates capacity
        ↓
QueueTicket -> SCHEDULED
checked_in_at -> null
Booking -> PENDING
        ↓
fresh check-in required
```

The backend's existing reschedule workflow remains responsible for queue-number/state repair and QueueEvent audit creation.

### Engineering lesson

Rescheduling is a state transition, not merely editing two text fields. Reuse the workflow that already preserves capacity, queue state, check-in state and audit history.

---

## 11. Check-in stays server-authoritative

Day 44 retains the Day 43 check-in action.

The browser still does not calculate the six-hour eligibility window. It asks the backend and displays backend outcomes such as:

```text
valid
too early
already checked in
expired/cancelled
final state
```

When too early, the exact backend-provided opening timestamp is shown.

### Engineering lesson

Time-based rules are especially risky to duplicate because browser clocks, time zones and stale client state can disagree with the server.

---

## 12. Booking workflow state

The UI presents five steps:

```text
1 Branch
2 Service
3 Date
4 Time
5 Confirm
```

These are presentation states only. They are not database fields and are not persisted.

### Engineering lesson

Persist domain facts, not temporary interface progress. Transient UI state belongs in the browser when it has no independent business meaning.

---

## 13. Error handling and recovery

Day 44 keeps structured backend validation visible to the customer. Examples include:

```text
service not offered
past date
past slot
invalid slot
slot full
invalid pregnancy priority input
```

When a create/reschedule write fails because current capacity changed, the UI refreshes slot availability instead of leaving a stale selection visible.

### Engineering lesson

Error handling should restore the interface to authoritative state, not only display a message.

---

## 14. Responsive and accessibility behavior

The booking workflow continues the Day 41 design language:

```text
white dominant surfaces
light-blue structure
restrained green success states
small borders/radii
no emoji interface language
```

Desktop uses a three-column Branch/Service/Date row and compact slot grid. Smaller screens collapse progressively to one column.

Form controls remain native HTML inputs/selects/radios with labels and keyboard focus visibility. Disabled/full slots remain understandable in text.

### Engineering lesson

Responsive design should preserve task order and semantics, not just shrink desktop visuals.

---

## 15. Files changed

### Updated

```text
templates/frontend/customer_dashboard.html
static/js/pages/customer-dashboard.js
static/css/customer-dashboard.css
bookings/serializers.py
.github/workflows/django-tests.yml
```

### Added

```text
smartq/test_day44_booking_experience.py
docs/DAY44_BOOKING_EXPERIENCE.md
```

---

## 16. Automated verification

The Day 44 focused suite verifies:

```text
customer page renders the booking workflow contract
customer frontend assets remain discoverable
backend availability can drive a real booking create
created booking belongs to authenticated customer
created booking is ONLINE
created queue ticket is SCHEDULED
queue number is backend allocated
rescheduling uses backend availability
rescheduling clears checked_in_at
rescheduled ticket returns to SCHEDULED
non-female customer cannot submit pregnancy priority directly to API
```

CI adds:

```powershell
python manage.py test smartq.test_day44_booking_experience
```

before the complete Smart Q regression suite.

### Engineering lesson

Frontend milestones need more than markup assertions. The focused suite should prove that the screen contract and the backend lifecycle it depends on still agree.

---

## 17. Product boundary preserved

Day 44 does not introduce:

```text
frontend-generated queue numbers
frontend-generated appointment slots
frontend capacity rules
frontend priority rules
frontend check-in rules
frontend role authorization
React/Tailwind/Bootstrap
WebSockets
ML ETA changes
```

The backend remains the domain authority.

---

## 18. Day 44 completion rule

Day 44 is complete when:

```text
booking UI renders
branch -> service dependency works
backend availability drives slot choices
booking create uses the existing API
reschedule uses the existing API
pregnancy priority is server protected
focused Day 44 tests pass
all previous frontend tests pass
complete Smart Q regression remains green
exact Day 44 branch head passes GitHub Actions
```

---

## 19. Next milestone - Day 45

Day 45 moves to the Receptionist workspace and connects the already-complete backend reception contract:

```text
branch-scoped customer/booking search
staff-assisted check-in
guest walk-in creation
branch waiting queue visibility
clear reception operating states
```

This continues the same frontend principle used on Days 41-44:

```text
browser presents and coordinates
backend decides and protects
```
