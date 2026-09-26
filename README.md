# Smart Q

## Where Time Meets Priority

Smart Q started with a simple question:

> Why should a person lose hours of their day standing in a physical queue just to keep their place?

At the beginning there was no dashboard, no API, no queue engine, no machine-learning model and no polished frontend. There was only the problem.

People arrive at service centres without knowing how long they will wait. Staff often work with limited visibility. Managers need to understand what is happening across counters and services. Priority customers need fair treatment without forcing staff to manually decide who should move ahead. When something changes, such as a counter closing or a booking being disrupted, the whole queue can become confusing very quickly.

I built Smart Q to turn that uncertainty into a system.

My goal was not to make a booking page and call it a queue system. I wanted to build the **backend engine first**: the part that owns the queue rules, protects the workflow, assigns priority, controls counters, records events, measures waiting time and later gives machine learning clean data to learn from.

The project grew from a basic Django queue model into a full queue-intelligence platform with five user roles, live queue operations, real-time ETA calculation, forecasting data, a 100,000-row ML dataset and an integrated XGBoost waiting-time model.

---

# What Smart Q is today

Smart Q is a Django + Django REST Framework + React + TypeScript queue-management and queue-intelligence system.

It supports:

- appointments;
- registered and guest walk-ins;
- online and staff-assisted check-in;
- automatic queue numbering;
- automatic General / Priority lane assignment;
- live queue position;
- counter operations;
- Reception workflows;
- Branch Manager operations;
- System Admin configuration;
- cancellations and rescheduling;
- disruption recovery;
- audit history;
- deterministic ETA;
- XGBoost-assisted waiting-time prediction;
- prediction-versus-outcome logging;
- forecasting and ML quality reporting.

I currently support five roles:

| Role | What I built for the role |
|---|---|
| Customer | Register, sign in, book, reschedule, cancel, check in, join a walk-in queue, follow queue position and ETA, view history |
| Receptionist | See branch arrivals, search customers, check customers in, create guest walk-ins and see the live waiting queue |
| Counter Staff | Open/pause/resume/close an assigned counter, call next, complete service and mark no-shows |
| Branch Manager | See live branch operations, counters, staffing, history, forecasting quality and operational controls |
| System Admin | Manage branches, services, staff, counters and system-wide configuration |

---

# Why the backend mattered so much to me

One of the biggest lessons I learned while building Smart Q was that the frontend should **show the rules**, not own the rules.

For example, a Customer should not be able to choose whether they are Priority. A Counter Staff member should not be able to call a customer from the wrong branch or wrong lane. A user should not be able to change queue position from the browser.

Those rules belong to the backend.

That is why I spent so much of the project grinding on Django models, services, transactions, permissions, APIs and regression tests before treating the frontend as the main product.

The main queue lifecycle is backend-controlled:

```text
APPOINTMENT / WALK-IN
        |
        v
CHECK-IN
        |
        v
WAITING
        |
        v
CALL NEXT
        |
        v
SERVING
   +----+----+
   |         |
COMPLETED  NO_SHOW
```

For appointments I also separate **check-in time** from **service eligibility**.

A customer may check in early, but that does not mean the system may call them before the booked appointment time.

Walk-ins become eligible at check-in.

---

# Priority is a system rule, not a button

Smart Q automatically assigns the queue lane.

The current priority rule is:

```text
age >= 55
OR disability status
OR female + pregnancy for the visit
```

The Customer and Receptionist do not manually choose General or Priority.

I designed it this way because priority should be consistent and backend-enforced.

I also keep protected personal details out of forecasting/ML exports. The ML data only needs the resulting queue lane, not the private reason why somebody received priority.

---

# My development journey

## Stage 1 — From nothing to a queue engine

### Day 1 — The problem and the direction

Smart Q started as an idea and an engineering problem.

I first had to answer basic questions:

- What exactly is a queue in software?
- What is a booking?
- When does somebody officially enter a queue?
- Who decides priority?
- Who owns the queue number?
- What happens when somebody is called?
- What happens when a counter closes?
- How do I stop the frontend from breaking the rules?

My direction became clear very early:

> build the queue rules correctly first, then build the interfaces around them.

### Day 2 — Queue model and admin foundation

I created the early queue data model and used Django Admin to inspect and manage the data while the product was still very small.

This gave me my first working backend foundation.

### Day 3 — Views, URLs, templates and QuerySets

I learned how the Django request flow connected the model to the rest of the application.

I worked with:

- views;
- URLs;
- templates;
- QuerySets.

This was where Smart Q started moving from stored data to actual application behaviour.

### Day 4 — I corrected the design

I changed two important ideas:

1. queue numbers should be generated by the system;
2. priority should be decided by the system.

This was an important engineering change because I stopped treating the queue as user-entered data and started treating it as a controlled workflow.

### Day 5 — Branches, services and bookings

I added the organisational structure around the queue:

- Branch;
- Service;
- Booking.

A queue only makes sense when the system knows **where** the customer is going and **what** they are going there for.

### Day 6 — Automatic QueueTicket and queue numbers

I connected bookings to actual queue tickets and automatic numbering.

The backend became responsible for creating the queue identity instead of expecting a user to type one.

### Day 7 — Priority logic

I moved priority into the domain logic.

This meant the application could place a customer into the correct queue lane consistently.

---

## Stage 2 — Turning the backend into an API

From Day 20 onward I moved the project deeper into Django REST Framework.

I wanted Smart Q to become a real web application rather than a collection of Django pages.

Important API milestones included:

- booking creation;
- booking list/detail;
- cancellation;
- ownership checks;
- queue operations;
- role-aware API access.

By Days 28–40 the backend had become a much more complete operational engine.

| Day | Main milestone |
|---|---|
| 28 | Operational core |
| 29 | Authentication and roles |
| 30 | Check-in workflow |
| 31 | Reception walk-ins |
| 32 | Branch / service capacity |
| 33 | Counter lifecycle |
| 34 | Manager dashboard backend |
| 35 | Disruption and rescheduling |
| 36 | QueueEvent audit history |
| 37 | Admin security |
| 38 | Production hardening |
| 39 | Reporting and performance |
| 40 | Final backend audit |

By the end of this stage I had moved away from “can I make this feature work?” toward:

> can this feature work safely when different roles, branches, counters and queue states interact?

---

## Stage 3 — Building the frontend around the engine

Days 41–50 were the frontend roadmap.

I used React and TypeScript to build role-specific workspaces instead of one giant dashboard.

| Day | Frontend milestone |
|---|---|
| 41 | React frontend foundation |
| 42 | Authentication and application shell |
| 43 | Customer dashboard |
| 44 | Booking experience |
| 45 | Reception workspace |
| 46 | Counter Staff workspace |
| 47 | Branch Manager workspace |
| 48 | System Admin workspace |
| 49 | History, reporting and recovery |
| 50 | Frontend release audit |

The important lesson here was that a clean UI is not just about making things look modern.

Each role should see **the information needed to do the job**, not the entire database.

---

## Stage 4 — Making the workflows feel like one system

The next work was less about adding pages and more about fixing how people coordinate.

### Day 51

I simplified the Customer / Reception / Counter workflow.

I removed unnecessary engineering information from user-facing screens and focused on the handoff between roles.

### Day 52

I improved live Customer state and Admin controls.

### Day 53

I re-engineered the React + TypeScript frontend.

### Day 54

I cleaned up the public UI and role workspaces.

### Days 55–56

I hardened authentication, sessions, CSRF and logout behaviour.

### Day 57

I completed counter creation and Manager staffing workflows.

At this stage Smart Q felt less like separate dashboards and more like one operational system.

---

# Real-time ETA — Day 58

At first, ETA could have been something simple like:

```text
people ahead × average service time
```

But that is not good enough when several counters are working in parallel.

I rebuilt the deterministic ETA to consider:

- customers already being served;
- remaining service target time;
- waiting customers ahead;
- open counters for the correct lane;
- idle counters;
- parallel counter availability;
- appointment service eligibility.

Smart Q stores exact timing evidence such as:

```text
service_started_at
service_completed_at
service_target_seconds
actual_service_seconds
service_variance_seconds
```

The user sees simple minutes.

The backend keeps the detailed timing evidence.

---

# Forecasting data — Day 59

Machine learning needs labelled data.

So before training ML, I built `QueueForecastObservation`.

At check-in I record information that is known **before** the outcome.

Later, when the customer is called or completes service, I record what actually happened.

That gave me the structure:

```text
queue state at prediction time
        +
prediction
        +
actual outcome later
        =
training / evaluation evidence
```

This was important because I did not want to build an ML model using information from the future.

That would be data leakage.

---

# Simulation — Day 61

Before I had a large ML dataset, I wanted to prove that Smart Q could survive a realistic operating flow.

I built a controlled busy-day simulator.

The successful Day 61 run used:

```text
80 customers
72 General
8 Priority

3 counters
- 2 General
- 1 Priority

Services
- Collections
- ID Applications
- Passport Applications

Appointments from 08:00 to 15:45
```

The simulator exercised the real lifecycle:

```text
booking becomes due
        ↓
check-in
        ↓
waiting
        ↓
matching counter calls next
        ↓
serving
        ↓
complete
        ↓
actual wait/service evidence stored
```

All **80 customers were processed successfully**.

I also allowed service times to finish early, on target or late.

For example, if a 15-minute service actually took 8 minutes, the counter became free after 8 minutes. I did not artificially reserve the unused 7 minutes.

### A failed simulation also taught me something useful

Not every experiment became valid training data.

A later 110-customer attempt exposed problems with unrealistic arrivals, early appointment eligibility and wall-clock downtime contaminating timing labels.

I rejected that experiment instead of pretending the data was good.

That failure directly influenced later fixes:

- I separated check-in from service eligibility;
- I became stricter about simulation timing;
- I stopped treating every generated run as valid ML evidence.

That was one of the most useful engineering lessons in the whole project.

---

# Machine learning

## Why I added ML

The deterministic ETA is useful because it is understandable and reliable.

But queues are nonlinear.

Waiting time is affected by combinations of:

- people ahead;
- workload ahead;
- available counters;
- queue pressure;
- recent service speed;
- recent waiting behaviour;
- arrival timing;
- branch/service conditions.

I wanted to test whether a learned model could improve on the deterministic estimate.

---

## The dataset

I built a **100,000-row synthetic Smart Q operational dataset**.

It contains **45 columns** and represents:

- appointments;
- walk-ins;
- General and Priority queues;
- multiple branches;
- multiple services;
- cancellations;
- no-shows;
- arrival timing;
- active counters;
- queue pressure;
- recent queue history;
- waiting-time outcomes;
- service-time outcomes.

The complete dataset is submitted in this repository:

```text
machine_learning/repository_snapshot/data/
└── SmartQ_Synthetic_Operational_Dataset_100k.csv
```

I clearly treat this as **synthetic data**.

The current model proves the ML process and integration. It does not prove that the same accuracy is guaranteed in a real organisation.

---

## The three models I trained

My proposal required:

1. Linear Regression;
2. Random Forest;
3. XGBoost.

I trained all three using the same chronological data split.

I also kept:

- a mean-wait baseline;
- the existing deterministic Smart Q ETA.

### Why chronological splitting mattered

I did not randomly mix all dates together.

I trained on earlier dates and validated/tested on later dates.

That better matches the real question:

> can a model learn from past queue behaviour and predict later queue behaviour?

---

# Model performance

## Validation results

| Model | MAE | RMSE |
|---|---:|---:|
| Linear Regression | 4.1146 min | 6.1452 min |
| Random Forest | 2.6315 min | 4.4920 min |
| **XGBoost** | **2.6302 min** | **4.3893 min** |

My selection rule was decided before the final test:

> lowest validation MAE wins.

That selected **XGBoost**.

Random Forest and XGBoost were extremely close.

## Final test results

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Linear Regression | 4.0645 min | 6.4606 min | 0.9313 |
| Random Forest | **2.5231 min** | **4.6425 min** | **0.9645** |
| Selected XGBoost | 2.5824 min | 4.9561 min | 0.9596 |

Random Forest happened to have a slightly lower **final test MAE**.

I did **not** switch models after seeing that result.

If I changed the winner using the final test result, I would be using the test set for model selection.

I kept XGBoost because it won according to the validation rule I had already defined.

That decision mattered more to me than chasing a tiny post-test improvement.

---

# Model diagnostics

I did not stop at MAE and RMSE.

I also checked:

- R²;
- adjusted R²;
- residuals;
- p-values for Linear Regression;
- confidence intervals;
- heteroscedasticity;
- VIF / multicollinearity;
- permutation importance;
- TreeSHAP;
- performance during Low / Moderate / Busy traffic.

The biggest predictive signals included:

- workload minutes ahead;
- people ahead;
- arrival timing;
- effective open counters;
- queue pressure.

The biggest weakness was severe congestion.

XGBoost test MAE was approximately:

```text
Low traffic       1.22 min
Moderate traffic  2.95 min
Busy traffic      7.94 min
```

I keep that weakness visible because the point of diagnostics is to understand where the model struggles, not hide it.

---

# Integrating XGBoost into Smart Q

Training a model in a notebook was not enough.

I integrated the actual model into Django.

The runtime model is stored at:

```text
machine_learning/runtime/smartq_wait_time_model.joblib
```

The live prediction path now works like this:

```text
Customer joins / checks queue
        ↓
Django reads current queue state
        ↓
I build the 22 ML input features
        ↓
I check important inputs against the training domain
        ↓
saved preprocessing is applied
        ↓
XGBoost predicts waiting time
        ↓
prediction returned through the existing queue API
```

I load the model once per process instead of reading the file for every request.

I also keep the deterministic ETA as a fallback.

If:

- the model cannot load;
- ML is disabled;
- prediction fails;
- the current queue state is too far outside the training domain;

Smart Q still returns the deterministic estimate.

The runtime can be disabled without changing code:

```text
SMARTQ_ML_ENABLED=false
```

---

# Measured ML runtime performance

I measured the integrated Django prediction path in GitHub Actions.

```text
Cold prediction: 0.924552 seconds
Warm prediction: 0.018159 seconds
Requirement:     below 2 seconds
```

Both passed.

The machine-readable result is stored at:

```text
machine_learning/runtime/latency_benchmark.json
```

---

# Prediction versus real outcome

The integration does not only predict and forget.

I extended forecasting observations to keep:

- deterministic estimate;
- ML estimate;
- prediction model;
- prediction time;
- actual waiting time later;
- deterministic residual;
- ML residual.

That means Smart Q can eventually answer:

> how accurate is the model on real operational data?

This is the bridge between the current synthetic research model and a future real-data model.

---

# Technology stack

| Area | Technology / tool |
|---|---|
| Backend | Python, Django 6 |
| API | Django REST Framework |
| Frontend | React 18, TypeScript |
| Frontend build | Vite 5 |
| Routing | React Router 6 |
| Server-state | TanStack Query 5 |
| Authentication | Django sessions + CSRF |
| Database | SQLite3 for current development/submission environment |
| ML/data | pandas, NumPy |
| ML models | scikit-learn, XGBoost |
| Model packaging | joblib |
| ML statistics/diagnostics | scikit-learn + statistical diagnostic tooling in the ML snapshot |
| Testing | Django TestCase / DRF tests, TypeScript checks, Vite build |
| Automation | GitHub Actions |
| Development | Git, GitHub, GitHub Codespaces / local environment |

---

# Architecture

```text
React + TypeScript
        |
        v
Django REST Framework
        |
        v
Authentication / permissions / ownership
        |
        v
Domain services + transactions
        |
        +-----------------------------+
        |                             |
        v                             v
Queue / Booking / Counter       ML feature builder
        |                             |
        v                             v
Django ORM                    XGBoost runtime model
        |                             |
        +-------------+---------------+
                      |
                      v
         Prediction + actual outcomes
                      |
                      v
              Reporting / learning
```

The main Django apps are:

```text
accounts
branches
services
bookings
queues
counters
notifications
rescheduling
dashboard
```

---

# Testing philosophy

I did not want “it works on my screen” to be the quality standard.

I used regression tests and GitHub Actions throughout the project.

The final repository checks include:

- frontend TypeScript build;
- Django system checks;
- migration checks;
- role and permission tests;
- booking and queue workflow tests;
- Reception tests;
- Counter lifecycle tests;
- Manager/Admin tests;
- ETA tests;
- forecasting tests;
- simulation tests;
- packaged XGBoost loading;
- exact ML feature-contract tests;
- live Customer queue API prediction;
- deterministic fallback tests;
- out-of-training-domain fallback tests;
- appointment service-eligibility tests;
- prediction-versus-outcome logging tests;
- latency tests;
- complete Django test suite.

At the end of the ML integration, the work was merged into `main` only after the focused ML integration suite and the complete Django regression suite passed.

---

# The final roadmap

| Stage | What I completed |
|---|---|
| Days 1–7 | Problem definition, queue model, system-owned numbering, branches/services/bookings, QueueTicket and priority rules |
| Days 20–27 | Django REST Framework and booking API foundation |
| Days 28–40 | Operational backend, roles, check-in, Reception, capacity, counters, Manager, disruptions, audit, security and backend hardening |
| Days 41–50 | React/TypeScript role workspaces and frontend release |
| Days 51–57 | Workflow simplification, live state, frontend reengineering, auth/session hardening, counter staffing |
| Day 58 | Real-time deterministic ETA and service timing |
| Day 59 | Forecasting observation / labelled-data foundation |
| Day 60 | Workspace cleanup |
| Day 61 | Successful 80-customer live busy-day simulation |
| ML research | 100k dataset, EDA, data preparation, Linear Regression, Random Forest, XGBoost, diagnostics |
| ML integration | Packaged XGBoost model, live 22-feature builder, API integration, fallback, logging and latency testing |
| Final state | Full system + ML integration merged to `main` |

Detailed milestone documents are under:

```text
docs/
```

---

# How to run Smart Q in GitHub Codespaces

This is the quickest way to inspect the complete project.

## 1. Open a Codespace on `main`

Open the repository in GitHub and create a Codespace.

Then in the Codespace terminal:

```bash
git checkout main
git pull origin main
```

## 2. Install Python dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Build the React frontend

```bash
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..
```

## 4. Prepare the database and demo data

```bash
python manage.py migrate
python manage.py bootstrap_demo
```

## 5. Start Smart Q

```bash
python manage.py runserver 0.0.0.0:8000
```

Open the forwarded **port 8000**.

Smart Q automatically trusts the active Codespaces development hostname for the forwarded port.

---

# How to run Smart Q locally

Recommended environment:

```text
Python 3.12
Node.js 22
Git
```

## 1. Clone the repository

```bash
git clone https://github.com/Katlegojack/SmartQ.git
cd SmartQ
```

## 2. Create a Python virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install backend dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Install and build the frontend

```bash
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..
```

## 5. Run migrations and create demo data

```bash
python manage.py migrate
python manage.py bootstrap_demo
```

## 6. Run the application

```bash
python manage.py runserver 0.0.0.0:8000
```

Then open:

```text
http://127.0.0.1:8000
```

---

# Demo accounts

For local development and Codespaces only, `bootstrap_demo` creates these accounts.

All demo accounts use:

```text
SmartQDemo2026!
```

| Username | Role |
|---|---|
| `customer_demo` | Customer |
| `reception_demo` | Receptionist |
| `counter_demo` | Counter Staff |
| `manager_demo` | Branch Manager |
| `admin_demo` | System Admin |

When testing several roles at the same time, use separate browser profiles or incognito windows because one browser profile shares one Django session cookie.

---

# Useful development commands

## Run the full Django test suite

```bash
python manage.py test
```

## Check for missing migrations

```bash
python manage.py makemigrations --check --dry-run
```

## Django system check

```bash
python manage.py check
```

## Frontend type check

```bash
cd frontend
npm run typecheck
```

## Frontend production build

```bash
cd frontend
npm run build
```

## Rebuild the Day 61 simulation data

```bash
python manage.py seed_busy_day --date 2026-09-07 --customers 80 --reset
python manage.py verify_busy_day --date 2026-09-07 --customers 80
```

Run the simulator in another terminal while Django is running:

```bash
python manage.py run_busy_day --date 2026-09-07
```

---

# Repository layout

```text
SmartQ/
├── accounts/
├── bookings/
├── branches/
├── counters/
├── dashboard/
├── notifications/
├── queues/
├── rescheduling/
├── services/
├── frontend/
├── docs/
├── machine_learning/
│   ├── repository_snapshot/
│   │   ├── data/
│   │   ├── notebooks/
│   │   ├── docs/
│   │   ├── results/
│   │   ├── src/
│   │   └── .project-notes/
│   └── runtime/
│       ├── smartq_wait_time_model.joblib
│       ├── latency_benchmark.json
│       └── requirements.txt
├── manage.py
├── requirements.txt
└── README.md
```

---

# Where Smart Q can go next

The current project is complete for the scope I built, but I see this as the beginning of Smart Q rather than the end.

The biggest next step is **real operational data**.

The current XGBoost model was trained on synthetic data. A real pilot would let Smart Q collect prediction-versus-outcome records and answer:

- does the model stay accurate in a real branch?
- where does model drift appear?
- which services behave differently in practice?
- how does staffing affect wait time?
- when should the model be retrained?

From there I would move toward:

- a production database such as PostgreSQL;
- cloud deployment with persistent storage;
- real organisation pilot testing;
- model monitoring and scheduled retraining;
- an explicit physical-arrival timestamp so live ML features match training definitions even more closely;
- stronger operational analytics;
- integrations with existing organisational systems instead of forcing every organisation to replace what it already uses;
- multi-organisation support;
- larger-scale capacity planning and forecasting;
- customer notification channels around queue movement and disruptions.

My long-term idea is bigger than replacing a paper ticket.

I want Smart Q to become an operational intelligence layer around waiting: one that helps customers protect their time and helps organisations understand the queues they are creating.

---

# What I learned as a software engineer

This project changed how I think about software.

I learned that the difficult part is rarely the button.

The difficult part is deciding what that button is **allowed to do**, what happens if two users act at the same time, what data should exist before an action is valid, how the system recovers from failure and how I prove that a new feature did not break an old one.

I learned to care about:

- domain modelling;
- backend ownership of rules;
- permissions;
- transactions;
- state machines;
- API contracts;
- frontend simplicity;
- test coverage;
- reproducibility;
- data leakage;
- model evaluation;
- failed experiments;
- fallback behaviour;
- documentation;
- honest limitations.

Smart Q started as a queue project.

It became the project where I learned how the different parts of software engineering actually meet each other.

---

# Final status

```text
Backend engine                       COMPLETE
Role-based API                       COMPLETE
React/TypeScript frontend            COMPLETE
Customer workflow                    COMPLETE
Reception workflow                   COMPLETE
Counter workflow                     COMPLETE
Branch Manager workflow              COMPLETE
System Admin workflow                COMPLETE
Real-time deterministic ETA          COMPLETE
Forecasting observation pipeline     COMPLETE
Busy-day simulation                  COMPLETE
100k ML dataset                      COMPLETE
EDA + data preparation               COMPLETE
Linear Regression                    COMPLETE
Random Forest                        COMPLETE
XGBoost                              COMPLETE
Model diagnostics                    COMPLETE
Runtime model packaging              COMPLETE
Django ML integration                COMPLETE
Deterministic ML fallback            COMPLETE
Prediction/outcome logging           COMPLETE
Latency requirement                  PASS
Regression test suite                PASS
Final integration merge to main      COMPLETE
```

---

# Author

**Katlego Mmako**

Smart Q — **Where Time Meets Priority**
