# Smart Q - Day 38 Engineering Documentation

## PostgreSQL, Concurrency and Production Hardening

## 1. Purpose

Day 38 moves Smart Q from a development-safe backend toward a production-safe backend.

Days 28-37 proved business behavior primarily with SQLite. SQLite remains useful for fast local development, but production queue systems have additional concerns:

```text
multiple requests at the same time
real row-level database locking
secrets outside source control
HTTPS and secure cookies
browser origin / CSRF policy
production logging
fresh-database migrations
backup and restore operations
```

Day 38 therefore treats deployment configuration and concurrency as part of backend correctness.

The following product rules remain unchanged:

```text
Estimated Wait = People Ahead × Service.average_service_time
Check-in opens exactly 6 hours before appointment time
Priority = age >= 55 OR disability OR female + pregnancy for visit
Branch opening time is the service-start boundary
```

No Day 38 production work changes queue priority or ETA policy.

---

## 2. Development database vs production database

Local development still defaults to SQLite because it is simple and fast:

```text
SMARTQ_ENV=development
DATABASE_URL not supplied
        ↓
SQLite
```

Production is different:

```text
SMARTQ_ENV=production
        ↓
DJANGO_SECRET_KEY required
ALLOWED_HOSTS required
DATABASE_URL required
DEBUG must be false
Database must be PostgreSQL
```

If one of those production invariants is violated, Smart Q raises `ImproperlyConfigured` instead of silently falling back to an unsafe development setting.

### Engineering lesson

**Fail fast when a deployment cannot satisfy an important invariant.**

A server refusing to start is easier to detect and repair than a server quietly running with the wrong database or an exposed Django debug page.

---

## 3. PostgreSQL dependencies

Day 38 adds:

```text
psycopg[binary]
dj-database-url
django-cors-headers
```

`psycopg` is Django's PostgreSQL driver.

`dj-database-url` converts a deployment-style URL such as:

```text
postgresql://user:password@host:5432/database
```

into Django's `DATABASES` configuration.

`django-cors-headers` gives Smart Q an explicit browser-origin policy for a separately hosted frontend.

### Engineering lesson

Dependencies should solve a real infrastructure problem. Day 38 adds only the packages required by the production architecture rather than introducing a broad deployment framework.

---

## 4. The queue-number race condition

Before Day 38, queue numbers were produced by reading the latest ticket and adding one:

```text
latest = A007
next = A008
```

That works when requests arrive one after another.

Under concurrency this can happen:

```text
Request A reads A007
Request B reads A007
Request A calculates A008
Request B calculates A008
```

The arithmetic is correct, but the operation is not atomic.

This is a classic **read-modify-write race condition**.

---

## 5. QueueNumberSequence

Day 38 introduces a database-backed allocation record:

```text
QueueNumberSequence
├── branch
├── booking_date
├── queue_type
└── last_number
```

The unique allocation scope is:

```text
branch + booking_date + queue_type
```

Therefore:

```text
Johannesburg / 2026-09-02 / GENERAL  -> own sequence
Johannesburg / 2026-09-02 / PRIORITY -> own sequence
Johannesburg / 2026-09-03 / GENERAL  -> own sequence
Pretoria     / 2026-09-02 / GENERAL  -> own sequence
```

A database uniqueness constraint ensures there can be only one sequence row for each scope.

---

## 6. Transactional number allocation

`generate_queue_number()` now runs inside `transaction.atomic()` and uses a row lock:

```python
@transaction.atomic
def generate_queue_number(booking, queue_type):
    prefix = "A" if queue_type == QueueTicket.GENERAL else "P"

    sequence, _ = QueueNumberSequence.objects.select_for_update().get_or_create(
        branch=booking.branch,
        booking_date=booking.booking_date,
        queue_type=queue_type,
        defaults={"last_number": 0},
    )
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])

    return f"{prefix}{sequence.last_number:03d}"
```

On PostgreSQL, once the sequence row exists, `select_for_update()` prevents two transactions from incrementing that row at the same time.

The first ever allocation is also protected by the database unique constraint. Two concurrent transactions may both attempt to create the first sequence row; one wins and the other resolves against the row that now exists.

### Engineering lesson

**Locks and constraints solve different parts of concurrency.**

The unique constraint protects creation of the coordination row. The row lock serializes later increments.

---

## 7. Why not lock the Branch row?

One alternative was to lock the entire branch whenever a queue number was allocated.

That would be simpler conceptually, but much coarser:

```text
one General allocation blocks Priority allocation
one date may block another date
unrelated branch configuration could share the same lock target
```

The dedicated sequence row is more precise.

### Trade-off

The new model adds a migration and another database table.

We accepted that extra schema complexity because the concurrency invariant becomes explicit and the lock scope is substantially better.

---

## 8. Do queue numbers have to be gapless?

No.

The important Smart Q invariant is:

> Two successful tickets in the same branch/date/queue-type scope must not receive the same queue number.

Queue numbers are operational identifiers, not legal invoice numbers.

Trying to guarantee a perfectly gapless sequence would increase transaction coupling and contention without creating meaningful queue value.

### Engineering lesson

**Protect the business invariant that matters, not an aesthetic property that merely looks nice.**

---

## 9. Queue sequence data migration

Adding `QueueNumberSequence` alone would cause an existing installation to restart at `A001` and `P001`.

Migration `queues.0008_queuenumbersequence` therefore includes a data migration.

It scans existing queue tickets, groups them by:

```text
branch
booking_date
queue_type
```

and records the highest historical numeric suffix as `last_number`.

Example:

```text
existing tickets: A001, A002, A003, A007
migration state: last_number = 7
next allocation: A008
```

### Engineering lesson

A **schema migration** changes structure. A **data migration** preserves the meaning of existing production data while that structure changes.

---

## 10. Existing appointment-capacity locking

Day 32 already made the final booking-capacity check transactional.

For a capacity-critical create/update:

```text
lock BranchService row
        ↓
count current reservations
        ↓
reject if capacity reached
        ↓
create/update Booking
        ↓
commit transaction / release lock
```

This prevents two PostgreSQL transactions from both consuming the same final appointment capacity.

### Lock granularity trade-off

The lock scope is currently `branch + service`, not `branch + service + individual slot`.

Therefore two bookings for different time slots of the same branch/service may briefly serialize.

A future dedicated slot-lock row could increase concurrency, but it would add schema and operational complexity.

For v1, the existing lock is safe and simple. Day 39 performance work should measure contention before optimizing it.

### Engineering lesson

**Correctness first, measured optimization second.**

Do not make concurrency design more complex until there is evidence that the safe implementation is actually a bottleneck.

---

## 11. Why PostgreSQL-specific tests matter

SQLite is useful for local development, but it does not provide the same row-lock behavior as PostgreSQL.

A concurrency test that passes only on SQLite cannot prove a PostgreSQL locking guarantee.

Day 38 therefore keeps:

```text
SQLite regression CI
```

and adds:

```text
PostgreSQL production CI
```

PostgreSQL-only `TransactionTestCase` tests use separate threads and separate database connections to issue simultaneous operations.

### Engineering lesson

**Test an infrastructure guarantee on the infrastructure that provides that guarantee.**

Mocks and lightweight databases are useful, but they cannot prove every production behavior.

---

## 12. Production settings contract

Day 38 moves deployment-specific settings to environment variables.

Important variables are documented in `.env.example`:

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

Real `.env` files are ignored by Git.

### Engineering lesson

**Source control should contain the configuration contract, not the production secrets.**

`.env.example` teaches an operator what must be configured. `.env` contains real values and must stay outside Git.

---

## 13. SECRET_KEY

The old development settings stored a Django secret key directly in source code.

Day 38 changes this behavior:

```text
development -> safe development-only fallback is allowed
production  -> DJANGO_SECRET_KEY is mandatory
```

The production key must come from the deployment platform's secret store or environment configuration.

### Engineering lesson

A secret is not secret if it is committed to a public repository.

Production credentials must be rotatable without changing application source code.

---

## 14. DEBUG and ALLOWED_HOSTS

Production now refuses to start when:

```text
DJANGO_DEBUG=true
```

Production also requires explicit `ALLOWED_HOSTS`.

This protects against accidentally exposing Django debug information and prevents arbitrary Host headers from being treated as valid application hosts.

---

## 15. CORS vs CSRF

CORS and CSRF solve different problems.

### CORS

CORS answers:

> Is browser JavaScript from this origin allowed to read/send cross-origin requests to the API?

Configured with:

```text
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
```

Smart Q does **not** enable an allow-all CORS policy.

### CSRF

Because Smart Q uses Django session authentication, state-changing browser requests also need CSRF protection.

Trusted frontend origins are configured separately with:

```text
CSRF_TRUSTED_ORIGINS
```

### Engineering lesson

**CORS is not a substitute for CSRF protection.**

Allowing a frontend origin to communicate with an API does not remove the need to prove that a state-changing request is legitimate.

---

## 16. Session cookies

Production defaults include:

```text
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

`Secure` cookies are sent only over HTTPS.

`HttpOnly` keeps the session identifier out of normal browser JavaScript access.

`SameSite` remains configurable because the correct value depends on how the final frontend and API domains are deployed.

### Trade-off

`SameSite=Lax` is a safer simple default for same-site deployment.

A genuinely cross-site frontend may require `SameSite=None`, which also requires HTTPS and should be chosen only after the final frontend/API topology is known.

---

## 17. HTTPS and reverse proxy

Production defaults to HTTPS redirection.

Smart Q can trust `X-Forwarded-Proto` only when explicitly configured for a trusted reverse proxy:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

This must only be enabled when the hosting proxy strips/replaces client-supplied forwarding headers correctly.

### Engineering lesson

**Trust boundaries matter.**

A forwarding header becomes security information only when it comes from infrastructure you control and trust.

---

## 18. HSTS

Day 38 supports HSTS through:

```text
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
```

CI runs Django's deployment check with the strict profile enabled.

However, `includeSubDomains` and browser preload are **not** automatically enabled for every future deployment.

Why?

`includeSubDomains` commits every subdomain to HTTPS.

HSTS preload is intentionally difficult to reverse after browsers ship the domain on preload lists.

### Engineering lesson

Some security options are **infrastructure commitments**, not checkboxes that should be turned on simply to remove a warning.

---

## 19. Production logging

Day 38 configures application logging to standard output/error rather than writing rotating application files inside the Django container/process.

The deployment platform can then collect and retain logs centrally.

The log level is configured with:

```text
LOG_LEVEL=INFO
```

Django security messages are explicitly retained at warning level.

Smart Q should not log passwords, session cookies, CSRF tokens, disability/pregnancy information or other unnecessary sensitive request data.

### Engineering lesson

In container/cloud deployments, the application should usually **emit logs**, while infrastructure handles storage, rotation and search.

---

## 20. Database backup requirement

Day 38 defines the production backup requirement, but it does not falsely claim a backup provider is already configured.

The final PostgreSQL deployment must provide:

```text
1. automated database backups at least daily
2. retention appropriate to the deployment/provider
3. encrypted backup storage
4. point-in-time recovery when the provider supports it
5. a documented restore procedure
6. at least one restore test before production launch
```

A backup that has never been restored is not yet proven useful.

### Recommended launch target

For the first production release:

```text
Daily automated backup
+ provider point-in-time recovery if available
+ minimum 7-day recoverability target
+ restore drill before real customer data is trusted to the system
```

The exact retention period may be increased according to organisation/legal requirements.

### Engineering lesson

**Backup configuration and restore verification are separate states.**

Creating backups is only half the reliability problem. We must know that they can actually restore Smart Q.

---

## 21. PostgreSQL transport security

Production database credentials belong in `DATABASE_URL`.

If the managed database is reached across an untrusted network, its provider URL/configuration should require TLS, commonly with a PostgreSQL parameter such as:

```text
sslmode=require
```

Some cloud platforms provide a private trusted network or inject their own TLS parameters. Therefore Day 38 does not hard-code one SSL mode that could conflict with the eventual hosting provider.

### Engineering lesson

**Application security configuration must respect the actual infrastructure boundary.**

Document the requirement, then configure the final provider correctly rather than guessing a provider-specific connection policy in source code.

---

## 22. Fresh database verification

The PostgreSQL CI job starts a clean PostgreSQL service and runs:

```text
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
```

This verifies that Smart Q can be built from an empty production database using committed migrations only.

That is different from merely proving that a developer's existing database can be upgraded.

### Engineering lesson

**Migration-from-empty is a release property.**

A new deployment should not depend on invisible state from a developer's machine.

---

## 23. Django deployment checks

PostgreSQL CI also runs:

```text
python manage.py check --deploy --fail-level WARNING
```

Day 38 intentionally treated its warnings as design feedback.

The first production check exposed HSTS deployment decisions. Those were reviewed rather than blindly silenced.

### Engineering lesson

A security check is useful when we understand why it is complaining. Passing the check is not the goal by itself; satisfying or deliberately resolving the underlying security concern is the goal.

---

## 24. Threaded test connection lesson

The first PostgreSQL queue concurrency run produced a useful test-infrastructure failure.

The actual concurrency assertion passed, but Django could not destroy `test_smartq` because a worker thread still held a persistent PostgreSQL connection.

Day 38 production settings use a non-zero connection lifetime (`CONN_MAX_AGE`). Therefore `close_old_connections()` can intentionally retain a still-healthy connection.

The threaded tests now explicitly close their per-thread database connection.

### Engineering lesson

**Read the phase of a test failure.**

A red CI job can fail during setup, the assertion, cleanup, packaging or deployment. Do not rewrite working business logic when the actual failure is test teardown.

---

## 25. CI architecture

Day 38 CI has two complementary jobs.

### SQLite regression

Protects the local-development path and all established business behavior.

It runs app-level regressions plus the full suite.

### PostgreSQL production

Verifies:

```text
production configuration imports
fresh PostgreSQL migrations
Django deployment security checks
queue-number concurrency
appointment-capacity concurrency
full Smart Q suite on PostgreSQL
```

### Engineering lesson

Use a **test matrix by risk**.

The lightweight environment protects developer speed. The production-like environment proves guarantees that depend on the real database and deployment profile.

---

## 26. What Day 38 deliberately does not do

Day 38 does not:

- change the approved ETA formula;
- add ML forecasting;
- add SMS/WhatsApp;
- add WebSockets;
- introduce Celery/Redis;
- choose a hosting vendor prematurely;
- claim managed backups are active before a database provider exists;
- turn on HSTS preload without domain/infrastructure review;
- optimize BranchService locking before measuring contention.

These boundaries keep Day 38 focused on production correctness rather than scope expansion.

---

## 27. Day 38 deployment checklist

Before a real production launch, the deployment operator must confirm:

```text
[ ] SMARTQ_ENV=production
[ ] DJANGO_SECRET_KEY is a strong secret outside Git
[ ] DJANGO_DEBUG=false
[ ] ALLOWED_HOSTS contains only intended hosts
[ ] DATABASE_URL points to PostgreSQL
[ ] database transport/TLS matches provider security guidance
[ ] CORS_ALLOWED_ORIGINS matches the actual frontend origin
[ ] CSRF_TRUSTED_ORIGINS matches trusted browser origins
[ ] credentialed CORS is enabled only when required
[ ] SameSite policy matches frontend/API topology
[ ] HTTPS terminates at trusted infrastructure
[ ] SECURE_SSL_REDIRECT is enabled
[ ] forwarding-header trust matches the reverse proxy
[ ] HSTS policy has been reviewed
[ ] logs are collected by the platform
[ ] automated database backups are enabled
[ ] backup retention is known
[ ] a restore has been tested
[ ] reminder management command is scheduled hourly
[ ] migrations run before application traffic
[ ] python manage.py check --deploy is clean for final settings
```

---

## 28. Main Day 38 engineering lessons

1. Development database behavior is not proof of production concurrency behavior.
2. Read-modify-write operations require database coordination under concurrency.
3. Unique constraints and row locks solve complementary race conditions.
4. Transaction boundaries determine whether a lock actually protects the write.
5. Data migrations preserve existing meaning when schema changes.
6. Correctness is more important than perfectly gapless operational numbers.
7. Safe coarse locking is better than premature fine-grained complexity.
8. Environment configuration belongs outside source code.
9. Production should fail fast when required security/database guarantees are missing.
10. CORS and CSRF are different controls.
11. Secure cookie policy depends partly on frontend/API topology.
12. Reverse-proxy headers are trustworthy only at a deliberate infrastructure boundary.
13. HSTS preload/subdomain settings are commitments, not cosmetic warning suppressors.
14. Log to platform-managed streams; do not casually persist sensitive application logs.
15. Backups are not proven until restore works.
16. Fresh-database migrations must be tested independently of developer state.
17. Read exactly where CI failed before deciding what code to change.
18. Test production-specific guarantees on the real production database engine.

---

## 29. Day 39 handoff

Once Day 38's final dual-database CI is green, Day 39 should move to historical reporting and performance review.

Day 39 should use the existing append-only `QueueEvent` history to build approved operational reporting without changing Smart Q's deterministic ETA policy.

Performance work should be evidence-driven:

```text
measure query counts
inspect repeated joins
review indexes
identify slow report paths
measure lock contention if any
optimize only where evidence justifies it
```

Day 40 remains the full backend journey/security/release audit.
