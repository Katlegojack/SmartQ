# Smart Q — Day 61 Busy-Day ML Simulation

## Goal

Day 61 creates a controlled synthetic operating day that behaves like a real busy branch so Smart Q can collect prediction-vs-outcome observations before any machine-learning model is trained.

The scenario is deliberately operational rather than a CSV-only generator: customers have bookings, queue tickets, queue types, check-in events, counter service starts, service completions, actual waiting times and actual service-duration residuals. This means the Day 59 forecasting observation pipeline receives data through the same queue events used by the real product.

## Target run

The first planned run is Monday, 7 September 2026.

```bash
python manage.py seed_busy_day --date 2026-09-07 --customers 80 --reset
python manage.py run_busy_day --date 2026-09-07
```

The simulator is disabled when `IS_PRODUCTION` is true.

## Scenario shape

- 80 synthetic customer accounts.
- The synthetic customers use unusable passwords because nobody needs to sign in as them.
- Exactly 10% of the 80 customers are routed to the priority lane: 8 priority and 72 general.
- Priority status is produced through the normal Smart Q policy using a mixture of age, disability and pregnancy conditions rather than directly forcing the ticket type.
- All 80 customers belong to one synthetic branch: `ML01 — Smart Q Training Branch`.
- Three Counter Staff accounts are prepared for that branch.
- Counter 1 is General.
- Counter 2 is General.
- Counter 3 is Priority.
- The counters remain closed after seeding and are opened automatically by the live simulator at 08:00.

## Appointment distribution

Appointments are spread between 08:00 and 15:45 using 15-minute appointment points. For 80 customers this naturally creates a denser morning because the available slot list is repeated.

Important checkpoint times such as 08:00, 10:00, 11:00 and 14:00 are guaranteed to contain appointments.

At 08:00 the first group contains two General customers and one Priority customer so all three counters can begin work immediately.

## Services

The scenario uses three service families:

| Service | Baseline target |
| --- | ---: |
| Collections | 10 min |
| ID Applications | 15 min |
| Passport Applications | 20 min |

The baseline is not treated as the truth. It is the prediction target Smart Q begins with.

## Service-time variation

Each visit receives a reproducible but varied actual-duration plan. This is intentionally different from simply adding random noise after the day has finished.

Collections use values such as:

```text
5, 6, 8, 9, 10, 11, 13, 15 minutes
```

ID Applications use values such as:

```text
8, 10, 12, 14, 15, 17, 19, 22 minutes
```

Passport Applications use values such as:

```text
12, 15, 17, 19, 20, 23/24, 27, 30 minutes
```

The exact ordering is deterministic for the scenario date so restarting the simulator does not silently assign a different intended duration to the same customer.

This gives Smart Q examples that finish early, exactly on target and late for every service.

## Why reproducible randomness matters

Pure randomness would make debugging difficult. If customer A took 8 minutes on one run and 17 minutes after a restart, the resulting dataset would be harder to reason about.

The Day 61 design therefore uses varied sequences with a deterministic date/service rotation. The day looks irregular, but the same synthetic visit keeps the same intended duration when the process restarts.

## Real-time queue operation

`run_busy_day` is a long-running management command.

At 08:00 it:

1. Opens both General counters and the Priority counter.
2. Activates every appointment once its scheduled time is reached.
3. Records the normal `CHECKED_IN` queue event.
4. Calls waiting customers using the existing `call_next_ticket` queue service.
5. Starts the normal Smart Q service clock.
6. Watches the elapsed service duration internally.
7. Completes the service once that visit's planned actual duration has elapsed.
8. Immediately allows the free counter to call the next eligible customer.
9. Repeats until every synthetic booking is completed.
10. Closes the three counters at the end of the day.

The simulator heartbeat defaults to two seconds. This does not change the Smart Q UI contract: customer-facing and staff-facing durations remain expressed in minutes. Exact timestamps and seconds remain internal measurement precision for forecasting.

## Forecasting data generated

Because Day 61 uses the real queue event path, the Day 59 signal layer creates `QueueForecastObservation` rows automatically.

For each queue entry Smart Q captures information known before the outcome, including:

- branch;
- service;
- queue type;
- booking source;
- check-in time;
- people ahead;
- open counter count;
- serving count;
- baseline estimated wait.

When the customer is called Smart Q adds:

- called time;
- actual wait;
- wait prediction error;
- service target.

When the service ends Smart Q adds:

- completion time;
- actual service duration;
- service-duration variance.

Example:

```text
Service target: 10 min
Actual service: 5 min
Service variance: -5 min
```

The five saved minutes are not discarded. They become labelled evidence for later modelling.

Another example:

```text
Service target: 15 min
Actual service: 22 min
Service variance: +7 min
```

That overrun is equally important training evidence.

## Why synthetic customers are real Django users

The Day 61 customers are synthetic, but they are represented using the same User/Profile/Booking/QueueTicket relationships as normal registered customers. This matters because priority routing, queue numbering, booking ownership and forecasting hooks should be exercised under the same domain model as the live product.

The accounts use unusable passwords to avoid creating 80 unnecessary login credentials.

## Priority split

For the default 80-customer day:

```text
General:  72
Priority:  8
Total:    80
```

The priority customers are spread through the appointment order while ensuring at least one priority arrival is available at opening.

## Counter staffing

The scenario creates/refreshes three Counter Staff users:

```text
ml_counter_general_1
ml_counter_general_2
ml_counter_priority_1
```

They are assigned to counters 1, 2 and 3 respectively. The simulator performs the counter work using those users as the event actors, so queue audit history still records which counter staff identity performed the call/open/complete actions.

## Isolation

The customers are prefixed with the scenario date, for example:

```text
mlbusy_20260907_001
mlbusy_20260907_002
...
mlbusy_20260907_080
```

The scenario uses a dedicated branch so the automated runner does not accidentally consume a real customer's queue ticket from another branch.

## Reset behavior

If the same day has already been seeded, the command refuses to duplicate it unless `--reset` is supplied.

```bash
python manage.py seed_busy_day --date 2026-09-07 --customers 80 --reset
```

Reset removes the existing dated synthetic customer scenario, its related queue events/forecast observations and queue-number sequence before rebuilding it.

## Codespaces operational warning

A management command cannot run while the Codespace itself is suspended.

For an exact 08:00 live run, either:

- keep the Codespace alive overnight with the simulator process running; or
- start/reopen the Codespace before 08:00 and launch the command around 07:55.

The Django server and simulator should run in separate terminals.

Terminal 1:

```bash
python manage.py runserver 0.0.0.0:8000
```

Terminal 2:

```bash
python manage.py run_busy_day --date 2026-09-07
```

## Export after the day

Once the customers have been processed:

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-07 \
  --end-date 2026-09-07 \
  --output smartq_training_2026-09-07.csv
```

The existing Day 59 export intentionally excludes names, email addresses, phone numbers, dates of birth, pregnancy flags and disability attributes.

## Engineering lessons

### Simulation should exercise the real domain path

Writing 80 finished rows directly into a CSV would be easy, but it would not test queue allocation, counter capacity, real waiting behavior or event-driven observation capture. Day 61 instead drives the live queue.

### Baseline and outcome must remain separate

The configured service average is a prediction baseline. The actual duration is a measurement. Overwriting the baseline with every new outcome would destroy the prediction error that the later model needs to learn.

### Randomness must still be reproducible

Training data needs variation, but engineering needs repeatability. Deterministic variation gives both.

### Synthetic data must not contaminate real users

Scenario usernames are clearly prefixed, account passwords are unusable, production execution is blocked, and the automated queue is isolated to a dedicated branch.

### Real time is different from accelerated testing

Day 61 is designed to move the queue according to actual wall-clock minutes so the application UI, queue estimates and operational events behave as they would in a real branch. Unit tests separately manipulate timestamps so CI does not need to wait for hours.
