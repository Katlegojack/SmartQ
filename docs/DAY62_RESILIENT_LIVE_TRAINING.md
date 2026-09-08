# Smart Q — Day 62 Resilient Live Training

**Target live date:** Wednesday, 9 September 2026  
**Operating window:** 09:00–18:00  
**Branch:** `ML01 — Smart Q Training Branch`  
**Status:** implementation/preflight milestone; live run not yet declared complete

## Goal

Day 62 keeps the Day 61 real-time training philosophy and adds controlled operational disturbances without bypassing Smart Q's real queue domain.

The seeded workload remains made of normal Django users, bookings, queue tickets, queue events, counters and forecasting observations. Customer and Reception walk-ins are not fake simulator rows: they enter the same live queue and can change the waiting experience of everybody else.

No machine-learning model is enabled by this milestone. Smart Q is still collecting labelled evidence for later statistical/ML evaluation.

## Scenario shape

```text
110 seeded appointments
├── 99 General
└── 11 Priority

10 deterministic-random seeded absences
100 seeded customers expected to attend

PLUS any live extras during the day:
├── registered Customer joins
└── Reception guest walk-ins
```

The extras are outside the 110. If two extra customers join and all planned attendance behaves as expected, the day would serve 102 customers while still recording 10 seeded no-shows.

## Operating day

`ML01` now uses:

```text
Opening:          09:00
Closing:          18:00
Appointment grid: 09:00 through 17:45
Slot rhythm:      15 minutes
```

The live runner remains operational through 18:00 even if the seeded batch happens to finish earlier. After 18:00 it drains customers who are already `WAITING` or `SERVING` before closing the counters.

## What remains unchanged from Day 61

- dedicated `ML01` training isolation;
- Collections, ID Applications and Passport Applications;
- the same service target families;
- early, exact and overrun actual service-duration examples;
- deterministic/reproducible scenario variation;
- normal `Booking -> QueueTicket -> QueueEvent` lifecycle;
- event-driven `QueueForecastObservation` capture;
- real target-vs-actual timing measurements;
- two General counters and one Priority counter;
- user-facing time in minutes and internal second-resolution evidence;
- production execution blocked by `IS_PRODUCTION`.

## Ten no-shows

Exactly ten of the 110 seeded appointments are selected using a date/version-seeded random generator. The selection looks irregular but is reproducible: resetting 9 September produces the same absent customers.

The opening customers are protected from the random selection so all three counters can begin with work at 09:00.

A selected absent customer behaves as follows:

```text
appointment time reached
        |
        | customer does not check in
        v
remains outside WAITING
        |
        | 10-minute grace period
        v
Booking -> NO_SHOW
QueueTicket -> NO_SHOW
QueueEvent(NO_SHOW)
        |
        v
live queue continues normally
```

A scheduled absence never occupies a counter and never blocks the next real waiting customer.

## Work-conserving Priority counter

Counter 3 is still a Priority counter. Its dispatch policy is:

```text
Counter 3 becomes free
        |
        v
Priority customer waiting?
    |             |
   YES            NO
    |             |
    v             v
serve Priority   General waiting?
                    |
                   YES
                    |
                    v
                 help General
```

Priority always wins when Counter 3 becomes free. If Counter 3 is already serving a General customer and a Priority customer arrives, the General service is not interrupted; the Priority customer gets first claim when Counter 3 next becomes available.

The live ETA calculation follows the same policy so General customers can benefit from available Priority capacity without pretending Priority demand does not exist.

The `CALLED` event records non-sensitive routing evidence:

```text
counter_queue_type
served_queue_type
priority_overflow
```

This allows later comparison of how often flexible capacity was used.

## Reception live operations

Reception remains operational rather than analytical. The workspace now refreshes queue/counter state every two seconds and shows:

```text
General waiting
Priority waiting
Serving now
Counter 1 state/current customer
Counter 2 state/current customer
Counter 3 state/current customer
Live waiting queue
Today's arrivals
Search/check-in
Add customer to live queue
```

A Reception-created walk-in goes through the existing production workflow and immediately becomes a real queue participant. The runner recognises that extra ML01 booking and completes it through the normal service lifecycle.

## Registered Customer live test

A normal Customer account can select `Smart Q Training Branch`, choose one of its services and press **Join live queue now** during the run.

That Customer is outside the seeded 110 and enters the same queue as everybody else.

The Customer workspace polls authoritative queue state every two seconds and displays:

```text
queue number
people ahead
estimated wait
waiting so far
status
```

When called, it shows the real physical counter number. ETA is refreshed from the server while `Waiting so far` increases locally from the actual check-in timestamp.

The ETA is not a fake countdown. It is recalculated as the queue changes, including service early finishes/overruns and Counter 3 helping General.

## Service-duration variation

The Day 61 duration families are retained:

| Service | Target | Example actual-duration family |
|---|---:|---|
| Collections | 10 min | 5–15 min |
| ID Applications | 15 min | 8–22 min |
| Passport Applications | 20 min | 12–30 min |

Seeded customers receive reproducible service durations. Live extra bookings use the same duration families and a stable booking/date seed so the automated runner can complete them too.

## Security/isolation

- `seed_resilient_day`, `verify_resilient_day` and `run_resilient_day` refuse production execution.
- Synthetic customer accounts have unusable passwords.
- Observer passwords are supplied only through local environment variables.
- No training password is committed to Git.
- `ml_manager` is scoped to ML01 as Branch Manager.
- `ml_receptionist` is scoped to ML01 as Receptionist.
- Training dataset export remains PII-minimised.

## Prepare the Codespace

```bash
git checkout main
git pull origin main
pip install -r requirements.txt

cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

python manage.py migrate
```

Use Django forwarded port **8000**. Do not use Vite port 5173 as the product entry point.

## Optional local observer credentials

Set local temporary passwords **before seeding** if the Manager and Reception workspaces will be observed:

```bash
export SMARTQ_TRAINING_MANAGER_PASSWORD='choose-a-local-temporary-password'
export SMARTQ_TRAINING_RECEPTION_PASSWORD='choose-a-local-temporary-password'
```

Do not commit those values.

## Seed the 9 September scenario

```bash
python manage.py seed_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10 \
  --reset
```

Expected structural shape:

```text
110 seeded appointments
99 General
11 Priority
10 planned deterministic no-shows
3 counters
09:00-18:00 ML01 branch hours
09:00-17:45 appointment grid
```

## Mandatory preflight

```bash
python manage.py verify_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10
```

Do not arm the live runner if preflight reports a blocking error.

Expected final line:

```text
READY: Day 62 is structurally ready for the 09:00 resilient live training run.
```

## Live run

Terminal 1:

```bash
python manage.py runserver 0.0.0.0:8000
```

Terminal 2, before 09:00:

```bash
python manage.py run_resilient_day \
  --date 2026-09-09 \
  --customers 110 \
  --no-shows 10
```

The runner waits for 09:00 when started early.

## What to observe during the day

1. At 09:00 all three counters open and begin normal queue work.
2. Selected no-show customers never enter `WAITING`; after ten minutes they become `NO_SHOW`.
3. When Priority is empty, Counter 3 can call a General ticket.
4. If Priority arrives while Counter 3 serves General, the current General service completes normally.
5. Reception can watch both lanes/counters and add extra walk-ins.
6. A normal Customer can join ML01 as an extra and see queue position, ETA and elapsed wait change.
7. Extras receive normal queue numbers and forecasting observations.
8. The runner remains open through 18:00 and drains active work after closing time.

## Regression gate

```bash
python manage.py test smartq.test_day62_resilient_live_training
```

CI also type-checks/builds the React frontend and runs the full historical Django suite.

## Export after the live day

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-09 \
  --end-date 2026-09-09 \
  --output smartq_training_2026-09-09.csv
```

Do not call Day 62 complete merely because the code merged. The milestone closes only after the real 9 September run is observed and its outcome/data are verified.

## Later comparison with Day 61

No analytics dashboard is part of Day 62. After data collection, September 7 and September 9 can be compared offline using normalized operational measures such as customers served per hour, wait distribution, counter utilisation, Priority-counter General assists and total operating duration. The raw total duration alone is not a fair comparison because the workloads differ.
