# Smart Q - Day 61 Final Engineering Documentation

## 1. Purpose of Day 61

Day 61 moved Smart Q from a forecasting-data foundation into a controlled, real-time operational simulation designed to generate realistic labelled observations before any machine-learning model is trained.

The goal was not to write artificial completed rows directly into a CSV. The goal was to make Smart Q operate a busy synthetic branch through the same queue lifecycle used by the product:

```text
Booking -> Scheduled QueueTicket -> Check-in -> Waiting -> Call Next -> Serving -> Completed
```

This allowed the Day 59 `QueueForecastObservation` pipeline to collect real prediction-vs-outcome evidence through normal `QueueEvent` creation.

---

## 2. Final Verified Result

The live Day 61 run on 7 September 2026 completed successfully with:

```text
Busy-day simulation complete: all 80 customers processed.
```

The terminal showed real target-vs-actual service variance, including:

```text
A066 - actual 22.0 min, target 15 min, variance +7.0 min
A068 - actual  8.0 min, target 10 min, variance -2.0 min
A067 - actual 27.0 min, target 20 min, variance +7.0 min
A069 - actual 14.0 min, target 15 min, variance -1.0 min
A070 - actual 17.0 min, target 20 min, variance -3.0 min
A071 - actual 11.0 min, target 10 min, variance +1.0 min
A072 - actual 15.0 min, target 15 min, variance +0.0 min
```

This confirmed that Smart Q can process a full synthetic busy day, free counters immediately when work finishes, and retain actual operational timing rather than forcing every visit to match a configured average.

---

## 3. Scenario Shape

The Day 61 scenario used:

```text
Branch: ML01 - Smart Q Training Branch
Customers: 80
General queue: 72
Priority queue: 8
Counters: 3
General counters: 2
Priority counters: 1
Appointment range: 08:00 to 15:45
Appointment interval points: 15 minutes
```

Services:

| Service | Baseline Target |
| --- | ---: |
| Collections | 10 min |
| ID Applications | 15 min |
| Passport Applications | 20 min |

The 8 Priority customers were produced through the normal Smart Q priority rules using age, disability and pregnancy conditions instead of directly forcing the queue lane.

---

## 4. Why the Simulation Uses the Real Domain Path

A simple CSV generator would have been easier, but it would not verify queue allocation, counter availability, check-in timing, queue ordering, actual waiting time or service-duration residuals.

Day 61 deliberately drives the same domain logic as the product:

```text
Scheduled booking becomes due
        |
        v
CHECKED_IN event
        |
        v
QueueTicket -> WAITING
        |
        v
Matching free counter calls next
        |
        v
QueueTicket -> SERVING
        |
        v
Actual service duration elapses
        |
        v
QueueTicket -> COMPLETED
        |
        v
Forecast observation receives actual outcome labels
```

This makes the resulting dataset much more useful for later statistical and machine-learning evaluation.

---

## 5. Important Timing Rule

The configured service average is a baseline target, not reserved counter time.

Example:

```text
Target: 15 min
Actual: 8 min
Variance: -7 min
```

At minute 8, the service completes and the counter becomes free immediately. Smart Q does not wait until minute 15.

That difference is crucial because the future forecasting model needs to learn the difference between:

- service finishing early;
- service overrunning;
- counter idle time because nobody is waiting;
- queue congestion;
- actual throughput.

---

## 6. Commands Used

### 6.1 Update and prepare the Codespace

```bash
git checkout main
git pull origin main

cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

python manage.py migrate
```

### 6.2 Seed exactly 80 customers

```bash
python manage.py seed_busy_day \
  --date 2026-09-07 \
  --customers 80 \
  --reset
```

### 6.3 Run mandatory preflight verification

```bash
python manage.py verify_busy_day \
  --date 2026-09-07 \
  --customers 80
```

Expected readiness line:

```text
READY: the Smart Q busy-day scenario is structurally ready for the 08:00 live run.
```

### 6.4 Start Django in Terminal 1

```bash
python manage.py runserver 0.0.0.0:8000
```

The Smart Q application should be opened from forwarded Django port 8000.

### 6.5 Run the simulator in Terminal 2

```bash
python manage.py run_busy_day --date 2026-09-07
```

### 6.6 Export the completed forecasting dataset

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-07 \
  --end-date 2026-09-07 \
  --output smartq_training_2026-09-07.csv
```

---

## 7. Core Simulation Configuration Code

File:

```text
queues/busy_day.py
```

Core configuration:

```python
SCENARIO_BRANCH_CODE = "ML01"
SCENARIO_BRANCH_NAME = "Smart Q Training Branch"
SCENARIO_VERSION = "busy-day-v1"
CUSTOMER_PREFIX = "mlbusy_"

SERVICE_SEQUENCE = ("COLLECT", "IDAPP", "PASSPORT")
SERVICE_PROFILES = {
    "COLLECT": {
        "name": "Collections",
        "average_minutes": 10,
        "duration_minutes": (10, 5, 13, 8, 11, 6, 10, 15, 9),
    },
    "IDAPP": {
        "name": "ID Applications",
        "average_minutes": 15,
        "duration_minutes": (15, 8, 19, 12, 17, 10, 15, 22, 14),
    },
    "PASSPORT": {
        "name": "Passport Applications",
        "average_minutes": 20,
        "duration_minutes": (20, 12, 27, 17, 24, 15, 20, 30, 19),
    },
}
```

Counter staff setup:

```python
STAFF_SPECS = (
    ("ml_counter_general_1", "General", "One", QueueTicket.GENERAL, "1"),
    ("ml_counter_general_2", "General", "Two", QueueTicket.GENERAL, "2"),
    ("ml_counter_priority_1", "Priority", "One", QueueTicket.PRIORITY, "3"),
)
```

The Branch Manager observer account uses an environment variable instead of storing a password in Git:

```python
SCENARIO_MANAGER_USERNAME = "ml_manager"
SCENARIO_MANAGER_PASSWORD = os.getenv("SMARTQ_TRAINING_MANAGER_PASSWORD")
```

---

## 8. Reproducible Service-Time Variation

The simulator deliberately avoids uncontrolled randomness.

```python
def planned_service_minutes(username: str, service_code: str, target_date: date) -> int:
    profile = SERVICE_PROFILES[service_code]
    options = profile["duration_minutes"]
    customer_index = parse_customer_index(username)
    occurrence = (customer_index - 1) // len(SERVICE_SEQUENCE)
    rng = random.Random(
        f"{SCENARIO_VERSION}:{target_date.isoformat()}:{service_code}"
    )
    rotation = rng.randrange(len(options))
    return int(options[(occurrence + rotation) % len(options)])
```

This gives the workload variation while keeping the same scenario reproducible when restarted.

---

## 9. Booking Activation Code

Day 61 uses the normal queue-event path instead of directly changing analytics data.

```python
@transaction.atomic
def activate_simulation_booking(booking: Booking, *, occurred_at=None):
    booking = Booking.objects.select_for_update().select_related(
        "branch", "service", "user", "user__profile"
    ).get(pk=booking.pk)

    if booking.checked_in_at is not None:
        return booking.queueticket, "already_checked_in"

    ticket = QueueTicket.objects.select_for_update().get(booking=booking)

    if occurred_at is None:
        occurred_at = timezone.now()

    old_ticket_status = ticket.status
    old_booking_status = booking.status

    ticket.status = QueueTicket.WAITING
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    booking.checked_in_at = occurred_at
    booking.status = Booking.PENDING
    booking.save(update_fields=["checked_in_at", "status"])

    record_queue_event(
        QueueEvent.CHECKED_IN,
        ticket=ticket,
        booking=booking,
        source=QueueEvent.SYSTEM,
        from_ticket_status=old_ticket_status,
        to_ticket_status=QueueTicket.WAITING,
        from_booking_status=old_booking_status,
        to_booking_status=Booking.PENDING,
        occurred_at=occurred_at,
        metadata={"simulation": SCENARIO_VERSION},
    )
    return ticket, None
```

This is the key bridge into the existing Day 59 forecasting observation pipeline.

---

## 10. Seeder Command

File:

```text
queues/management/commands/seed_busy_day.py
```

The command accepts:

```python
parser.add_argument("--date", dest="target_date")
parser.add_argument("--customers", type=int, default=80)
parser.add_argument("--reset", action="store_true")
```

It blocks production execution:

```python
if getattr(settings, "IS_PRODUCTION", False):
    raise CommandError("seed_busy_day is disabled in production.")
```

It creates the training branch, services, staff, counters, manager, synthetic users, bookings and queue tickets inside a transaction.

For the 80-customer scenario, priority is generated through the normal profile/booking rules. Example logic:

```python
if is_priority and rank % 3 == 0:
    dob = date(1960, 1, 1)
    gender = Profile.MALE
    disability = False
    pregnant = False
elif is_priority and rank % 3 == 1:
    dob = date(1988, 1, 1)
    gender = Profile.OTHER
    disability = True
    pregnant = False
elif is_priority:
    dob = date(1992, 1, 1)
    gender = Profile.FEMALE
    disability = False
    pregnant = True
```

This is better than manually forcing `queue_type=priority` because it tests the actual Smart Q priority policy.

---

## 11. Preflight Verification Command

File:

```text
queues/management/commands/verify_busy_day.py
```

The verifier checks:

- exact customer count;
- 72/8 General/Priority split;
- clean scheduled state;
- no premature forecasting observations;
- required appointment checkpoints;
- exactly three counters;
- 2 General / 1 Priority counter split;
- valid Counter Staff assignment;
- correct branch scope;
- at least two General and one Priority arrival at 08:00;
- early, exact and overrun examples for every service;
- Branch Manager observer scope.

Successful output ends with:

```python
self.stdout.write(
    self.style.SUCCESS(
        "READY: the Smart Q busy-day scenario is structurally ready for the 08:00 live run."
    )
)
```

---

## 12. Real-Time Runner Code

File:

```text
queues/management/commands/run_busy_day.py
```

The command runs a real wall-clock loop:

```python
while True:
    now = timezone.now()

    if now < start_at:
        wall_clock.sleep(min(poll_seconds, 10.0))
        continue

    if not opened:
        self._open_counters(counters)
        opened = True

    self._activate_due_bookings(...)
    self._complete_due_services(counters, target_date)
    self._fill_free_counters(counters, target_date)

    remaining = Booking.objects.filter(...).exclude(
        status=Booking.COMPLETED
    ).count()

    if remaining == 0:
        self._close_counters(counters)
        self.stdout.write(
            self.style.SUCCESS(
                f"Busy-day simulation complete: all {bookings.count()} customers processed."
            )
        )
        return

    wall_clock.sleep(poll_seconds)
```

---

## 13. Completing Services by Actual Duration

The runner uses `service_started_at` and the planned actual duration to determine when a service is complete:

```python
elapsed = (now - ticket.service_started_at).total_seconds()
if elapsed < planned_minutes * 60:
    continue

completed = complete_current_ticket(
    counter,
    actor=counter.assigned_staff,
)
```

The output records actual time and variance:

```python
actual_minutes = (completed.actual_service_seconds or 0) / 60
variance_minutes = (completed.service_variance_seconds or 0) / 60

self.stdout.write(
    f"COMPLETE - {completed.queue_number} at Counter {counter.counter_number}: "
    f"actual {actual_minutes:.1f} min, target "
    f"{(completed.service_target_seconds or 0) / 60:.0f} min, "
    f"variance {variance_minutes:+.1f} min."
)
```

---

## 14. Immediately Reusing a Free Counter

Free counters call the next eligible ticket immediately:

```python
if counter.status != Counter.OPEN or get_current_ticket(counter) is not None:
    continue

ticket = call_next_ticket(
    counter,
    booking_date=target_date,
    actor=counter.assigned_staff,
)
```

If no matching customer is waiting, the counter remains idle until a later arrival becomes eligible.

This is an important distinction: idle time is a real operational state, not a simulator bug.

---

## 15. Forecasting Data Captured

Because the simulation enters through normal queue events, `QueueForecastObservation` rows are generated automatically.

At check-in Smart Q records pre-outcome features such as:

```text
branch
service
queue_type
booking_source
checked_in_at
people_ahead
open_counter_count
serving_count
baseline_estimated_wait_seconds
```

Later events add labels:

```text
actual_wait_seconds
wait_variance_seconds
service_target_seconds
actual_service_seconds
service_variance_seconds
```

The exported dataset excludes personally identifiable/protected profile attributes.

---

## 16. Tests and CI

Day 61 added focused test gates:

```bash
python manage.py test smartq.test_day61_busy_day_simulation
python manage.py test smartq.test_day61_busy_day_readiness
```

The main GitHub Actions workflow also includes the Day 61 simulation regression gate before running the full Django suite.

---

## 17. Security and Safety Decisions

### Production execution is blocked

All busy-day management commands check `IS_PRODUCTION`.

### Synthetic customers do not need usable passwords

The scenario users exist to exercise the real domain model, not to act as real sign-in accounts.

### Manager password is not committed

The optional observer password is read from:

```text
SMARTQ_TRAINING_MANAGER_PASSWORD
```

### Dedicated branch isolation

The automated workload runs only against:

```text
ML01 - Smart Q Training Branch
```

This prevents the simulator from consuming real queue traffic from another branch.

### PII-minimised forecasting export

Training export excludes names, emails, phone numbers, dates of birth, gender, disability and pregnancy attributes.

---

## 18. Engineering Lessons

### Lesson 1 - A useful simulation should exercise production logic

A synthetic scenario is most valuable when it proves the real queue workflow, not when it bypasses it.

### Lesson 2 - Prediction and outcome must remain separate

The baseline target must not be overwritten by the observed result. The difference between the two is the learning signal.

### Lesson 3 - Reproducible randomness is better than uncontrolled randomness

The workload needs variation for useful learning data, but developers also need repeatable behaviour for debugging.

### Lesson 4 - Counter availability must follow reality

A counter becomes free when service actually finishes. Keeping it blocked until a planned target expires would falsify queue behaviour and corrupt training observations.

### Lesson 5 - Idle time is informative

If a counter is free and nobody is waiting, that is genuine operational evidence. A model should eventually learn the difference between idle capacity and service delay.

### Lesson 6 - Synthetic data still needs isolation and security boundaries

Training tooling should never be allowed to silently affect production or real customer records.

---

## 19. What Day 61 Does Not Claim

Day 61 does **not** mean Smart Q has an active production ML model.

The current live ETA remains deterministic. Day 61 creates labelled evidence that can later be used to evaluate whether a statistical or machine-learning model can outperform the deterministic baseline.

---

## 20. Next Engineering Step

After exporting the completed Day 61 data, the next modelling phase should be evidence-driven:

```text
1. inspect dataset quality and missingness
2. measure baseline MAE and bias
3. inspect wait/service residual distributions
4. split observations chronologically
5. build simple statistical/classical ML baselines
6. compare them against Smart Q deterministic ETA
7. test a neural network only if data volume and non-linearity justify it
8. deploy only if the model is measurably better and operationally safe
```

---

## 21. Day 61 Completion Statement

Day 61 is complete.

The 80-customer real-time busy-day simulation ran through the Smart Q queue lifecycle and finished with all 80 synthetic customers processed. The final run demonstrated early, exact and late service completions, immediate counter reuse, proper General/Priority separation, and forecasting-ready target-vs-outcome measurements.

This is the first full operational dataset-generation day for Smart Q's forecasting research.
