# Smart Q - Day 38 Engineering Documentation

## SQLite3 and Production Hardening

## 1. Day 38 goal

Day 38 keeps Smart Q on SQLite3 and hardens the backend around the database choice that matches the current project scale.

Days 28-37 already established the business system: accounts and roles, booking/check-in, reception walk-ins, capacity, counter lifecycle, live queues, dashboard, disruption recovery, QueueEvent audit and System Admin controls.

Day 38 focuses on:

```text
SQLite3 as the single project database
explicit browser CSRF protection
environment-based secrets and deployment settings
HTTPS, cookie and origin policy
stable queue-number allocation
production logging and backup expectations
one reliable SQLite3 CI regression path
```

Day 38 does not change the approved product rules:

```text
Estimated Wait = People Ahead × Service.average_service_time
Check-in opens exactly 6 hours before appointment time
Priority = age >= 55 OR disability OR female + pregnancy for the visit
Branch opening time is the customer-service start boundary
```

---

## 2. Database decision

Smart Q uses SQLite3 for development, testing, demonstrations and the current deployment scope.

```text
Django ORM
    ↓
SQLite3
    ↓
db.sqlite3
```

The default database path is:

```text
BASE_DIR / db.sqlite3
```

A deployment can point SQLite3 at persistent mounted storage with:

```text
SMARTQ_SQLITE_PATH=/app/data/db.sqlite3
```

This keeps setup simple and removes unnecessary database infrastructure from the current project.

### Engineering lesson

Choose infrastructure for the scale you actually have. Smart Q does not need a more complex database layer while it remains a small-user project and prototype.

---

## 3. Dependencies

The project keeps only the dependencies required by the current backend:

```text
Django
Django REST Framework
django-cors-headers
```

No external database driver or database URL parser is required for SQLite3.

---

## 4. Queue-number allocation

Queue numbers remain scoped by:

```text
branch + booking date + queue type
```

`QueueNumberSequence` stores the latest number for each scope:

```text
QueueNumberSequence
├── branch
├── booking_date
├── queue_type
└── last_number
```

The migration also seeds sequence state from historical queue tickets so existing data does not restart from `A001` or `P001`.

Verified behaviors include:

```text
A001 then A002 for sequential General tickets
new day resets to A001
General and Priority sequences remain independent
existing sequence state is respected
historical tickets seed a missing sequence correctly
```

This keeps queue numbering predictable for the current Smart Q workload.

---

## 5. Booking capacity

The existing branch/service capacity rules remain unchanged:

```text
slot duration = Service.average_service_time
capacity = BranchService.max_bookings_per_slot
```

Bookings are still validated immediately before creation inside the existing transactional service path. The current project does not claim high-concurrency guarantees that are unnecessary for its present user volume.

---

## 6. Browser login and CSRF

Smart Q uses Django session authentication.

Browser login flow:

```text
GET /api/v1/accounts/csrf/
        ↓
receive CSRF cookie + token
        ↓
POST /api/v1/accounts/login/
with X-CSRFToken
        ↓
session established
```

The login endpoint is explicitly CSRF-protected. Tests using `APIClient(enforce_csrf_checks=True)` verify that a missing token is rejected and a valid token allows login.

CORS and CSRF remain separate controls. Allowing an origin does not disable CSRF protection.

---

## 7. Production-facing settings

`SMARTQ_ENV=production` keeps the important security checks:

```text
DJANGO_SECRET_KEY required
DJANGO_DEBUG must be false
ALLOWED_HOSTS required
secure session cookie
secure CSRF cookie
HTTPS redirect enabled by default
HSTS configurable
console logging enabled
```

The database remains SQLite3 in both development and production modes.

---

## 8. Origin and cookie policy

Supported variables:

```text
CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS
CSRF_TRUSTED_ORIGINS
SESSION_COOKIE_SAMESITE
CSRF_COOKIE_SAMESITE
```

The default SameSite value is `Lax`. Cross-site deployments must intentionally review cookie behavior before changing it.

---

## 9. HTTPS and reverse proxy settings

Supported variables:

```text
SECURE_SSL_REDIRECT
USE_X_FORWARDED_PROTO
SECURE_HSTS_SECONDS
SECURE_HSTS_INCLUDE_SUBDOMAINS
SECURE_HSTS_PRELOAD
```

Forwarded-protocol trust should only be enabled behind infrastructure that correctly controls forwarding headers.

---

## 10. Logging

Smart Q writes structured console logs for deployment collection.

Logs must not contain:

```text
passwords
session cookies
CSRF tokens
pregnancy/disability details
other unnecessary sensitive information
```

---

## 11. SQLite3 persistence and backups

SQLite3 is a file database, so deployment must keep `db.sqlite3` on persistent storage.

Minimum operational requirement:

```text
persistent database file
daily backup copy
known retention period
restore procedure
restore test before trusting important data
```

For this project, that is sufficient and keeps infrastructure proportional to the expected user volume.

---

## 12. Automated verification

GitHub Actions now has one database path:

```text
SQLite3 regression
```

The job verifies:

```text
requirements install
missing migration check
Django system checks
accounts and security tests
branch administration tests
service/capacity tests
counter tests
queue tests
booking/reception tests
notification tests
dashboard tests
rescheduling tests
QueueEvent audit tests
full Smart Q test suite
```

A green SQLite3 job is the Day 38 database acceptance criterion.

---

## 13. Day 38 boundary

Included:

```text
SQLite3-only database configuration
browser CSRF login bootstrap
environment secret validation
HTTPS/CORS/CSRF/cookie settings
queue-number sequence allocator
production console logging
SQLite3 persistence/backup guidance
single SQLite3 CI regression path
```

Not added:

```text
Celery
Redis
WebSockets
SMS/WhatsApp
ML forecasting
hosting-vendor-specific infrastructure
```

These remain outside backend v1 unless later required.

---

## 14. Completion rule

Day 38 is complete when the exact final branch head passes the SQLite3 CI job.

The next backend milestone is Day 39 reporting and performance review. The approved ETA formula remains unchanged.
