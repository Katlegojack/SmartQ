# Smart Q — Day 61 Tomorrow Runbook

Target live simulation date: **Monday, 7 September 2026**.

This runbook is intentionally short and operational. The goal is to make tomorrow boring from an engineering perspective: prepare the scenario, verify it, start the web app, arm the simulator before 08:00, watch the queues move, and export the observations after the day.

## 1. Update the Codespace

```bash
git checkout main
git pull origin main

cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

python manage.py migrate
```

Do not use Vite port 5173 as the product entry point. Smart Q should be opened from Django port 8000.

## 2. Optional Branch Manager observer login

No training password is stored in Git.

If you want to watch the dedicated `ML01` branch through the Branch Manager workspace, choose a temporary local password in the Codespace terminal before seeding:

```bash
export SMARTQ_TRAINING_MANAGER_PASSWORD='choose-a-local-temporary-password'
```

The variable exists only in that shell/session unless you deliberately persist it. Do not commit it to a file.

If this variable is omitted, the simulator still works; the `ml_manager` observer account simply receives an unusable password.

Observer username:

```text
ml_manager
```

## 3. Seed exactly 80 customers

Run this once after the final Day 61 code is on `main`:

```bash
python manage.py seed_busy_day \
  --date 2026-09-07 \
  --customers 80 \
  --reset
```

Expected shape:

```text
80 customers
72 General
8 Priority
2 General counters
1 Priority counter
3 services
appointments from 08:00 through 15:45
```

The synthetic customer accounts have unusable passwords and do not need to be opened manually.

## 4. Run the preflight verifier

This is mandatory before arming the live simulator:

```bash
python manage.py verify_busy_day \
  --date 2026-09-07 \
  --customers 80
```

Do not proceed if the command prints a blocking error.

The expected final line is:

```text
READY: the Smart Q busy-day scenario is structurally ready for the 08:00 live run.
```

The verifier checks the customer count, 72/8 queue split, required time checkpoints, three staffed counters, 2-General/1-Priority counter split, clean scheduled state, absence of premature forecast labels, the 08:00 starting mix, service-duration variation, and the training manager's branch scope.

## 5. Start Django in Terminal 1

```bash
python manage.py runserver 0.0.0.0:8000
```

Open forwarded port **8000** and keep the Codespace active.

## 6. Arm the live simulator in Terminal 2 before 08:00

Recommended time: approximately 07:50–07:55.

```bash
python manage.py run_busy_day --date 2026-09-07
```

When started early, it waits for 08:00.

At 08:00 it opens all three counters and begins processing the first two General customers plus one Priority customer. Later appointments enter at their scheduled times.

Do not close Terminal 2 while the simulation is running.

## 7. What to watch in the UI

The important verification is not the terminal text alone. Keep Smart Q open and watch operational state change.

Confirm during the day that:

- queue counts increase when scheduled customers arrive;
- two General counters and one Priority counter are open;
- counters change between free and serving states;
- waiting customers are called automatically;
- the customer-facing wait estimate changes as services finish early or late;
- service durations remain displayed in minutes in the UI;
- completed customers leave the active queue;
- Manager/Admin operational metrics move with the queue;
- the queue continues without manual Counter Staff clicks.

## 8. Service-time variation is intentional

Smart Q starts with service baselines, but actual synthetic service time differs per visit.

Examples include early, exact and late completions. A 10-minute service may take 5, 8, 10, 13 or 15 minutes. The actual duration is not rounded back to the baseline.

Internally, Smart Q retains exact timestamps and second-resolution measurements so the future model can learn prediction error. User-facing duration remains expressed in minutes.

## 9. End-of-day checks

The runner exits only after all 80 synthetic bookings are completed, then attempts to close all three training counters.

After completion, verify the forecasting dataset exists for the date:

```bash
python manage.py export_forecasting_dataset \
  --start-date 2026-09-07 \
  --end-date 2026-09-07 \
  --output smartq_training_2026-09-07.csv
```

The exported data should contain operational features and labels while excluding customer names, email, phone, DOB, pregnancy and disability attributes.

## 10. Failure handling tomorrow

If the web UI is unavailable but Terminal 2 is still processing, do not immediately reset the database. Restart only the Django web server first.

If the simulator itself stops, capture the terminal error before changing anything. Do not run `--reset` after 08:00 unless we deliberately decide to discard that day's partial observations.

If a Codespace suspension occurs, resume the Codespace and inspect existing queue state before deciding whether to restart the simulator. The runner is written to ignore already checked-in bookings and already-completed visits, but partial-day data should be inspected before making destructive changes.

## 11. Why tomorrow matters

Tomorrow is not supposed to prove that 80 observations are enough for a production ML model. It proves that Smart Q can generate trustworthy queue observations through a realistic operating day.

The week can then expand the evidence across different loads, staffing patterns, services and queue conditions. The model comes after the data pipeline has earned our trust.
