# Smart Q - Day 38 Engineering Documentation

## PostgreSQL, Concurrency and Production Hardening

## 1. Day 38 goal

Day 38 moves Smart Q from a backend that is safe for development toward one whose important database and browser-security guarantees are explicitly designed for production.

Days 28-37 established the business system: accounts and roles, booking/check-in, reception walk-ins, capacity, counter lifecycle, live queues, dashboard, disruption recovery, QueueEvent audit and System Admin controls.

Day 38 asks a different question:

```text
Will those guarantees still hold when:
- multiple requests arrive at the same time,
- PostgreSQL rather than SQLite owns the data,
- the frontend is served through a browser over HTTPS,
- secrets and infrastructure differ between deployments?
```

Day 38 does **not** change the approved product rules:

```text
Estimated Wait = People Ahead × Service.average_service_time
Check-in opens exactly 6 hours before appointment time
Priority = age >= 55 OR disability OR female + pregnancy for the visit
Branch opening time is the customer-service start boundary
```

---

## 2. Development vs production database

Local development remains intentionally simple:

```text
SMARTQ_ENV=development
DATABASE_URL absent
        ↓
SQLite
```

Production is explicit:

```text
SMARTQ_ENV=production
        ↓
DJANGO_SECRET_KEY required
DJANGO_DEBUG must be false
ALLOWED_HOSTS required
DATABASE_URL required
Database engine must be PostgreSQL
```

If those production invariants are missing, Smart Q raises `ImproperlyConfigured` rather than silently falling back to a development configuration.

### Engineering lesson

**Fail fast when the deployment cannot provide an important guarantee.**

A server refusing to start is safer than a server quietly running production traffic with SQLite, an exposed debug page or a source-controlled secret.

---

## 3. Production dependencies

Day 38 adds:

```text
psycopg[binary]
dj-database-url
django-cors-headers
```

Purpose:

```text
Psycopg 3           -> Django/PostgreSQL driver
dj-database-url     -> parse deployment DATABASE_URL
django-cors-headers -> explicit browser-origin policy
```

The additions are narrow: each dependency solves a concrete production requirement.

---

## 4. The original queue-number race

Before Day 38, queue numbers were based on the latest ticket:

```text
latest ticket = A007
next ticket   = A008
```

That is correct when requests happen sequentially.

Under concurrency:

```text
Request A reads A007
Request B reads A007
Request A calculates A008
Request B calculates A008
```

Both calculations are individually correct, but the overall operation is not atomic.

This is a classic **read-modify-write race condition**.

### Engineering lesson

Concurrency bugs often do not come from bad arithmetic. They come from several individually correct steps being interleaved by multiple requests.

---

## 5. QueueNumberSequence

Day 38 introduces an explicit database-backed allocator:

```text
QueueNumberSequence
├── branch
├── booking_date
├── queue_type
└── last_number
```

A database unique constraint owns this scope:

```text
branch + booking_date + queue_type
```

Examples:

```text
JHB / 2026-09-02 / GENERAL  -> one sequence
JHB / 2026-09-02 / PRIORITY -> separate sequence
JHB / 2026-09-03 / GENERAL  -> separate sequence
PTA / 2026-09-02 / GENERAL  -> separate sequence
```

This gives the lock a precise business meaning rather than locking an unrelated whole Branch row.

### Trade-off

A dedicated model adds a table and migration, but it keeps unrelated dates/types/branches from sharing one coarse lock.

---

## 6. The first attempted concurrency design and what PostgreSQL taught us

The first Day 38 implementation used:

```python
QueueNumberSequence.objects.select_for_update().get_or_create(...)
```

The reasoning was:

```text
unique constraint protects first row
select_for_update protects later increments
```

PostgreSQL full-suite testing exposed an important flaw during two simultaneous **first-ever** allocations.

Both transactions could reach `get_or_create()` before the row existed. Both attempted the INSERT. One won the unique constraint. The second transaction could still fail while trying to recover the newly-created row under that concurrency timing.

### Engineering lesson

**`get_or_create()` is a convenience API, not a universal concurrency primitive.**

When correctness depends on conflict behavior, make the conflict strategy explicit and test it on the real database.

---

## 7. Final queue-number allocation protocol

The allocator now uses this protocol:

```text
1. Determine the highest historical number if the sequence needs seeding
2. Attempt a conflict-tolerant sequence INSERT
3. Database uniqueness allows only one row for the scope
4. SELECT the surviving row FOR UPDATE
5. Repair last_number from historical state if necessary
6. Increment
7. Save
8. Keep the critical section inside transaction.atomic()
```

Core implementation shape:

```python
@transaction.atomic
def generate_queue_number(booking, queue_type):
    prefix = "A" if queue_type == QueueTicket.GENERAL else "P"
    seed_number = get_highest_existing_queue_number(booking, queue_type)

    QueueNumberSequence.objects.bulk_create(
        [
            QueueNumberSequence(
                branch=booking.branch,
                booking_date=booking.booking_date,
                queue_type=queue_type,
                last_number=seed_number,
            )
        ],
        ignore_conflicts=True,
    )

    sequence = QueueNumberSequence.objects.select_for_update().get(
        branch=booking.branch,
        booking_date=booking.booking_date,
        queue_type=queue_type,
    )

    if seed_number > sequence.last_number:
        sequence.last_number = seed_number

    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])

    return f"{prefix}{sequence.last_number:03d}"
```

On PostgreSQL, conflict-tolerant insert handles simultaneous creation without treating the expected conflict as an application failure. `select_for_update()` then serializes increments of the surviving row.

### Engineering lesson

**Constraints and locks are complementary.**

The unique constraint establishes identity. The row lock protects mutation of that identity's shared counter.

---

## 8. Why the transaction boundary matters

A row lock is useful only while the transaction that owns it is alive.

Smart Q keeps queue allocation inside `transaction.atomic()`. Ticket creation also stays transactionally coupled to allocation.

Conceptually:

```text
lock allocator row
increment
create/update ticket
commit
        ↓
lock released
```

If the lock were released before the dependent ticket write, another request could enter too early and the protection would be weaker than it appears.

### Engineering lesson

Do not ask only, “Did we call `select_for_update()`?” Ask, “What exact critical section is protected before the transaction commits?”

---

## 9. Historical compatibility and the data migration

Adding a new allocator to an existing installation creates another problem: existing ticket history may already have numbers such as `A007`.

If Day 38 simply created an empty sequence, the next deployment could incorrectly restart at `A001`.

Migration:

```text
queues/migrations/0008_queuenumbersequence.py
```

creates the table/constraint and backfills the highest numeric suffix for each existing:

```text
branch + booking date + queue type
```

Example:

```text
historical tickets: A001, A002, A007
backfilled last_number: 7
next allocation: A008
```

The runtime allocator also knows how to seed a missing sequence from existing ticket history. This protects test fixtures or controlled legacy/manual data where ticket records exist but the coordination row does not.

### Engineering lesson

A **schema migration** changes structure. A **data migration** preserves meaning while structure changes.

---

## 10. Gapless numbers were deliberately not required

Queue numbers are operational identifiers, not invoice numbers.

The invariant Smart Q protects is:

> Two successful allocations in the same branch/date/queue-type scope must not receive the same queue number.

A failed/rolled-back business operation may leave a gap. That is acceptable.

Trying to guarantee absolutely gapless numbering would increase transaction coupling and contention without improving queue fairness.

### Engineering lesson

Protect the real business invariant, not an aesthetic property that merely looks cleaner.

---

## 11. Appointment-capacity concurrency

Day 32 already performs the final capacity check under a transaction and locks the relevant `BranchService` row before counting reservations.

Day 38 verifies that design on PostgreSQL with two simultaneous customers attempting to consume a single remaining slot.

Required result:

```text
one request -> booking created
one request -> slot full
final booking count -> 1
```

### Lock-granularity trade-off

The current lock is per `branch + service`, not per individual generated slot.

That is safe but somewhat coarse. Different time slots for the same service can briefly serialize.

A dedicated slot-lock model could improve throughput, but it would add schema/logic. Day 39 should measure real contention before optimizing it.

### Engineering lesson

**Correctness first; measured optimization second.**

Do not add concurrency complexity because it feels more advanced. Add it when evidence shows the safe implementation is a bottleneck.

---

## 12. Why SQLite tests are not enough

SQLite remains useful for fast local development and regression testing, but its locking semantics are not PostgreSQL row-lock semantics.

Day 38 therefore uses two CI jobs:

```text
sqlite-regression
postgres-production
```

PostgreSQL-specific concurrency tests use `TransactionTestCase`, worker threads and separate database connections.

### Engineering lesson

**Test an infrastructure guarantee on the infrastructure that actually provides it.**

A mock or lightweight database can prove business logic, but it cannot prove every production lock/transaction behavior.

---

## 13. A test teardown failure that was not a business failure

An early PostgreSQL concurrency run passed its actual queue-number assertion, then failed while Django tried to destroy the test database.

Reason:

```text
production profile CONN_MAX_AGE = 60
worker thread retained a PostgreSQL connection
Django teardown could not drop test_smartq
```

The threaded tests were changed to explicitly close their per-thread connection.

### Engineering lesson

**Read the phase of a CI failure.**

Red can mean setup, assertion, teardown, packaging or infrastructure. Do not rewrite correct business logic to solve a cleanup problem.

---

## 14. Production environment contract

Day 38 moves environment-specific values out of source code.

`.env.example` documents the contract:

```text
SMARTQ_ENV
DJANGO_SECRET_KEY
DJANGO_DEBUG
ALLOWED_HOSTS
DATABASE_URL
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SAMESITE
CSRF_COOKIE_SAMESITE
SECURE_SSL_REDIRECT
USE_X_FORWARDED_PROTO
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
LOG_LEVEL
```

`.gitignore` excludes real `.env` files while allowing `.env.example` to remain versioned.

### Engineering lesson

Source control should contain the **configuration contract**, not production credentials.

---

## 15. Secret, DEBUG and database fail-fast rules

Production refuses to start when:

```text
DJANGO_SECRET_KEY is missing
DJANGO_DEBUG is true
ALLOWED_HOSTS is empty
DATABASE_URL is missing
DATABASE_URL does not configure PostgreSQL
```

Development can still use a clearly development-only fallback secret and SQLite.

### Engineering lesson

A deployment label should mean something. `SMARTQ_ENV=production` must activate real production invariants rather than being a cosmetic string.

---

## 16. CORS and CSRF are different controls

CORS answers:

> Which browser origins may communicate with/read the API cross-origin?

CSRF answers:

> Is this state-changing cookie-authenticated request intentionally coming from the trusted client/session flow?

Day 38 configures both separately.

```text
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
CSRF_TRUSTED_ORIGINS
```

Smart Q does not enable an allow-all CORS policy.

### Engineering lesson

**CORS does not replace CSRF protection.**

---

## 17. Explicit CSRF bootstrap for browser login

A session-authenticated browser needs a CSRF token before it can safely POST login credentials.

Day 38 adds:

```http
GET /api/v1/accounts/csrf/
```

Flow:

```text
GET /api/v1/accounts/csrf/
        ↓
Django sets CSRF cookie and returns token
        ↓
POST /api/v1/accounts/login/
Header: X-CSRFToken: <token>
        ↓
CSRF validation
        ↓
Django session established
```

`LoginAPIView` is explicitly wrapped in Django `csrf_protect`.

Tests use:

```python
APIClient(enforce_csrf_checks=True)
```

and prove:

```text
CSRF endpoint returns token/cookie
login without CSRF header -> 403
login with bootstrapped token -> 200
session /me request works afterward
```

### Engineering lesson

**Configuration is not protection unless the request path actually uses it.**

Security tests must also turn framework shortcuts off when those shortcuts would bypass the behavior being tested.

---

## 18. Session/cookie policy

Production defaults include:

```text
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

`SameSite` is configurable because final policy depends on frontend/API topology.

```text
same-site deployment -> Lax is a simple safer default
genuinely cross-site deployment -> may require None + HTTPS
```

The final value must be chosen from the actual deployment architecture, not guessed during backend development.

---

## 19. HTTPS, reverse proxy and HSTS

Production supports:

```text
SECURE_SSL_REDIRECT
SECURE_PROXY_SSL_HEADER (through USE_X_FORWARDED_PROTO)
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
```

Forwarded-protocol trust is safe only behind a trusted reverse proxy that strips/replaces untrusted client forwarding headers.

Django's first `check --deploy` run highlighted HSTS include-subdomain and preload recommendations.

Smart Q deliberately did **not** turn those commitments on globally just to make the warnings disappear. CI exercises a strict HSTS profile, while the deployment must review whether all subdomains are HTTPS-only before enabling those irreversible/broad commitments.

### Engineering lesson

Some security options are **infrastructure commitments**, not cosmetic toggles.

---

## 20. Production logging

Smart Q now emits timestamp/level/logger messages to stdout/stderr.

The hosting platform is expected to collect, retain and search those streams.

```text
LOG_LEVEL=INFO
```

Django security warnings are retained explicitly.

Do not log passwords, session cookies, CSRF tokens, pregnancy/disability attributes or other unnecessary sensitive request content.

### Engineering lesson

Cloud/container applications usually emit logs; infrastructure owns durable rotation/storage/search.

---

## 21. Backup and restore requirement

Day 38 defines the requirement without pretending a cloud provider has already been selected/configured.

A real PostgreSQL deployment must provide:

```text
automated backups at least daily
encrypted backup storage
known retention
point-in-time recovery when supported
documented restore procedure
restore drill before trusting real customer data
```

Initial target:

```text
>= 7 days recoverability
+ provider point-in-time recovery when available
+ verified restore before launch
```

### Engineering lesson

A backup is not fully proven until a restore works.

“Backup configured” and “recoverability verified” are separate engineering states.

---

## 22. Database transport security

Production credentials live in `DATABASE_URL`.

When PostgreSQL traffic crosses an untrusted network, the provider connection should require TLS (commonly via a provider-supplied option such as `sslmode=require`).

Day 38 does not hard-code one SSL mode because some managed platforms use private trusted networks or inject their own connection requirements.

### Engineering lesson

Security settings must match the real infrastructure trust boundary rather than guessing a provider-specific policy in source code.

---

## 23. Fresh-database and deployment verification

The PostgreSQL CI job creates a clean PostgreSQL 17 service and runs:

```text
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py check --deploy --fail-level WARNING
```

This proves committed migrations can construct Smart Q from an empty production database.

That is different from proving only that one developer's already-existing database can upgrade successfully.

### Engineering lesson

**Migration-from-empty is a release property.**

---

## 24. CI architecture

### SQLite job

Protects:

```text
local developer path
app-specific regressions
full established business suite
```

### PostgreSQL job

Protects:

```text
production settings import
fresh PostgreSQL migrations
Django deployment checks
queue-number concurrency
last-slot capacity concurrency
full Smart Q suite on PostgreSQL
```

This is a test matrix by risk: use each environment to prove the guarantees it actually owns.

---

## 25. Day 38 files introduced/changed

Core Day 38 work includes:

```text
.env.example
.gitignore
.github/workflows/django-tests.yml
requirements.txt
smartq/settings.py
accounts/api_views.py
accounts/api_urls.py
accounts/test_day38_csrf.py
queues/models.py
queues/services.py
queues/migrations/0008_queuenumbersequence.py
queues/test_day38_queue_numbers.py
services/test_day38_concurrency.py
docs/DAY38_PRODUCTION_HARDENING.md
README.md
```

---

## 26. Deliberate Day 38 non-goals

Day 38 does not:

- change the approved ETA formula;
- add ML forecasting;
- add WebSockets;
- add SMS/WhatsApp;
- add Celery/Redis;
- choose a hosting vendor prematurely;
- claim provider backups are active before a provider exists;
- enable HSTS preload blindly;
- optimize safe BranchService locking before measuring contention;
- claim Django `runserver` is a production server.

A real deployment must use an appropriate production WSGI/ASGI server behind the selected hosting/reverse-proxy setup.

---

## 27. Production launch checklist created by Day 38

Before production traffic:

```text
[ ] SMARTQ_ENV=production
[ ] strong DJANGO_SECRET_KEY stored outside Git
[ ] DJANGO_DEBUG=false
[ ] ALLOWED_HOSTS restricted
[ ] PostgreSQL DATABASE_URL configured
[ ] DB transport security matches provider guidance
[ ] frontend CORS origin configured exactly
[ ] CSRF trusted origins configured when cross-origin
[ ] cookie SameSite policy matches deployment topology
[ ] HTTPS termination is trusted
[ ] reverse-proxy header trust is correct
[ ] HSTS commitment reviewed
[ ] platform collects logs
[ ] automated DB backups enabled
[ ] retention known
[ ] restore tested
[ ] reminder command scheduled hourly
[ ] migrations run before traffic
[ ] final check --deploy is clean
```

---

## 28. Main engineering lessons

1. SQLite success does not prove PostgreSQL concurrency behavior.
2. Read-modify-write sequences require coordination under simultaneous requests.
3. ORM convenience APIs are not automatically concurrency primitives.
4. Conflict-tolerant insert, uniqueness constraints and row locks solve different parts of the allocator problem.
5. Transaction boundaries determine how long a lock actually protects correctness.
6. Data migrations preserve production meaning across schema changes.
7. Queue-number uniqueness matters; perfectly gapless numbering does not.
8. Safe coarse capacity locking is better than premature complexity; measure before optimizing.
9. Production should fail fast when its security/database invariants are not present.
10. Secrets and deployment values belong outside source control.
11. CORS and CSRF are separate controls.
12. Browser session login needs an explicit CSRF bootstrap/protected request path.
13. Secure-cookie policy depends partly on actual frontend/API topology.
14. Reverse-proxy headers are security inputs only across a trusted boundary.
15. HSTS subdomain/preload settings are commitments, not warning-suppression flags.
16. Threaded integration tests must manage their own database connections carefully.
17. Read the exact phase of CI failure before changing business logic.
18. A backup is only operationally trusted after restore verification.
19. Fresh PostgreSQL migration is a release property.
20. Production configuration and actual deployed infrastructure are related but not the same claim.

---

## 29. Day 39 handoff

Once the final Day 38 dual-database CI head is green, Day 39 moves to historical reporting and measured performance work.

The existing append-only `QueueEvent` history should power approved reports. Performance work should be evidence-driven:

```text
measure query counts
inspect repeated joins
review indexes
measure report latency
measure lock contention if needed
optimize only where evidence justifies it
```

The deterministic ETA formula remains unchanged unless explicit product approval says otherwise.

Day 40 remains the full role-journey, abuse-case, release and backend-security audit.
