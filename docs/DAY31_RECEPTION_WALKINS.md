# SMART Q Day 31 — Reception, Guest Walk-Ins, and Check-In Reminder Policy

## Objective

Day 31 completes a major reception workflow and corrects the meaning of Smart Q check-in.

A Smart Q check-in is **live-queue activation**, not proof that the customer is physically inside a branch. A registered customer may check in online, while authorised staff may check them in at reception. Once checked in, the customer joins the live queue.

Day 31 also adds guest walk-ins for people who do not have a Smart Q account.

## Product Rules Confirmed on Day 31

### Advance online appointment

```text
Appointment exists
    ↓
QueueTicket = SCHEDULED
    ↓
6 hours before appointment
    ↓
CHECK-IN OPENS
    ↓
Hourly reminders while unchecked
    ↓
Customer checks in online or through staff
    ↓
QueueTicket = WAITING
    ↓
Customer joins live queue
```

### Unchecked appointment expires

```text
Appointment time passes
AND checked_in_at is NULL
    ↓
Booking = CANCELLED
QueueTicket = CANCELLED
```

The customer was never in the live queue, therefore this outcome is **CANCELLED**, not `NO_SHOW`.

### Checked-in customer fails to present when called

```text
checked_in_at exists
    ↓
WAITING
    ↓
CALLED / SERVING
    ↓
Customer does not present
    ↓
Booking = NO_SHOW
QueueTicket = NO_SHOW
```

This preserves an important domain distinction:

- `CANCELLED` — appointment expired without live-queue activation;
- `NO_SHOW` — customer joined the live queue but did not present when called.

## Check-In Window

`queues.services.get_check_in_opens_at()` calculates the exact opening time:

```python
CHECK_IN_OPEN_HOURS = 6


def get_check_in_opens_at(booking):
    return get_booking_datetime(booking) - timedelta(hours=CHECK_IN_OPEN_HOURS)
```

Example:

```text
Appointment: 15:00
Check-in opens: 09:00
```

An early check-in receives HTTP 400 and returns `check_in_opens_at` to the frontend.

An expired unchecked booking is cancelled and a late check-in attempt returns HTTP 409.

## Reminder Policy

Registered online customers receive an in-app check-in reminder once per hour during the six-hour window until they check in.

For a 15:00 appointment:

```text
09:00
10:00
11:00
12:00
13:00
14:00
```

A reminder is not generated after successful check-in.

The reminder service creates only the **current hourly slot**. If scheduling infrastructure was unavailable during an earlier slot, Smart Q does not dump stale reminders on the customer later.

Database deduplication prevents retries from creating the same reminder twice.

## Scheduler-Agnostic Design

Day 31 deliberately does not force Smart Q into Celery/Redis or another background-job platform yet.

Business logic:

```python
create_due_check_in_reminders()
```

Management command:

```powershell
python manage.py process_check_in_reminders
```

This can be invoked hourly by cron, Windows Task Scheduler, Celery Beat, a cloud scheduler, or another approved production job runner later.

## Guest Walk-In Architecture

A guest walk-in does **not** require a Smart Q/Django account.

`GuestCustomer` stores only operationally required information:

- full name;
- optional phone number;
- date of birth;
- gender;
- disability status.

Pregnancy remains a booking-level field because it relates to that visit.

A database constraint enforces that each Booking belongs to exactly one identity:

```text
Registered customer OR Guest customer
Never both
Never neither
```

## Booking Source

Bookings now distinguish:

```text
online
walk_in
```

An online booking starts `SCHEDULED` and must be checked in.

A reception-created guest walk-in is already at the service point, so it is created with:

```text
source = WALK_IN
checked_in_at = now
QueueTicket.status = WAITING
```

## Priority Rules for Guests

Guest walk-ins use the exact same backend priority policy as registered customers:

- age 55+;
- disability status;
- female + pregnancy.

The frontend/receptionist never chooses `GENERAL` or `PRIORITY` directly.

## Reception Search API

```http
GET /api/v1/bookings/reception/search/?q=<query>
```

Reception may search within its assigned branch using:

- booking ID;
- username;
- first/last name;
- email;
- guest name;
- guest phone number.

A branch-scoped staff member cannot search another branch.

System administrators are global but must explicitly provide `branch_id` to avoid accidental global searches.

## Guest Walk-In API

```http
POST /api/v1/bookings/reception/walk-ins/
```

Example request:

```json
{
  "full_name": "Guest Person",
  "phone_number": "0712345678",
  "date_of_birth": "1994-04-10",
  "gender": "other",
  "disability_status": false,
  "is_pregnant": false,
  "service": 1
}
```

The receptionist's branch is taken from the authorised Profile. Reception cannot use the API to create a walk-in in another branch.

## Security

Day 31 reuses the Day 29 authorization model:

```text
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Reception workflows require `IsQueueViewer`.

Branch-scoped staff operate only their assigned branch.

Customers cannot call reception search or walk-in creation APIs.

## Migrations

Day 31 adds:

```text
bookings/migrations/0004_guestcustomer_booking_guest_customer_booking_source_and_constraint.py
notifications/migrations/0003_check_in_reminder_fields.py
```

CI verifies model/migration consistency with:

```powershell
python manage.py makemigrations --check --dry-run
```

## Regression Coverage

Booking/reception tests verify:

- check-in succeeds exactly from the six-hour window;
- early check-in is rejected;
- expired unchecked booking becomes CANCELLED;
- duplicate check-in is rejected;
- ownership remains enforced;
- reception can check in its own branch;
- wrong-branch reception is denied;
- rescheduling clears previous check-in;
- online booking starts SCHEDULED;
- reception can search its branch;
- reception search does not leak another branch;
- guest walk-in requires no account;
- guest walk-in joins WAITING immediately;
- eligible guest receives PRIORITY automatically;
- customer role cannot create guest walk-ins.

Notification tests verify:

- first reminder at six hours before appointment;
- same-hour retry does not duplicate;
- next hour creates the next reminder;
- successful check-in stops reminders;
- expired unchecked booking is CANCELLED, not NO_SHOW;
- no reminder exists before the window.

## CI Verification

Day 31 GitHub Actions runs:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test notifications
python manage.py test
```

All stages passed on the implemented Day 31 branch before documentation closeout.

## Known Limitations

- Hourly execution infrastructure is not selected yet; only the scheduler-independent service and command exist.
- Reminder delivery is currently in-app. SMS/WhatsApp/email/push remain future channels.
- Guest phone number is stored for operational identification but external guest messaging is not implemented yet.
- Branch-Service availability mapping is not yet enforced; this is a later backend slice.
- Capacity-aware appointment slots are not yet implemented.
- The exact staff-side UI flow for calling/searching guests belongs to frontend integration.
- Historical QueueEvent timestamps remain future work.

## Outcome

Day 31 gives Smart Q a complete conceptual distinction between:

```text
scheduled appointment
live-queue activation
walk-in
expired unchecked appointment
no-show after check-in
```

It also enables a receptionist to search branch bookings and place a no-account guest directly into the live queue without weakening Smart Q's priority or branch-security rules.
