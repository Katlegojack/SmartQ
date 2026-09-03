# Smart Q Live Smoke Demo

This setup is for local development and GitHub Codespaces only. `bootstrap_demo` refuses to run when `SMARTQ_ENV=production`.

## Start a fresh demo

```bash
python manage.py migrate
python manage.py bootstrap_demo
python manage.py runserver 0.0.0.0:8000
```

In GitHub Codespaces, Smart Q automatically trusts the active forwarded port-8000 development hostname for `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. No manual CSRF export is required after this change.

## Demo accounts

All demo accounts use this password:

```text
SmartQDemo2026!
```

| Username | Role | Scope |
|---|---|---|
| `customer_demo` | Customer | Own bookings / queue / recovery |
| `reception_demo` | Receptionist | Pretoria Central |
| `counter_demo` | Counter Staff | Pretoria Central, Counter 1 |
| `manager_demo` | Branch Manager | Pretoria Central |
| `admin_demo` | System Admin | Global |

## Demo operational data

Branches:

- Pretoria Central
- Centurion Service Centre

Services:

- ID Applications
- Passport Applications
- Collections

Both branches have active BranchService capacity mappings. Pretoria has two General counters and one Priority counter. Centurion has one General and one Priority counter.

## Suggested end-to-end smoke test

1. Sign in as `customer_demo` and book an appointment.
2. Sign out and sign in as `reception_demo` to inspect branch intake and queue visibility.
3. Sign in as `counter_demo`, open Counter 1, and exercise the serving workflow when an eligible customer is waiting.
4. Sign in as `manager_demo` to inspect branch operations, staffing, history, and disruption controls.
5. Sign in as `admin_demo` to inspect global staff, branch, service, and capacity administration.

The browser may guide valid choices, but all queue, capacity, role, branch, priority, disruption, and rescheduling invariants remain enforced by the backend APIs.
