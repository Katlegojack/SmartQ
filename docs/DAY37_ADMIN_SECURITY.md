# Smart Q - Day 37 Engineering Documentation

## System Admin Management, Account Security, Throttling and Scheduler Decision

## 1. Purpose of Day 37

Day 37 hardens Smart Q's control plane before the production-database and deployment work planned for Day 38.

Days 28-36 established the operational queue system: authentication, role and branch authorization, check-in, reception walk-ins, capacity-aware booking, counter lifecycle, queue operations, manager dashboards, disruption recovery, rescheduling and append-only QueueEvent auditing.

Day 37 addresses a different question:

```text
Who configures Smart Q itself,
and how do we protect those account-management entry points?
```

The day focuses on:

- System Admin staff management;
- branch management;
- service management;
- BranchService/capacity management;
- safe account deactivation;
- password rotation;
- login/account-security throttling;
- reminder scheduler execution strategy;
- regression and abuse-case verification.

The approved queue ETA remains unchanged:

```text
Estimated Wait = People Ahead × Service.average_service_time
```

Day 37 does not alter queue ordering, check-in timing, priority rules, disruption logic or QueueEvent architecture.

---

## 2. Control Plane vs Operational Plane

A useful architecture distinction introduced on Day 37 is the difference between the **operational plane** and the **control plane**.

Operational plane examples:

```text
Receptionist checks in a customer
Counter Staff calls next
Counter Staff completes service
Branch Manager pauses a disrupted service
Customer selects a disruption replacement slot
```

Control plane examples:

```text
System Admin creates staff
System Admin creates a branch
System Admin configures services
System Admin maps a service to a branch
System Admin changes slot capacity
System Admin disables an account
```

These responsibilities should not share the same permission boundary.

Smart Q therefore reuses the existing `IsSystemAdmin` permission for configuration APIs rather than adding another parallel authorization mechanism.

### Engineering lesson

**Reuse a trusted security abstraction instead of scattering raw role checks across views.**

Centralized authorization is easier to audit, test and maintain.

---

## 3. Smart Q System Admin Is Not Django Superuser

Smart Q already stores business roles in `Profile.role`:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Day 37 preserves a deliberate boundary:

```text
Profile.SYSTEM_ADMIN != Django is_superuser
```

A Smart Q System Admin can manage Smart Q business configuration without automatically receiving unrestricted Django framework administration privileges.

Newly-created operational staff accounts therefore remain:

```text
is_staff = False
is_superuser = False
```

unless a separate Django administration decision is made outside the Smart Q business-role API.

### Engineering lesson

This is the **principle of least privilege**.

Grant the minimum authority required for the business operation. Do not use a framework-wide superuser flag as a shortcut for application authorization.

---

## 4. System Admin Staff Management APIs

Day 37 adds:

```http
GET  /api/v1/accounts/admin/staff/
POST /api/v1/accounts/admin/staff/
GET  /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/
PATCH /api/v1/accounts/admin/staff/<id>/activation/
```

Only authenticated `SYSTEM_ADMIN` users may access these endpoints.

### Staff creation

The System Admin can provision:

```text
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

Public customer registration remains unchanged and can only create `CUSTOMER`.

### Role/branch invariant

Smart Q already has a database constraint requiring:

```text
Receptionist   -> branch required
Counter Staff  -> branch required
Branch Manager -> branch required
Customer       -> branch must be null
System Admin   -> branch must be null
```

Day 37 validates the same rule before database persistence.

This gives two layers of protection:

```text
Serializer/business validation
        ↓
Database constraint
```

### Engineering lesson

**Do not rely on only one layer for important invariants.**

Application validation gives useful API errors. Database constraints protect integrity if another code path bypasses the serializer.

---

## 5. Atomic Staff Provisioning

Staff creation creates two related records:

```text
Django User
   +
Smart Q Profile
```

The operation uses `transaction.atomic`.

Desired behavior:

```text
Create User
Create Profile
        ↓
Both succeed -> COMMIT
Any step fails -> ROLLBACK
```

Without an atomic transaction, Smart Q could create a User without a Profile. That would leave an ambiguous account that authentication/authorization logic cannot safely classify.

### Engineering lesson

**Multi-record business operations should be treated as one transaction when partial success would create an invalid system state.**

---

## 6. Staff Update Safety

The staff update endpoint intentionally exposes only approved business fields such as:

```text
first_name
last_name
email
date_of_birth
gender
disability_status
role
branch
```

It does not expose arbitrary Django privilege flags.

Role and branch are validated together so a caller cannot create combinations such as:

```text
SYSTEM_ADMIN + branch
BRANCH_MANAGER + no branch
```

### Engineering lesson

**Mass assignment is dangerous.**

A serializer should explicitly define which fields are writable instead of allowing a request body to mutate every model attribute.

---

## 7. Safe Account Deactivation

Day 37 uses:

```text
User.is_active = False
```

instead of deleting operational staff accounts.

Why?

Smart Q now stores historical operational facts such as:

- QueueEvent actors;
- bookings;
- counter actions;
- audit timelines;
- branch operational history.

Deleting a staff identity can damage historical traceability.

Deactivation preserves the record but prevents normal Django authentication.

The activation API also protects against administrative lockout:

```text
System Admin cannot deactivate their own current account.
Smart Q must retain an active System Admin.
```

### Engineering lesson

This is the **soft-delete/deactivation pattern**.

Operational records often need to disappear from future workflows while remaining available for history and audit.

---

## 8. Branch Management APIs

Day 37 adds System Admin branch management:

```http
GET  /api/v1/branches/admin/
POST /api/v1/branches/admin/
GET  /api/v1/branches/admin/<id>/
PATCH /api/v1/branches/admin/<id>/
```

The existing public endpoint remains:

```http
GET /api/v1/branches/
```

Public catalogue behavior:

```text
only is_active=True
```

System Admin catalogue behavior:

```text
active + inactive branches
```

This keeps public/customer responses simple while allowing administrators to manage deactivated historical configuration.

### Branch-hours validation

Day 37 rejects:

```text
opening_time >= closing_time
```

The current MVP does not model overnight service centres. Therefore normal same-day branch hours must have closing time after opening time.

### Engineering lesson

**Different trust levels often need different serializers/endpoints.**

A customer catalogue and an administrative configuration screen do not need the same data or mutation rights.

---

## 9. Service Management APIs

Day 37 adds:

```http
GET  /api/v1/services/admin/
POST /api/v1/services/admin/
GET  /api/v1/services/admin/<id>/
PATCH /api/v1/services/admin/<id>/
```

The public service catalogue remains:

```http
GET /api/v1/services/
```

The administrative serializer validates:

```text
average_service_time > 0
```

This field is important because Smart Q uses `Service.average_service_time` in:

- appointment slot duration;
- deterministic ETA;
- disruption capacity calculations;
- future operational reporting.

### Engineering lesson

A value used by multiple downstream algorithms should be validated at its configuration boundary. Invalid source data creates invalid behavior everywhere downstream.

---

## 10. BranchService Capacity Management

Smart Q's capacity architecture uses:

```text
BranchService
├── branch
├── service
├── max_bookings_per_slot
└── is_active
```

Day 37 adds administrative APIs:

```http
GET  /api/v1/services/admin/branch-services/
POST /api/v1/services/admin/branch-services/
GET  /api/v1/services/admin/branch-services/<id>/
PATCH /api/v1/services/admin/branch-services/<id>/
```

An active mapping requires:

```text
active branch
AND
active service
```

The database already guarantees one unique `(branch, service)` mapping.

`max_bookings_per_slot` continues to use the existing positive-value validation.

### Engineering lesson

A foreign key proves that a referenced row **exists**. It does not prove that the row is **operationally valid**.

That is why Smart Q separately checks active state.

---

## 11. Why Hard DELETE Was Not Added

The original Day 37 roadmap used the term CRUD. The implementation intentionally interprets removal as lifecycle deactivation for core operational configuration.

A hard DELETE API for branches/services/staff would introduce risks:

```text
historical booking references
QueueEvent context
PROTECT/CASCADE interactions
audit trace loss
reporting inconsistencies
```

Therefore Day 37 uses:

```text
Create
Read
Update
Deactivate/reactivate
```

rather than destructive deletion.

### Engineering lesson

**CRUD is not a requirement to expose HTTP DELETE for every model.**

Business lifecycle semantics are more important than mechanically implementing four database verbs.

---

## 12. Password Change API

Day 37 adds:

```http
POST /api/v1/accounts/change-password/
```

The caller must be authenticated and provide:

```json
{
  "current_password": "...",
  "new_password": "..."
}
```

Rules:

- current password must be correct;
- new password must differ from current password;
- Django's configured password validators must accept the new password;
- password is changed using `set_password()`;
- the current trusted session is preserved using `update_session_auth_hash()`.

### Why `set_password()` matters

Passwords must never be stored directly as plain text.

Django's `set_password()` applies the configured password hashing system.

### Why update the session auth hash?

Changing a password changes Django's authentication hash.

Without `update_session_auth_hash()`, the user would unexpectedly lose the current trusted session immediately after successfully changing the password.

### Engineering lesson

**Use framework security primitives instead of implementing password hashing/session behavior yourself.**

---

## 13. Scoped API Throttling

Day 37 configures DRF scoped throttling for sensitive account endpoints.

Current scopes:

```text
login            -> 10/min
account_security -> 10/min
```

Login uses:

```python
ScopedRateThrottle
throttle_scope = "login"
```

Password change uses:

```python
ScopedRateThrottle
throttle_scope = "account_security"
```

The throttling is intentionally scoped rather than globally applied to every Smart Q endpoint.

Why?

Queue operations, dashboards, public catalogue reads and login attempts have different traffic characteristics.

### Engineering lesson

**Security controls should be risk-based.**

A login endpoint is brute-force sensitive. A live queue read endpoint may legitimately receive more frequent traffic.

---

## 14. Inactive Account Authentication

Django's authentication backend rejects users with:

```text
is_active = False
```

Day 37 explicitly tests the full flow:

```text
System Admin deactivates staff
        ↓
Staff login attempted
        ↓
authenticate() refuses account
        ↓
HTTP 401
```

### Engineering lesson

Do not only test the state change itself. Test the **downstream behavior that the state change is supposed to cause**.

---

## 15. Reminder Scheduler Decision

Smart Q already has:

```powershell
python manage.py process_check_in_reminders
```

The processor:

- creates hourly in-app check-in reminders during the six-hour window;
- stops reminders after check-in;
- cancels unchecked appointments after appointment time passes.

Day 37 makes the production execution decision:

```text
Keep the Django management command as the business entry point.
Run it hourly using the deployment platform's scheduler/cron facility.
Do not add Celery/Redis before the Day 40 backend deadline.
```

Examples of valid production runners later include:

- Linux cron;
- systemd timer;
- Azure/AWS/GCP scheduler;
- Render/Railway scheduled job;
- another approved infrastructure scheduler.

Why not Celery now?

Celery would add:

```text
worker process
message broker
broker configuration
failure/retry operations
more deployment infrastructure
```

That complexity is not required for v1's hourly reminder processor.

### Engineering lesson

**Choose the simplest architecture that satisfies the actual reliability requirement.**

Distributed infrastructure is not automatically more professional. Unnecessary infrastructure increases failure surface and operational burden.

---

## 16. Day 37 Abuse-Case Testing

Day 37 tests include scenarios such as:

```text
Customer cannot list/create staff
Customer cannot create branches
Customer cannot create services
Branch-scoped staff cannot exist without branch
System Admin cannot be assigned to branch
Staff endpoint does not operate on customer account
System Admin cannot deactivate self
Inactive staff cannot log in
Weak replacement password rejected
Incorrect current password rejected
Repeated login attempts throttled
Inactive branch/service mapping rejected
Deactivated catalogue records hidden publicly
```

### Engineering lesson

These are **negative tests** or **abuse-case tests**.

Security-sensitive features are not complete when only the happy path works. We must also prove that forbidden operations fail correctly.

---

## 17. CI Verification

Verified Day 37 code checkpoint:

```text
commit: faa7dacb7afabb191d9bd51d47157f56794cee6c
GitHub Actions run: 33461789242
```

Results:

```text
makemigrations --check --dry-run : PASS (No changes detected)
Django system check              : PASS (0 issues)
accounts                         : 19/19 PASS
branches                         : 4/4 PASS
services                         : 14/14 PASS
counters                         : 11/11 PASS
queues                           : 24/24 PASS
bookings                         : 22/22 PASS
notifications                    : 6/6 PASS
dashboard                        : 7/7 PASS
rescheduling                     : 12/12 PASS
Day 36 focused audit             : 9/9 PASS
full suite                       : 119/119 PASS
```

Full-suite result:

```text
Ran 119 tests in 132.488s
OK
```

### Engineering lesson

**Implemented is not the same as verified.**

Day 37 is only considered stable after the new tests and all previous regression suites pass together.

---

## 18. Day 37 Architecture Summary

```text
Public customer registration
        ↓
CUSTOMER only

SYSTEM_ADMIN
        ↓
Staff management
Branch configuration
Service configuration
BranchService capacity configuration
        ↓
Validated business invariants
        ↓
Django ORM / database constraints

Sensitive account actions
        ↓
Authentication
Scoped throttling
Password validators
Session security
```

---

## 19. What Day 37 Deliberately Does Not Do

Day 37 does not:

- change Smart Q's ETA formula;
- add machine learning;
- add WebSockets;
- add SMS/WhatsApp;
- introduce Celery/Redis;
- move from SQLite to PostgreSQL;
- move `SECRET_KEY` to environment variables;
- configure production CORS/CSRF/cookies;
- configure production HTTPS/proxy settings;
- harden queue-number generation for database concurrency.

Those production database/configuration concerns are Day 38 work.

---

## 20. Day 38 Handoff

Day 38 should focus on production persistence and concurrency:

```text
1. PostgreSQL configuration
2. Environment-based secrets/settings
3. DEBUG/ALLOWED_HOSTS production split
4. CORS/CSRF/session-cookie strategy
5. HTTPS/security headers/proxy configuration
6. Queue-number concurrency hardening
7. Transaction/locking review for capacity-critical writes
8. Logging and backup strategy
9. Fresh-database migration verification
10. Full regression CI
```

The Day 40 deadline remains unchanged.

---

## 21. Main Engineering Lessons From Day 37

1. **Least privilege:** application System Admin is not automatically Django superuser.
2. **Centralized authorization:** reuse `IsSystemAdmin` rather than duplicate role checks.
3. **Defense in depth:** validate invariants in serializers and database constraints.
4. **Atomicity:** User + Profile creation must succeed or fail together.
5. **Explicit writable fields:** avoid mass assignment of privilege fields.
6. **Soft deactivation:** preserve audit/history while stopping future access.
7. **Control plane separation:** configuration APIs deserve stricter permissions than operational reads.
8. **Operational validity differs from referential validity:** an existing branch/service may still be inactive.
9. **Framework security primitives:** use Django password hashing, validators and session-hash tools.
10. **Scoped throttling:** apply rate limits according to endpoint risk.
11. **Negative testing:** prove forbidden actions fail.
12. **Regression testing:** prove new security work does not break old queue behavior.
13. **Avoid accidental complexity:** hourly scheduler + management command is enough for v1; Celery is not required yet.
14. **Verification is a separate engineering state:** code is not complete until CI confirms it.
