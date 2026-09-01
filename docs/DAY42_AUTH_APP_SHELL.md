# Smart Q - Day 42 Engineering Documentation

## Authentication, Session Restoration and Application Shell

## 1. Goal

Day 42 turns the Day 41 visual foundation into the first authenticated Smart Q frontend workflow. The browser now connects to the completed backend account contract using CSRF-protected Django sessions, restores identity through `/api/v1/accounts/me/`, and routes users to a workspace that matches the backend-provided role.

The frontend remains HTML, CSS and vanilla JavaScript. Business authority remains in Django and DRF.

## 2. Public authentication routes

Day 42 adds:

- `/login/`
- `/register/`

The sign-in page uses the existing username/password login API. Public registration mirrors the existing customer registration serializer and never accepts caller-controlled staff roles or branches.

## 3. Shared browser API client

`static/js/api/client.js` centralizes same-origin credentials, JSON parsing, CSRF bootstrap, `X-CSRFToken` injection for unsafe methods, `204 No Content` handling and structured API errors.

This prevents every page module from implementing security-sensitive request behavior independently.

## 4. CSRF and session login

The browser flow is:

```text
GET /api/v1/accounts/csrf/
        ↓
receive CSRF cookie + token
        ↓
POST /api/v1/accounts/login/
X-CSRFToken: <token>
credentials: same-origin
        ↓
Django session created
```

Django rotates the CSRF secret during login, so the frontend clears its cached token after authentication and obtains a fresh token before the next unsafe request.

## 5. Session restoration

The frontend does not use local storage as proof of identity. Protected workspaces restore the current account from:

```http
GET /api/v1/accounts/me/
```

The response supplies the user's identity, role and branch scope. Missing sessions are redirected to sign-in.

## 6. Role-aware frontend routes

The shared application shell supports:

```text
customer       -> /app/customer/
receptionist   -> /app/reception/
counter_staff  -> /app/counter/
branch_manager -> /app/manager/
system_admin   -> /app/admin/
```

`/app/` is a neutral entry point that redirects after `/me/` resolves the current role. If a signed-in user manually opens a frontend route for another role, the shell redirects to the route that matches the backend-provided role.

This routing is a user-experience control only. API authorization remains the security boundary.

## 7. Shared authenticated shell

The Day 42 shell establishes the layout later role screens will reuse:

- left navigation
- account identity
- role context
- branch scope
- session state
- account/security sections
- sign-out action

Day 42 does not prematurely implement booking, reception, counter, manager or administration business screens.

## 8. Password change

The security section connects to:

```http
POST /api/v1/accounts/change-password/
```

The frontend confirms the new password locally. The backend validates the current password and Django password policy. A successful change preserves the current trusted session.

## 9. Sign-out

The shell signs out through:

```http
POST /api/v1/accounts/logout/
```

No authentication token is stored in local storage.

## 10. Registration handoff

After successful customer registration, the frontend signs the new account in through the normal login API and routes it to `/app/customer/`. This avoids inventing a second authentication path for newly-created accounts.

## 11. Visual rules preserved

Day 42 keeps the approved interface direction: white dominant surfaces, light-blue structure, blue primary actions, restrained green success states, modest borders/radii, no emoji interface language, no glassmorphism, no decorative gradients and no oversized generated-dashboard card wall.

## 12. JavaScript modules

```text
static/js/api/client.js
static/js/auth/session.js
static/js/pages/home.js
static/js/pages/login.js
static/js/pages/register.js
static/js/pages/app-shell.js
```

Authentication and session logic is reusable rather than duplicated in later role screens.

## 13. Automated verification

`smartq/test_day42_frontend_auth.py` verifies public auth pages, all five workspace routes, static module discovery, the browser account endpoint contract, the CSRF -> login -> `/me/` -> logout journey, and the absence of emoji-style interface copy on public screens.

CI retains all backend and Day 41 regression suites before the complete Smart Q test suite.

## 14. Engineering boundary

The browser may decide what to display, but role authorization, branch authorization, check-in timing, priority, capacity, queue state, ETA, counter assignment and reporting scope remain backend decisions.

## 15. Completion rule

Day 42 is complete only when login/register render, CSRF-protected login works, `/me/` restoration works, role routing works, logout works, password change is wired, focused Day 42 tests pass, all existing tests pass and the exact Day 42 branch head is green in GitHub Actions.
