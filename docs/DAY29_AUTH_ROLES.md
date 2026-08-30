# Day 29 - Authentication and Role-Based Branch Authorization

## Objective

Day 29 replaces the temporary Day 28 `User.is_staff` queue boundary with the first real Smart Q authorization model and adds the account APIs required by the future frontend.

The goal is not simply "add login". The goal is to answer two different security questions correctly:

```text
Authentication -> Who are you?
Authorization  -> What are you allowed to do, and at which branch?
```

## Starting point

At the end of Day 28:

- customer-owned booking/notification APIs used `IsAuthenticated` and request-user scoping;
- queue staff actions used a temporary `IsQueueStaff` permission based on Django `User.is_staff`;
- the queue core had live read APIs and operational regression tests;
- there was no Smart Q-specific role model;
- there was no branch assignment for staff;
- there was no public register/login/logout/me REST contract.

The temporary `is_staff` boundary solved the immediate Day 28 security issue, but it could not distinguish Receptionist, Counter Staff, Branch Manager, and System Administrator, and it could not restrict staff to one branch.

---

## Role model introduced

`accounts.Profile` now includes:

```text
CUSTOMER
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

### CUSTOMER

Customer-facing role. Public registration always creates this role.

### RECEPTIONIST

May view live queue information for the assigned branch but may not perform service transitions such as Call Next, Complete, or No Show.

### COUNTER_STAFF

May view and operate live queues for the assigned branch.

### BRANCH_MANAGER

May view and operate live queues for the assigned branch. This role is also the foundation for future branch-management APIs.

### SYSTEM_ADMIN

Global Smart Q operational role. It is intentionally not restricted to one branch.

---

## Branch scope

Profile now has an optional ForeignKey to `branches.Branch`.

The current MVP rule is:

```text
CUSTOMER        -> branch must be NULL
SYSTEM_ADMIN    -> branch must be NULL
RECEPTIONIST    -> branch is required
COUNTER_STAFF   -> branch is required
BRANCH_MANAGER  -> branch is required
```

A database `CheckConstraint` enforces this rule so invalid role/branch combinations cannot silently enter the database.

Existing profiles safely default to CUSTOMER during migration. Existing Django superusers are explicitly migrated to SYSTEM_ADMIN because they already hold global Django authority. Ordinary historical `is_staff=True` users are NOT automatically promoted into Smart Q roles; they must be deliberately assigned a role and branch.

---

## Public customer registration

Endpoint:

```http
POST /api/v1/accounts/register/
```

Registration accepts customer fields only:

```text
username
password
first_name
last_name
email
date_of_birth
gender
disability_status
```

It intentionally does not expose:

```text
role
branch
is_staff
is_superuser
```

Even if a caller submits those privilege fields, the created account remains:

```text
role = CUSTOMER
branch = NULL
is_staff = False
is_superuser = False
```

User and Profile creation run inside one database transaction.

Django's configured password validators are reused through `validate_password()`.

---

## Session authentication APIs

Day 29 uses Django's built-in session authentication rather than adding JWT without first choosing the final frontend deployment architecture.

Endpoints:

```http
POST /api/v1/accounts/login/
POST /api/v1/accounts/logout/
GET  /api/v1/accounts/me/
```

### Login

`POST /api/v1/accounts/login/` authenticates username/password with Django's `authenticate()` and creates a Django session using `login()`.

Accounts missing a Smart Q Profile are rejected because queue authorization and priority rules depend on Profile.

### Logout

`POST /api/v1/accounts/logout/` terminates the authenticated session.

### Current account

`GET /api/v1/accounts/me/` returns the authenticated identity and authorization context needed by the frontend:

```text
id
username
first_name
last_name
email
role
branch_id
branch_name
date_of_birth
gender
disability_status
```

For Customer and System Admin accounts, branch values are `null`.

### Production deployment limitation

Session authentication is a valid Django/DRF foundation, but a frontend hosted on a different origin requires an explicit production CORS/CSRF/secure-cookie strategy. Day 29 documents this rather than claiming cross-origin production authentication is complete.

---

## Reusable permission architecture

New file:

```text
accounts/permissions.py
```

Core classes:

```text
SmartQRolePermission
IsQueueViewer
IsQueueOperator
IsBranchManager
IsSystemAdmin
```

### IsQueueViewer

Allowed roles:

```text
RECEPTIONIST
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

### IsQueueOperator

Allowed roles:

```text
COUNTER_STAFF
BRANCH_MANAGER
SYSTEM_ADMIN
```

### Object-level branch authorization

Role permission is only the first gate. For a Branch or Counter object, branch-scoped staff must also satisfy:

```text
profile.branch_id == object.branch.id
```

SYSTEM_ADMIN bypasses the branch restriction because it is a global role.

---

## Queue API permission changes

Day 28's temporary `queues.permissions.IsQueueStaff` file was removed.

Queue APIs now use Smart Q roles from `accounts.permissions`.

### Queue operations

```http
POST /api/v1/queues/counters/<counter_id>/call-next/
POST /api/v1/queues/counters/<counter_id>/complete/
POST /api/v1/queues/counters/<counter_id>/no-show/
```

Use `IsQueueOperator` and object-level branch checks.

### Queue reads

```http
GET /api/v1/queues/branches/<branch_id>/waiting/
GET /api/v1/queues/counters/<counter_id>/current/
```

Use `IsQueueViewer` and object-level branch checks.

### Customer live tracker

```http
GET /api/v1/queues/my-current/
```

Remains `IsAuthenticated` and user-owned because it is a customer endpoint rather than a staff endpoint.

---

## Django Admin

`ProfileAdmin` now exposes role and branch assignment so development/admin users can deliberately configure staff identities.

Admin list information includes:

```text
user
role
branch
gender
disability_status
created_at
```

Filters include role and branch.

---

## Automated tests added

### Account API tests

Day 29 tests verify:

- public registration creates User + CUSTOMER Profile;
- passwords are hashed rather than stored directly;
- registration cannot self-assign SYSTEM_ADMIN, is_staff, is_superuser, or branch;
- duplicate usernames are rejected;
- valid login starts a session;
- `/accounts/me/` returns the role;
- invalid credentials return 401;
- logout ends the session.

### Queue authorization tests

Queue tests now verify:

- CUSTOMER cannot operate a counter;
- RECEPTIONIST can view the assigned branch queue;
- RECEPTIONIST cannot Call Next;
- COUNTER_STAFF can operate its assigned branch;
- COUNTER_STAFF from another branch receives 403;
- SYSTEM_ADMIN can view any branch;
- existing Day 28 operational regressions still pass.

---

## CI hardening

GitHub Actions now also runs:

```powershell
python manage.py makemigrations --check --dry-run
```

This catches a common Django failure mode: model code changed but the required migration file was forgotten.

Full verification sequence:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test accounts
python manage.py test queues
python manage.py test bookings
python manage.py test
```

---

## Security decisions

### Why public registration always creates CUSTOMER

A client request is untrusted input. Role escalation cannot be left to caller-controlled fields.

### Why ordinary is_staff users are not automatically migrated

Django Admin access is not identical to a Smart Q operational role. Automatically mapping every historical staff user to Counter Staff, Manager, or System Admin would grant new domain authority without deliberate assignment.

### Why superusers are mapped to SYSTEM_ADMIN

Django superusers already possess global application authority. Mapping them preserves their existing privilege level rather than creating a surprising loss of access.

### Why Receptionist is view-only for queue operations

Reception staff need visibility into the waiting room and current service state, but service transitions belong to Counter Staff/Manager roles. This implements least privilege.

### Why branch scope is object-level

A role tells us what category of action a user may perform. The Branch assignment tells us where that authority applies.

---

## Known limitations after Day 29

Day 29 does not yet implement:

- staff creation/role assignment REST APIs;
- multi-branch staff assignment;
- fine-grained service-level staff permissions;
- password reset/email verification;
- rate limiting/login throttling;
- production cross-origin CORS/CSRF configuration;
- JWT/token authentication decision for a separately hosted frontend;
- audit events for role changes;
- customer check-in;
- walk-ins/reception ticket issuance;
- manager dashboards.

---

## Git workflow note

Day 29 was branched from the verified Day 28 head because Day 28 PR #16 is still marked Draft and the connected GitHub draft-transition action fails due to a connector GraphQL schema error.

Day 29 draft PR:

```text
#17 - Day 29: Add authentication and role-based branch authorization
```

Temporary base:

```text
feature/day28-operational-core
```

After PR #16 is manually marked Ready for review and squash-merged to `main`, PR #17 should be retargeted to `main`.

---

## Day 29 outcome

Day 29 moves Smart Q from a generic "logged in vs not logged in" model to a real domain authorization foundation:

```text
Identity
   ↓
Smart Q Role
   ↓
Branch Scope
   ↓
API Permission
   ↓
Object Permission
   ↓
Allowed / Denied
```

This is a prerequisite for safely implementing check-in, reception, counter management, manager dashboards, and future enterprise branch operations.
